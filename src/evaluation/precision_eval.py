"""Precision-focused model evaluation with walk-forward stability.

Computes precision at multiple thresholds, walk-forward temporal stability,
AUC-PR, false positive severity, and cascading elimination filters.

Used post-training to evaluate model quality before promotion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch
from sklearn.metrics import average_precision_score

from src.config import PromotionEvalConfig


@dataclass
class PrecisionEvalResult:
    """Complete evaluation result for a single model run."""

    # Per-threshold metrics
    precision_at_threshold: dict[float, float]
    recall_at_threshold: dict[float, float]
    signal_count_at_threshold: dict[float, int]

    # AUC-PR
    auc_pr: float

    # Walk-forward stability (at primary_threshold)
    wf_precision_per_window: list[float]
    wf_precision_mean: float
    wf_precision_std: float
    stability_score: float  # mean - penalty * std

    # FP severity
    avg_fp_return: float
    avg_tp_return: float
    fp_severity: float  # abs(avg_fp_return - buy_threshold)

    # Recall at primary threshold
    recall_at_primary: float
    signal_count_at_primary: int

    # Walk-forward coverage (fraction of windows that qualified)
    coverage_ratio: float  # n_qualifying_windows / n_total_windows

    # Brier score
    brier_score: float

    # Elimination result
    elimination_stage: str  # "passed", "failed_stability", "failed_recall", "failed_signals", "failed_coverage", "failed_generalization"
    passed_all_filters: bool

    # Val-test generalization gap (optional, set when test_precision_up is available)
    val_test_precision_gap: float = 0.0

    # Adaptive threshold (effective threshold used, may differ from configured primary)
    effective_threshold: float = 0.65


def collect_val_predictions(
    model: torch.nn.Module,
    val_dataloader,
) -> tuple[np.ndarray, np.ndarray]:
    """Collect all validation predictions in a single pass.

    Args:
        model: LSTMForecaster in eval mode.
        val_dataloader: Validation DataLoader.

    Returns:
        (prob_up, targets) arrays of shape (n_samples,).
    """
    model.eval()
    all_prob_up = []
    all_targets = []

    with torch.no_grad():
        for batch in val_dataloader:
            x, y = batch
            probs = model.predict_proba(x)  # (batch, num_classes)
            prob_up = probs[:, 1].cpu().numpy()  # P(UP)
            all_prob_up.append(prob_up)
            all_targets.append(y.cpu().numpy())

    return np.concatenate(all_prob_up), np.concatenate(all_targets)


def compute_precision_at_thresholds(
    prob_up: np.ndarray,
    targets: np.ndarray,
    thresholds: list[float],
) -> tuple[dict[float, float], dict[float, float], dict[float, int]]:
    """Compute precision, recall, and signal count at each threshold.

    Args:
        prob_up: Array of P(UP) per sample.
        targets: Binary target array (1=UP, 0=NOT_UP).
        thresholds: List of probability thresholds.

    Returns:
        (precision_dict, recall_dict, signal_count_dict)
    """
    n_positive = int(targets.sum())
    precision_dict = {}
    recall_dict = {}
    signal_dict = {}

    for t in thresholds:
        predicted_positive = prob_up >= t
        n_predicted = int(predicted_positive.sum())
        signal_dict[t] = n_predicted

        if n_predicted == 0:
            precision_dict[t] = 0.0
            recall_dict[t] = 0.0
        else:
            tp = int((predicted_positive & (targets == 1)).sum())
            precision_dict[t] = tp / n_predicted
            recall_dict[t] = tp / n_positive if n_positive > 0 else 0.0

    return precision_dict, recall_dict, signal_dict


def compute_walk_forward_precision(
    prob_up: np.ndarray,
    targets: np.ndarray,
    sample_dates: np.ndarray,
    threshold: float,
    window_size: int,
    step_size: int,
    min_signals: int,
) -> tuple[list[float], float, float, int]:
    """Compute precision in rolling walk-forward windows.

    Windows with fewer than min_signals predictions above threshold are
    excluded from mean/std computation.

    Args:
        prob_up: Array of P(UP) per sample.
        targets: Binary target array.
        sample_dates: Date array aligned with prob_up/targets.
        threshold: Probability threshold for UP classification.
        window_size: Window size in trading days.
        step_size: Step between windows in trading days.
        min_signals: Minimum predictions above threshold per window.

    Returns:
        (precisions_per_window, mean, std, total_windows)
    """
    unique_dates = np.unique(sample_dates)
    unique_dates.sort()
    n_dates = len(unique_dates)

    precisions = []
    total_windows = 0
    start_idx = 0

    while start_idx + window_size <= n_dates:
        total_windows += 1
        window_start = unique_dates[start_idx]
        window_end = unique_dates[min(start_idx + window_size - 1, n_dates - 1)]

        mask = (sample_dates >= window_start) & (sample_dates <= window_end)
        window_prob = prob_up[mask]
        window_targets = targets[mask]

        predicted_positive = window_prob >= threshold
        n_predicted = int(predicted_positive.sum())

        if n_predicted >= min_signals:
            tp = int((predicted_positive & (window_targets == 1)).sum())
            precision = tp / n_predicted
            precisions.append(precision)

        start_idx += step_size

    if len(precisions) == 0:
        return [], 0.0, 0.0, total_windows

    mean = float(np.mean(precisions))
    std = float(np.std(precisions))
    return precisions, mean, std, total_windows


def compute_fp_severity(
    prob_up: np.ndarray,
    targets: np.ndarray,
    forward_returns: np.ndarray | None,
    threshold: float,
    buy_threshold: float,
) -> tuple[float, float, float]:
    """Compute false positive and true positive return characteristics.

    Args:
        prob_up: Array of P(UP) per sample.
        targets: Binary target array.
        forward_returns: Continuous forward returns per sample. If None,
            returns (0.0, 0.0, buy_threshold).
        threshold: Probability threshold for UP classification.
        buy_threshold: The target buy threshold (e.g. 0.025).

    Returns:
        (avg_fp_return, avg_tp_return, fp_severity)
        fp_severity = abs(avg_fp_return - buy_threshold) -- lower is better
    """
    if forward_returns is None:
        return 0.0, 0.0, buy_threshold

    predicted_positive = prob_up >= threshold

    # False positives: predicted UP but actually NOT_UP
    fp_mask = predicted_positive & (targets == 0)
    # True positives: predicted UP and actually UP
    tp_mask = predicted_positive & (targets == 1)

    # Clean NaN from forward returns
    clean_fwd = np.nan_to_num(forward_returns, nan=0.0)

    avg_fp = float(np.mean(clean_fwd[fp_mask])) if fp_mask.any() else 0.0
    avg_tp = float(np.mean(clean_fwd[tp_mask])) if tp_mask.any() else 0.0
    severity = abs(avg_fp - buy_threshold)

    return avg_fp, avg_tp, severity


def compute_auc_pr(prob_up: np.ndarray, targets: np.ndarray) -> float:
    """Compute Area Under Precision-Recall Curve.

    Args:
        prob_up: Array of P(UP) per sample.
        targets: Binary target array.

    Returns:
        AUC-PR score.
    """
    if len(np.unique(targets)) < 2:
        return 0.0
    return float(average_precision_score(targets, prob_up))


def compute_adaptive_threshold(
    prob_up: np.ndarray,
    targets: np.ndarray,
    base_threshold: float = 0.65,
    min_threshold: float = 0.50,
    min_signal_pct: float = 0.05,
    min_precision: float = 0.50,
    step: float = 0.05,
) -> float:
    """Find the highest usable threshold for a given probability distribution.

    Searches from base_threshold downward until finding a threshold where:
    (1) at least min_signal_pct of predictions exceed it, AND
    (2) precision at that threshold exceeds min_precision (better than random).

    This adapts the promotion threshold per cluster, accommodating clusters
    with compressed probability distributions that can't reach the base threshold.

    Args:
        prob_up: Array of P(UP) per sample.
        targets: Binary target array (1=UP, 0=NOT_UP).
        base_threshold: Starting threshold (highest to try).
        min_threshold: Floor threshold (won't go below this).
        min_signal_pct: Minimum fraction of predictions above threshold.
        min_precision: Minimum acceptable precision at threshold.
        step: Step size for threshold search.

    Returns:
        Adapted threshold (between min_threshold and base_threshold).
    """
    n_samples = len(prob_up)
    if n_samples == 0:
        return min_threshold

    threshold = base_threshold
    while threshold >= min_threshold:
        predicted_up = prob_up >= threshold
        n_predicted = int(predicted_up.sum())
        signal_pct = n_predicted / n_samples

        if signal_pct >= min_signal_pct and n_predicted > 0:
            tp = int((predicted_up & (targets == 1)).sum())
            precision = tp / n_predicted
            if precision >= min_precision:
                return threshold

        threshold -= step

    return min_threshold


def evaluate_model(
    model: torch.nn.Module,
    val_dataloader,
    eval_config: PromotionEvalConfig,
    sample_dates: np.ndarray,
    forward_returns: np.ndarray | None = None,
    buy_threshold: float = 0.025,
    test_precision_up: float | None = None,
    adaptive_threshold: bool = False,
) -> PrecisionEvalResult:
    """Full precision-based evaluation of a trained model.

    Orchestrates: collect predictions -> threshold sweep -> AUC-PR ->
    walk-forward stability -> FP severity -> cascading elimination.

    Args:
        model: LSTMForecaster (will be set to eval mode).
        val_dataloader: Validation DataLoader.
        eval_config: Promotion evaluation configuration.
        sample_dates: Date array for walk-forward windowing (aligned with
            val dataset valid_indices + seq_len).
        forward_returns: Continuous forward returns (aligned same as dates).
            If None, FP severity defaults to 0.
        buy_threshold: The target buy threshold (e.g. 0.025).
        test_precision_up: Test set precision for val-test gap filter.
            If None, generalization filter is skipped.
        adaptive_threshold: If True, compute and use an adaptive primary threshold
            when the base threshold produces no signals.

    Returns:
        PrecisionEvalResult with all metrics and elimination status.
    """
    # Collect predictions
    prob_up, targets = collect_val_predictions(model, val_dataloader)

    # Adaptive threshold: if base primary_threshold produces no signals, find a lower usable one
    effective_threshold = eval_config.primary_threshold
    if adaptive_threshold:
        signals_at_base = int((prob_up >= eval_config.primary_threshold).sum())
        if signals_at_base == 0:
            effective_threshold = compute_adaptive_threshold(
                prob_up, targets,
                base_threshold=eval_config.primary_threshold,
                min_threshold=0.50,
            )

    # Threshold sweep
    precision_dict, recall_dict, signal_dict = compute_precision_at_thresholds(
        prob_up, targets, eval_config.thresholds,
    )

    # AUC-PR
    auc_pr = compute_auc_pr(prob_up, targets)

    # Walk-forward stability at effective threshold (adapted or base)
    wf_precisions, wf_mean, wf_std, wf_total_windows = compute_walk_forward_precision(
        prob_up, targets, sample_dates,
        threshold=effective_threshold,
        window_size=eval_config.wf_window_size,
        step_size=eval_config.wf_step_size,
        min_signals=eval_config.min_signals_per_window,
    )

    # Coverage ratio: fraction of windows with enough signals
    coverage_ratio = len(wf_precisions) / wf_total_windows if wf_total_windows > 0 else 0.0

    # Brier score: calibration quality
    brier_score = float(np.mean((prob_up - targets.astype(np.float64)) ** 2))

    # FP severity at effective threshold
    avg_fp, avg_tp, fp_sev = compute_fp_severity(
        prob_up, targets, forward_returns,
        threshold=effective_threshold,
        buy_threshold=buy_threshold,
    )

    # Effective threshold metrics (uses adaptive threshold if active)
    recall_at_primary = recall_dict.get(effective_threshold, 0.0)
    signals_at_primary = signal_dict.get(effective_threshold, 0)
    # If effective_threshold is not in the swept thresholds, compute directly
    if effective_threshold not in recall_dict:
        predicted_up = prob_up >= effective_threshold
        n_predicted = int(predicted_up.sum())
        signals_at_primary = n_predicted
        n_positive = int(targets.sum())
        if n_predicted > 0 and n_positive > 0:
            tp = int((predicted_up & (targets == 1)).sum())
            recall_at_primary = tp / n_positive
        else:
            recall_at_primary = 0.0

    # Cascading elimination
    elimination_stage = "passed"
    passed = True

    # Filter 1: Stability — require enough windows and bounded std
    if len(wf_precisions) < 2:
        elimination_stage = "failed_stability"
        passed = False
    elif wf_mean > 0 and (wf_std / wf_mean) > eval_config.max_std_ratio:
        elimination_stage = "failed_stability"
        passed = False

    # Filter 2: Minimum recall
    if passed and recall_at_primary < eval_config.min_recall:
        elimination_stage = "failed_recall"
        passed = False

    # Filter 3: Minimum signals
    if passed and signals_at_primary < eval_config.min_signals_per_window:
        elimination_stage = "failed_signals"
        passed = False

    # Filter 4: Coverage ratio — penalize models that only predict in few windows
    if passed and coverage_ratio < 0.5:
        elimination_stage = "failed_coverage"
        passed = False

    # Compute val-test precision gap (for logging and Filter 5)
    val_prec_up = precision_dict.get(0.50, 0.0)  # best available val precision
    val_test_gap = 0.0
    if test_precision_up is not None and val_prec_up > 0:
        val_test_gap = val_prec_up - test_precision_up

    # Filter 5: Generalization gap — reject models with excessive val-test degradation
    if passed and test_precision_up is not None and val_test_gap > eval_config.max_val_test_gap:
        elimination_stage = "failed_generalization"
        passed = False

    # Stability score (computed regardless, for logging)
    # Apply coverage penalty: models with low coverage get proportionally lower scores
    stability_score = wf_mean - eval_config.stability_penalty * wf_std
    if coverage_ratio < 1.0:
        stability_score *= coverage_ratio

    # Apply generalization penalty to stability score
    if test_precision_up is not None and val_test_gap > eval_config.max_val_test_gap:
        gen_penalty = max(0.5, 1.0 - (val_test_gap - eval_config.max_val_test_gap))
        stability_score *= gen_penalty

    return PrecisionEvalResult(
        precision_at_threshold=precision_dict,
        recall_at_threshold=recall_dict,
        signal_count_at_threshold=signal_dict,
        auc_pr=auc_pr,
        wf_precision_per_window=wf_precisions,
        wf_precision_mean=wf_mean,
        wf_precision_std=wf_std,
        stability_score=stability_score,
        avg_fp_return=avg_fp,
        avg_tp_return=avg_tp,
        fp_severity=fp_sev,
        recall_at_primary=recall_at_primary,
        signal_count_at_primary=signals_at_primary,
        coverage_ratio=coverage_ratio,
        brier_score=brier_score,
        val_test_precision_gap=val_test_gap,
        effective_threshold=effective_threshold,
        elimination_stage=elimination_stage,
        passed_all_filters=passed,
    )


def log_eval_to_mlflow(
    result: PrecisionEvalResult,
    client,
    run_id: str,
) -> None:
    """Log all PrecisionEvalResult metrics to MLflow.

    Metrics are prefixed with 'val_' for consistency with training metrics.

    Args:
        result: Evaluation result from evaluate_model().
        client: MLflow client instance.
        run_id: MLflow run ID.
    """
    # Per-threshold metrics
    for t in sorted(result.precision_at_threshold.keys()):
        suffix = f"{int(t * 100):03d}"  # e.g., 050, 065, 080
        client.log_metric(run_id, f"val_precision_at_{suffix}", result.precision_at_threshold[t])
        client.log_metric(run_id, f"val_recall_at_{suffix}", result.recall_at_threshold[t])
        client.log_metric(run_id, f"val_signals_at_{suffix}", result.signal_count_at_threshold[t])

    # AUC-PR
    client.log_metric(run_id, "val_auc_pr", result.auc_pr)

    # Walk-forward stability
    client.log_metric(run_id, "val_wf_precision_mean", result.wf_precision_mean)
    client.log_metric(run_id, "val_wf_precision_std", result.wf_precision_std)
    client.log_metric(run_id, "val_stability_score", result.stability_score)
    client.log_metric(run_id, "val_wf_n_windows", len(result.wf_precision_per_window))

    # FP severity
    client.log_metric(run_id, "val_avg_fp_return", result.avg_fp_return)
    client.log_metric(run_id, "val_avg_tp_return", result.avg_tp_return)
    client.log_metric(run_id, "val_fp_severity", result.fp_severity)

    # Recall and signals at primary threshold
    client.log_metric(run_id, "val_recall_at_primary", result.recall_at_primary)
    client.log_metric(run_id, "val_signals_at_primary", result.signal_count_at_primary)

    # Coverage ratio, Brier score, and generalization gap
    client.log_metric(run_id, "val_coverage_ratio", result.coverage_ratio)
    client.log_metric(run_id, "val_brier_score", result.brier_score)
    client.log_metric(run_id, "val_test_precision_gap", result.val_test_precision_gap)

    # Adaptive threshold
    client.log_metric(run_id, "val_effective_threshold", result.effective_threshold)

    # Elimination result (as params, not metrics — for MLflow UI filtering)
    client.log_param(run_id, "val_elimination_stage", result.elimination_stage)
    client.log_param(run_id, "val_passed_all_filters", str(result.passed_all_filters).lower())
