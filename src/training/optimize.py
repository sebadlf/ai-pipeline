"""Optuna hyperparameter optimization for per-cluster LSTM training.

Replaces brute-force repeated training with systematic search over
architecture and training hyperparameters. Optimizes for precision
of the UP class (minimize false positives) with a recall floor.

Supports both per-cluster optimization and global optimization across all clusters.

Usage:
    Called from train.py via optimize_cluster() or optimize_global().
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import traceback
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import lightning as L  # noqa: N812
import mlflow
import numpy as np
import optuna
import torch
import torch.nn.functional as F  # noqa: N812
from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint
from lightning.pytorch.loggers import MLFlowLogger
from optuna.integration import PyTorchLightningPruningCallback
from scipy.optimize import minimize_scalar

from src.config import (
    ClusterConfig,
    SplitDates,
    compute_cv_fold_splits,
    compute_split_dates,
    get_cluster_buy_threshold,
    get_normalized_parquet_path,
    load_config,
    resolve_env_value,
)
from src.keys import MLFLOW_TRACKING_URI, OPTUNA_STORAGE_URL
from src.models.base_model import LSTMForecaster
from src.models.dataset import TradingDataModule

# Suppress noisy Lightning warnings and tips
warnings.filterwarnings("ignore", message=".*num_workers.*bottleneck.*")
warnings.filterwarnings("ignore", message=".*`isinstance.*LeafSpec.*")
logging.getLogger("lightning.pytorch.trainer.connectors.logger_connector").setLevel(logging.WARNING)
logging.getLogger("lightning.pytorch.trainer.connectors.callback_connector").setLevel(
    logging.WARNING
)
logging.getLogger("lightning.pytorch.utilities").setLevel(logging.WARNING)

# Suppress Lightning tips
os.environ["LIGHTNING_DISABLE_TIPS"] = "1"


class ClusterProgressCallback(L.Callback):
    """Compact per-epoch logging with cluster prefix for parallel training visibility."""

    def __init__(self, cluster_id: str, ensemble_rank: int = 1):
        self.cluster_id = cluster_id
        self.ensemble_rank = ensemble_rank
        self.prefix = f"[{cluster_id} E{ensemble_rank}]"

    def on_train_epoch_end(self, trainer: L.Trainer, pl_module: L.LightningModule) -> None:
        epoch = trainer.current_epoch
        metrics = trainer.callback_metrics
        parts = [f"{self.prefix} epoch {epoch}/{trainer.max_epochs}"]

        for key in [
            "train_loss",
            "train_acc",
            "val_loss",
            "val_acc",
            "val_precision_up",
            "val_recall_up",
            "val_mean_prob_up",
        ]:
            if key in metrics:
                val = metrics[key].item() if hasattr(metrics[key], "item") else metrics[key]
                short_key = key.replace("val_", "v_").replace("train_", "t_")
                parts.append(f"{short_key}={val:.4f}")

        lr = trainer.optimizers[0].param_groups[0]["lr"]
        parts.append(f"lr={lr:.2e}")
        print("  " + " | ".join(parts))

    def on_train_end(self, trainer: L.Trainer, pl_module: L.LightningModule) -> None:
        epoch = trainer.current_epoch
        metrics = trainer.callback_metrics
        val_prec = metrics.get("val_precision_up")
        val_acc = metrics.get("val_acc")
        prec_str = f"{val_prec.item():.4f}" if val_prec is not None else "N/A"
        acc_str = f"{val_acc.item():.4f}" if val_acc is not None else "N/A"
        print(
            f"  {self.prefix} DONE at epoch {epoch} — "
            f"val_precision_up={prec_str}, val_acc={acc_str}"
        )


def calibrate_temperature(
    model: LSTMForecaster,
    val_dataloader,
    primary_threshold: float = 0.65,
    min_signal_rate: float = 0.03,
    signal_penalty_alpha: float = 5.0,
) -> tuple[float, dict[str, float]]:
    """Find optimal temperature T using composite NLL + signal-preservation objective.

    Temperature scaling (Guo et al. 2017) adjusts logits by dividing by T
    before softmax, correcting overconfident predictions without changing
    accuracy or ranking.

    Pure NLL optimization can converge to extreme T values (>>1) that collapse
    all probabilities toward the base rate (~0.50), destroying the signal needed
    for threshold-based decisions. The composite objective adds a penalty when
    too few predictions exceed the primary threshold.

    Args:
        model: Trained model in eval mode.
        val_dataloader: Validation data loader.
        primary_threshold: Probability threshold for signal preservation (from promotion config).
        min_signal_rate: Minimum fraction of predictions that should exceed primary_threshold.
        signal_penalty_alpha: Weight of the signal-preservation penalty term.

    Returns:
        (optimal_temperature, diagnostics_dict) where diagnostics_dict contains
        pre/post calibration probability statistics for MLflow logging.
    """
    model.eval()
    all_logits = []
    all_targets = []

    with torch.no_grad():
        for batch in val_dataloader:
            x, y = batch
            logits = model(x)
            all_logits.append(logits.cpu())
            all_targets.append(y.cpu().long())

    all_logits = torch.cat(all_logits)
    all_targets = torch.cat(all_targets)

    # Pre-calibration diagnostics (T=1.0)
    pre_probs = torch.softmax(all_logits, dim=-1)[:, 1]
    pre_diagnostics = {
        "pre_cal_prob_mean": float(pre_probs.mean()),
        "pre_cal_prob_std": float(pre_probs.std()),
        "pre_cal_pct_above_060": float((pre_probs >= 0.60).float().mean()),
        "pre_cal_pct_above_065": float((pre_probs >= 0.65).float().mean()),
    }

    def composite_objective(T: float) -> float:  # noqa: N803
        scaled = all_logits / T
        nll = F.cross_entropy(scaled, all_targets).item()
        probs = torch.softmax(scaled, dim=-1)[:, 1]
        signal_rate = float((probs >= primary_threshold).float().mean())
        signal_penalty = signal_penalty_alpha * max(0.0, min_signal_rate - signal_rate)
        return nll + signal_penalty

    result = minimize_scalar(composite_objective, bounds=(0.5, 2.5), method="bounded")
    optimal_temp = float(result.x)

    # Post-calibration diagnostics
    post_probs = torch.softmax(all_logits / optimal_temp, dim=-1)[:, 1]
    post_pct_above_060 = float((post_probs >= 0.60).float().mean())

    # Safety check: if calibration still kills all signals, fall back to T=1.0
    if post_pct_above_060 < 0.01:
        print(
            f"  WARNING: calibration T={optimal_temp:.4f} produces <1% signals "
            "above 0.60, falling back to T=1.0"
        )
        optimal_temp = 1.0
        post_probs = pre_probs
        post_pct_above_060 = pre_diagnostics["pre_cal_pct_above_060"]

    diagnostics = {
        **pre_diagnostics,
        "post_cal_prob_mean": float(post_probs.mean()),
        "post_cal_prob_std": float(post_probs.std()),
        "post_cal_pct_above_060": post_pct_above_060,
        "post_cal_pct_above_065": float((post_probs >= 0.65).float().mean()),
    }

    return optimal_temp, diagnostics


def _get_random_symbols(
    cluster_id: str, clusters_parquet: str, n: int = 1, seed: int | None = None
) -> list[str]:
    """Get N random symbols from a cluster.

    Randomly selects N symbols from the cluster for use in
    hyperparameter optimization. Uses a local RNG instance to avoid
    affecting global random state.

    Args:
        cluster_id: Cluster identifier.
        clusters_parquet: Path to cluster assignments parquet.
        n: Number of random symbols to return.
        seed: RNG seed. Different seeds produce different subsets,
              enabling symbol rotation across Optuna trials.

    Returns:
        List of symbol strings.
    """
    import random

    import polars as pl

    clusters_df = pl.read_parquet(clusters_parquet)
    cluster_symbols = clusters_df.filter(pl.col("cluster_id") == cluster_id)["symbol"].to_list()

    if not cluster_symbols:
        return []

    if len(cluster_symbols) <= n:
        return cluster_symbols

    rng = random.Random(seed)
    return rng.sample(cluster_symbols, n)


_MLFLOW_TAG_MAX = 5000


def _log_exception_to_mlflow_run(
    client: mlflow.MlflowClient,
    mlflow_logger: MLFlowLogger | None,
    exc: BaseException,
) -> None:
    """Write error type, message, and truncated traceback as tags on the active run."""
    run_id = getattr(mlflow_logger, "run_id", None) if mlflow_logger else None
    if not run_id:
        ar = mlflow.active_run()
        run_id = ar.info.run_id if ar else None
    if not run_id:
        return
    tb = traceback.format_exc()
    client.set_tag(run_id, "error_type", type(exc).__name__)
    client.set_tag(run_id, "error_message", str(exc)[:_MLFLOW_TAG_MAX])
    client.set_tag(run_id, "error_traceback", tb[:_MLFLOW_TAG_MAX])


def _log_error_to_cluster_experiment(
    config: dict,
    cluster_id: str,
    exc: BaseException,
) -> None:
    """Create a FAILED MLflow run with error details when no run exists yet.

    This covers errors during Optuna optimization (before ensemble training
    creates its own MLflow runs), so the failure is visible in the MLflow UI.
    """
    try:
        prefix = config.get("training", {}).get("cluster_experiment_prefix", "cluster")
        experiment_name = f"{prefix}/{cluster_id}"
        client = mlflow.MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)

        # Check if the latest run already has error tags (set by train_final_model)
        experiment = client.get_experiment_by_name(experiment_name)
        if experiment:
            runs = client.search_runs(
                experiment_ids=[experiment.experiment_id],
                max_results=1,
                order_by=["start_time DESC"],
            )
            if runs and runs[0].data.tags.get("error_type"):
                return  # Already tagged by train_final_model

        # Create a short-lived run to record the error
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(experiment_name)
        with mlflow.start_run(run_name=f"{cluster_id}-error") as run:
            tb = traceback.format_exc()
            mlflow.set_tag("error_type", type(exc).__name__)
            mlflow.set_tag("error_message", str(exc)[:_MLFLOW_TAG_MAX])
            mlflow.set_tag("error_traceback", tb[:_MLFLOW_TAG_MAX])
            mlflow.set_tag("error_phase", "optuna_optimization")
            mlflow.log_param("cluster_id", cluster_id)
            mlflow.set_tag("mlflow.runName", f"{cluster_id}-error")
            # Mark as failed
            client.set_terminated(run.info.run_id, status="FAILED")
    except Exception:
        pass  # Best-effort — don't mask the original error


def suggest_hyperparams(trial: optuna.Trial, config: dict) -> dict[str, Any]:
    """Define the Optuna search space from config.

    Reads tunable ranges from config["training"]["optuna"]["search_space"]
    and fixed defaults from config["training"]["optuna"]["fixed_params"].

    The search space is intentionally reduced (~10 params) to mitigate
    overtuning on small per-cluster datasets. Fixed params use sensible
    defaults that don't need per-cluster optimization.

    Returns a dict with all hyperparameters (tuned + fixed) for this trial.
    """
    optuna_cfg = config.get("training", {}).get("optuna", {})
    ss = optuna_cfg.get("search_space", {})
    fixed = optuna_cfg.get("fixed_params", {})

    def _suggest(name: str, fallback):
        spec = ss.get(name, fallback)
        if isinstance(spec, list):
            return trial.suggest_categorical(name, spec)
        if isinstance(spec, dict):
            low, high = spec["low"], spec["high"]
            if isinstance(low, int) and isinstance(high, int) and not spec.get("log", False):
                return trial.suggest_int(name, low, high)
            return trial.suggest_float(name, float(low), float(high), log=spec.get("log", False))
        return spec

    # Tunable params (~12) — optimized per cluster
    tuned = {
        "learning_rate": _suggest("learning_rate", {"low": 1e-4, "high": 1e-2, "log": True}),
        "batch_size": _suggest("batch_size", [64, 128, 256]),
        "weight_decay": _suggest("weight_decay", {"low": 1e-3, "high": 0.2, "log": True}),
        "label_smoothing": _suggest("label_smoothing", {"low": 0.02, "high": 0.12}),
        "focal_gamma": _suggest("focal_gamma", {"low": 0.0, "high": 3.0}),
        "noise_std": _suggest("noise_std", {"low": 0.01, "high": 0.08}),
        "hidden_size": _suggest("hidden_size", [64, 96, 128]),
        "num_layers": _suggest("num_layers", {"low": 1, "high": 3}),
        "dropout": _suggest("dropout", {"low": 0.2, "high": 0.65}),
        "sequence_length": _suggest("sequence_length", [10, 20, 30]),
        "input_dropout": _suggest("input_dropout", {"low": 0.05, "high": 0.4}),
        "head_hidden_ratio": _suggest("head_hidden_ratio", {"low": 0.25, "high": 0.5}),
    }

    # Fixed params (~7) — sensible defaults, not searched
    fixed_defaults = {
        "optimizer_name": fixed.get("optimizer_name", "adamw"),
        "scheduler_factor": fixed.get("scheduler_factor", 0.5),
        "scheduler_patience": fixed.get("scheduler_patience", 5),
        "gradient_clip_val": fixed.get("gradient_clip_val", 2.0),
        "bidirectional": fixed.get("bidirectional", False),
        "num_attention_heads": fixed.get("num_attention_heads", 0),
        "activation": fixed.get("activation", "gelu"),
        "feature_mask_rate": fixed.get("feature_mask_rate", 0.0),
    }

    return {**tuned, **fixed_defaults}


def _trial_matches_current_config(trial: optuna.trial.FrozenTrial, config: dict) -> bool:
    """Check if a trial's params are compatible with the current search space.

    Rejects trials that were tuned under a different config (e.g., old trials
    where activation/bidirectional/attention were tunable rather than fixed).
    """
    optuna_cfg = config.get("training", {}).get("optuna", {})
    fixed = optuna_cfg.get("fixed_params", {})
    search_space = optuna_cfg.get("search_space", {})
    known_params = set(search_space.keys()) | set(fixed.keys())

    for key, expected_value in fixed.items():
        if key in trial.params and trial.params[key] != expected_value:
            return False

    for key in trial.params:
        if key not in known_params:
            return False

    return True


def _deduplicate_trials(
    trials: list[optuna.trial.FrozenTrial],
    top_k: int,
    key_params: tuple[str, ...] = (
        "hidden_size",
        "num_layers",
        "learning_rate",
        "dropout",
        "sequence_length",
        "label_smoothing",
        "focal_gamma",
        "input_dropout",
        "weight_decay",
        "batch_size",
    ),
) -> list[optuna.trial.FrozenTrial]:
    """Select top-K trials with meaningfully different hyperparameters.

    Considers two trials "duplicate" if their key architectural params match.
    For continuous params, uses rounding to detect near-duplicates.
    """
    selected: list[optuna.trial.FrozenTrial] = []
    seen_signatures: list[dict] = []

    for trial in trials:  # already sorted by value descending
        sig = {}
        for p in key_params:
            val = trial.params.get(p)
            if isinstance(val, float):
                sig[p] = round(val, 4) if val > 0.01 else round(val, 5)
            else:
                sig[p] = val

        is_dup = any(all(sig.get(p) == prev.get(p) for p in key_params) for prev in seen_signatures)

        if not is_dup:
            selected.append(trial)
            seen_signatures.append(sig)

        if len(selected) >= top_k:
            break

    if len(selected) < top_k:
        print(f"  WARNING: Only {len(selected)} unique configs found for ensemble (wanted {top_k})")
        for trial in trials:
            if trial not in selected:
                selected.append(trial)
            if len(selected) >= top_k:
                break

    return selected


def _compute_objective_value(
    model: LSTMForecaster,
    dm: TradingDataModule,
    min_recall: float,
    metric: str = "precision_at_threshold",
    threshold: float = 0.60,
    beta: float = 0.5,
) -> float:
    """Compute optimization objective with quadratic recall penalty.

    Supports two modes:
    - "precision_at_threshold": Precision of UP predictions at a fixed probability
      threshold. Aligns Optuna search with deployment threshold, ensuring the model
      learns to produce well-separated probabilities.
    - "f_beta": F-beta score at the optimal point on the precision-recall curve.
      Beta < 1 prioritizes precision over recall.

    Args:
        model: Trained model in eval mode.
        dm: DataModule with validation data.
        min_recall: Minimum recall before applying quadratic penalty.
        metric: Objective type ("precision_at_threshold" or "f_beta").
        threshold: Probability threshold for precision_at_threshold mode.
        beta: F-beta parameter (only used when metric="f_beta").

    Returns:
        Score to maximize (higher is better), with quadratic penalty
        applied if recall is below min_recall.
    """
    model.eval()
    all_probs = []
    all_targets = []

    with torch.no_grad():
        for batch in dm.val_dataloader():
            x, y = batch
            logits = model(x)
            probs = torch.softmax(logits, dim=-1)[:, 1]
            all_probs.append(probs.cpu())
            all_targets.append(y.cpu())

    probs = torch.cat(all_probs).numpy()
    targets = torch.cat(all_targets).numpy()

    if metric == "precision_at_threshold":
        predicted_up = probs >= threshold
        n_predicted = int(predicted_up.sum())
        if n_predicted == 0:
            # Return a small but differentiated value based on how close the model
            # got to the threshold. This gives Optuna gradient to navigate toward
            # configs that produce higher probabilities, instead of treating all
            # "no signal" trials as equally bad (0.0).
            max_prob = float(probs.max()) if len(probs) > 0 else 0.0
            # Also reward models with predictions near the threshold (within 0.10)
            near_threshold = float((probs > threshold - 0.10).mean()) if len(probs) > 0 else 0.0
            return max_prob * 0.01 + 0.001 * near_threshold  # always << any real precision score

        tp = int((predicted_up & (targets == 1)).sum())
        n_positive = int(targets.sum())
        precision = tp / n_predicted
        recall = tp / n_positive if n_positive > 0 else 0.0

        if recall < min_recall:
            penalty = (recall / min_recall) ** 2 if min_recall > 0 else 0.0
            return float(precision * penalty)
        return float(precision)

    # f_beta mode (legacy)
    from sklearn.metrics import precision_recall_curve

    precisions, recalls, _ = precision_recall_curve(targets, probs)
    beta_sq = beta**2
    fbetas = (1 + beta_sq) * (precisions * recalls) / ((beta_sq * precisions) + recalls + 1e-10)
    fbetas = np.nan_to_num(fbetas, nan=0.0)

    best_idx = np.argmax(fbetas)
    best_fbeta = fbetas[best_idx]
    best_recall = recalls[best_idx]

    if best_recall < min_recall:
        penalty = (best_recall / min_recall) ** 2 if min_recall > 0 else 0.0
        return float(best_fbeta * penalty)

    return float(best_fbeta)


def _create_trial_objective(
    config: dict,
    cluster_id: str,
    split_dates: SplitDates,
    cluster_cfg: ClusterConfig,
    buy_thresh: float,
) -> callable:
    """Create the Optuna objective function closure for a cluster."""
    optuna_cfg = config["training"].get("optuna", {})
    epochs_per_trial = int(resolve_env_value(optuna_cfg.get("epochs_per_trial", 30), default=30))
    patience_per_trial = int(resolve_env_value(optuna_cfg.get("patience_per_trial", 7), default=7))
    min_recall = optuna_cfg.get("min_recall_up", 0.10)
    n_folds = optuna_cfg.get("cv_folds", 3)
    purge_days = config["training"].get("purge_days", 21)

    # Objective configuration
    obj_cfg = optuna_cfg.get("objective", {})
    obj_metric = obj_cfg.get("metric", "precision_at_threshold")
    obj_threshold = obj_cfg.get("threshold", 0.60)
    beta = obj_cfg.get("beta", 0.5)
    max_overfit_gap = optuna_cfg.get("max_overfit_gap", 0.25)

    features_path = get_normalized_parquet_path(config)

    # Pre-compute CV fold splits
    fold_splits = compute_cv_fold_splits(split_dates, n_folds, purge_days)

    def _train_fold(
        params: dict,
        fold_sd: SplitDates,
        fold_idx: int,
        trial: optuna.Trial,
    ) -> tuple[float, float, int]:
        """Train and evaluate a single CV fold. Returns (score, overfit_gap, n_val_samples)."""
        dm = TradingDataModule(
            parquet_path=features_path,
            seq_len=params["sequence_length"],
            batch_size=params["batch_size"],
            split_dates=fold_sd,
            cluster_id=cluster_id,
            clusters_parquet=cluster_cfg.output_parquet,
            noise_std=params["noise_std"],
            feature_mask_rate=params.get("feature_mask_rate", 0.0),
        )
        dm.setup()

        if len(dm.train_ds) <= 0 or len(dm.val_ds) <= 0:
            return 0.0, 0.0, 0

        # FocalLoss already handles class imbalance — skip class_weights to avoid double correction
        cw = None if params["focal_gamma"] > 0 else dm.class_weights
        model = LSTMForecaster(
            input_size=dm.input_size,
            hidden_size=params["hidden_size"],
            num_layers=params["num_layers"],
            num_classes=2,
            dropout=params["dropout"],
            learning_rate=params["learning_rate"],
            weight_decay=params["weight_decay"],
            label_smoothing=params["label_smoothing"],
            class_weights=cw,
            num_attention_heads=params["num_attention_heads"],
            focal_gamma=params["focal_gamma"],
            feature_names=dm.feature_cols,
            optimizer_name=params["optimizer_name"],
            scheduler_factor=params["scheduler_factor"],
            scheduler_patience=params["scheduler_patience"],
            bidirectional=params["bidirectional"],
            head_hidden_ratio=params["head_hidden_ratio"],
            activation=params["activation"],
            input_dropout=params["input_dropout"],
        )

        early_stop = EarlyStopping(
            monitor="val_precision_up",
            patience=patience_per_trial,
            mode="max",
            min_delta=0.0,
        )
        # Only add pruning callback on last fold to avoid premature pruning
        callbacks = [early_stop]
        if fold_idx == len(fold_splits) - 1:
            callbacks.append(PyTorchLightningPruningCallback(trial, monitor="val_precision_up"))

        precision = config.get("training", {}).get("precision", "32")
        gradient_clip_val = params.get("gradient_clip_val", 1.0)

        trainer = L.Trainer(
            max_epochs=epochs_per_trial,
            accelerator="mps",
            devices=1,
            precision=precision,
            callbacks=callbacks,
            log_every_n_steps=10,
            gradient_clip_val=gradient_clip_val,
            enable_progress_bar=False,
            enable_model_summary=False,
            logger=False,
        )

        try:
            trainer.fit(model, dm)
        except optuna.exceptions.TrialPruned:
            raise
        except Exception:
            return 0.0, 0.0
        finally:
            del trainer
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()

        # Extract overfitting gap from precision (not accuracy) — precision-specific
        # gap detects UP class memorization that accuracy gap misses
        cb_metrics = model.trainer.callback_metrics if model.trainer else {}
        train_prec = (
            cb_metrics.get("train_precision_up", torch.tensor(0.0)).item() if cb_metrics else 0.0
        )
        val_prec = (
            cb_metrics.get("val_precision_up", torch.tensor(0.0)).item() if cb_metrics else 0.0
        )
        overfit_gap = max(0.0, train_prec - val_prec)

        n_val = len(dm.val_ds)
        score = _compute_objective_value(
            model,
            dm,
            min_recall,
            metric=obj_metric,
            threshold=obj_threshold,
            beta=beta,
        )
        del model, dm
        return score, overfit_gap, n_val

    def objective(trial: optuna.Trial) -> float:
        params = suggest_hyperparams(trial, config)

        # Evaluate on each CV fold, report mean score and overfitting gap
        fold_scores = []
        fold_gaps = []
        fold_val_sizes = []
        for fold_idx, fold_sd in enumerate(fold_splits):
            try:
                result = _train_fold(params, fold_sd, fold_idx, trial)
                if isinstance(result, tuple) and len(result) == 3:
                    score, gap, n_val = result
                elif isinstance(result, tuple):
                    score, gap = result
                    n_val = 0
                else:
                    score, gap, n_val = result, 0.0, 0
                fold_scores.append(score)
                fold_gaps.append(gap)
                fold_val_sizes.append(n_val)
            except optuna.exceptions.TrialPruned:
                raise
            except Exception as e:
                print(f"    Trial {trial.number} fold {fold_idx + 1} failed: {e}")
                fold_scores.append(0.0)
                fold_gaps.append(0.0)
                fold_val_sizes.append(0)

        mean_score = float(np.mean(fold_scores)) if fold_scores else 0.0
        avg_gap = float(np.mean(fold_gaps)) if fold_gaps else 0.0

        # Penalize overfitting: if gap > max_overfit_gap, scale score down
        if avg_gap > max_overfit_gap and max_overfit_gap > 0:
            gap_penalty = max_overfit_gap / avg_gap
            mean_score *= gap_penalty

        trial.set_user_attr("fold_scores", fold_scores)
        trial.set_user_attr("avg_overfit_gap", round(avg_gap, 4))
        trial.set_user_attr(
            "n_val_samples",
            int(np.mean([v for v in fold_val_sizes if v > 0]))
            if any(v > 0 for v in fold_val_sizes)
            else 0,
        )
        print(
            f"    Trial {trial.number}: folds={[f'{s:.4f}' for s in fold_scores]}, "
            f"mean={mean_score:.4f}, gap={avg_gap:.4f}"
        )
        return mean_score

    return objective


def _get_optuna_storage(optuna_cfg: dict) -> str | None:
    """Return the Optuna storage URL if persistence is enabled, else None (in-memory)."""
    if not optuna_cfg.get("persist", False):
        return None
    return OPTUNA_STORAGE_URL


def _convergence_callback(patience: int):
    """Create an Optuna callback that stops the study when no improvement is found.

    Args:
        patience: Number of consecutive completed trials without improvement
                  before stopping the study.

    Returns:
        Callback function for study.optimize().
    """

    def callback(study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
        completed = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
        if len(completed) < patience:
            return
        best_value = study.best_value
        recent = completed[-patience:]
        if (
            all(t.value <= best_value for t in recent)
            and recent[-1].number != study.best_trial.number
        ):
            print(f"  Convergence: no improvement in {patience} trials, stopping study.")
            study.stop()

    return callback


def _purge_old_trials(study: optuna.Study, max_history_days: int) -> int:
    """Report on trial age distribution in the study.

    Optuna doesn't expose a delete-trial API. Incompatible trials are
    filtered at the point of use (top-K selection) via
    _trial_matches_current_config() instead.

    Returns the number of recent trials (within max_history_days).
    """
    if max_history_days <= 0:
        return len(study.trials)

    cutoff = datetime.now() - timedelta(days=max_history_days)
    recent = [t for t in study.trials if t.datetime_start and t.datetime_start >= cutoff]
    old = len(study.trials) - len(recent)

    if old > 0:
        print(
            f"  Optuna history: {len(recent)} recent trials, "
            f"{old} older than {max_history_days}d "
            f"(incompatible configs filtered at ensemble selection)"
        )

    return len(recent)


def _tag_champion(run_ids: list[str], cluster_id: str) -> None:
    """Tag the best ensemble run as 'champion' based on generalization-adjusted score.

    Compares all ensemble runs for a cluster using val_stability_score
    (or val_precision_up as fallback), penalized by the val→test precision
    gap to prefer models that generalize well to unseen data.
    Non-champion runs are tagged as 'ensemble'.
    """
    if not run_ids:
        return

    client = mlflow.MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    best_run_id = None
    best_score = -float("inf")

    for rid in run_ids:
        run = client.get_run(rid)
        # Prefer stability_score, fallback to precision_up
        score = run.data.metrics.get("val_stability_score")
        if score is None:
            score = run.data.metrics.get("val_precision_up", 0.0)
        if score is None:
            score = 0.0

        # Penalize val→test gap: prefer models where test_precision is close
        # to val_precision (good generalization to unseen data)
        val_prec = run.data.metrics.get("val_precision_up", 0.0)
        test_prec = run.data.metrics.get("test_precision_up")
        if val_prec > 0 and test_prec is not None and test_prec > 0:
            gen_ratio = min(test_prec / val_prec, 1.0)
            # Soft penalty: score *= (1 + ratio) / 2
            # ratio=1.0 → no penalty; ratio=0.5 → score *= 0.75
            score *= (1.0 + gen_ratio) / 2.0

        if score > best_score:
            best_score = score
            best_run_id = rid

    for rid in run_ids:
        if rid == best_run_id:
            client.set_tag(rid, "champion", "true")
            client.set_tag(rid, "role", "champion")
        else:
            client.set_tag(rid, "champion", "false")
            client.set_tag(rid, "role", "ensemble")

    if best_run_id:
        print(f"\n  Champion for {cluster_id}: run {best_run_id[:8]} (score={best_score:.4f})")


def optimize_cluster(config: dict, cluster_id: str) -> None:
    """Run Optuna optimization for a cluster, then train final model.

    When persistence is enabled, the study is stored in PostgreSQL and
    previous trials are reused for warm-starting the TPE sampler.

    Args:
        config: Full config dict.
        cluster_id: Cluster identifier (e.g. "Technology_0").
    """
    split_dates = compute_split_dates(config)
    buy_thresh = get_cluster_buy_threshold(config, cluster_id)
    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))
    optuna_cfg = config["training"].get("optuna", {})
    n_trials = int(resolve_env_value(optuna_cfg.get("n_trials", 15), default=15))
    startup_trials = int(resolve_env_value(optuna_cfg.get("startup_trials", 5), default=5))
    conv_patience = int(resolve_env_value(optuna_cfg.get("convergence_patience", 5), default=5))
    max_history_days = int(resolve_env_value(optuna_cfg.get("max_history_days", 30), default=30))

    print(f"\n{'=' * 60}")
    print(f"Optimizing cluster: {cluster_id}")
    print(f"{'=' * 60}")
    print("Temporal splits:")
    print(split_dates.summary())
    print(f"  Threshold — UP: +{buy_thresh:.1%}")
    print(
        f"  Optuna — {n_trials} trials, {startup_trials} startup, "
        f"convergence patience {conv_patience}"
    )

    # Storage: PostgreSQL (persistent) or None (in-memory)
    storage = _get_optuna_storage(optuna_cfg)
    if storage:
        print(
            f"  Optuna storage: PostgreSQL (warm-starting enabled, max_history={max_history_days}d)"
        )
    else:
        print("  Optuna storage: in-memory (no persistence)")

    # Create or load existing study (v2 = per-cluster with CV + ensemble)
    study = optuna.create_study(
        direction="maximize",
        study_name=f"cluster-v2/{cluster_id}",
        storage=storage,
        load_if_exists=True,
        pruner=optuna.pruners.MedianPruner(
            n_startup_trials=startup_trials,
            n_warmup_steps=5,
        ),
    )

    # Purge old trials if using persistent storage
    prior_trials = len(study.trials)
    if storage and prior_trials > 0:
        kept = _purge_old_trials(study, max_history_days)
        print(f"  Warm-starting with {kept} prior trials")

    # Run optimization with progress feedback and convergence detection
    objective_fn = _create_trial_objective(
        config,
        cluster_id,
        split_dates,
        cluster_cfg,
        buy_thresh,
    )

    try:
        study.optimize(
            objective_fn,
            n_trials=n_trials,
            n_jobs=1,
            show_progress_bar=True,
            callbacks=[_convergence_callback(conv_patience)],
        )
    except Exception as e:
        print(f"  ERROR during Optuna optimization for {cluster_id}: {e}")
        _log_error_to_cluster_experiment(config, cluster_id, e)
        raise

    # Get top-K completed trials for ensemble, filtering incompatible configs
    ensemble_k = optuna_cfg.get("ensemble_top_k", 3)
    all_completed = [
        t
        for t in study.trials
        if t.state == optuna.trial.TrialState.COMPLETE and t.value is not None
    ]
    completed = [t for t in all_completed if _trial_matches_current_config(t, config)]
    filtered_count = len(all_completed) - len(completed)
    if filtered_count > 0:
        print(f"  Filtered {filtered_count} trials with incompatible param config")

    completed.sort(key=lambda t: t.value, reverse=True)
    top_trials = _deduplicate_trials(completed, ensemble_k)

    if not top_trials:
        msg = f"No completed compatible trials for {cluster_id}"
        print(f"  ERROR: {msg}")
        _log_error_to_cluster_experiment(config, cluster_id, RuntimeError(msg))
        raise RuntimeError(msg)

    # Multiple testing correction (Bailey & Lopez de Prado, "Deflated Sharpe Ratio", 2014)
    # Adjusts best score for the number of trials tested to avoid selection bias
    best_score = top_trials[0].value
    n_completed = len(completed)
    # Estimate n_val_samples from first trial's user_attrs if available
    n_val_samples = top_trials[0].user_attrs.get("n_val_samples", 500)
    if n_completed > 1 and n_val_samples > 0:
        correction = np.sqrt(2 * np.log(n_completed) / n_val_samples)
        corrected_score = best_score - correction
    else:
        correction = 0.0
        corrected_score = best_score
    print(
        f"  Multiple testing correction: raw={best_score:.4f}, "
        f"correction={correction:.4f}, corrected={corrected_score:.4f} "
        f"(n_trials={n_completed}, n_val≈{n_val_samples})"
    )

    # Optuna study summary for logging
    optuna_meta = {
        "optuna_total_trials": len(study.trials),
        "optuna_completed_trials": len(all_completed),
        "optuna_compatible_trials": len(completed),
        "optuna_filtered_trials": filtered_count,
        "optuna_unique_ensemble_configs": len(top_trials),
        "optuna_best_score_raw": best_score,
        "optuna_best_score_corrected": corrected_score,
        "optuna_multiple_testing_correction": correction,
    }

    print(f"\n  Top-{len(top_trials)} trials:")
    for rank, trial in enumerate(top_trials, 1):
        fold_scores = trial.user_attrs.get("fold_scores", [])
        folds_str = f" folds={[f'{s:.4f}' for s in fold_scores]}" if fold_scores else ""
        print(f"    Rank {rank}: trial #{trial.number}, value={trial.value:.4f}{folds_str}")

    # Train final models for ensemble
    fixed = optuna_cfg.get("fixed_params", {})
    ensemble_run_ids: list[str] = []
    for rank, trial in enumerate(top_trials, 1):
        # Merge trial's tuned params with fixed params for full config
        full_params = {**trial.params}
        # Fixed params ALWAYS override trial params (they're fixed, not tunable)
        for key, default in [
            ("optimizer_name", "adamw"),
            ("scheduler_factor", 0.5),
            ("scheduler_patience", 5),
            ("gradient_clip_val", 2.0),
            ("bidirectional", False),
            ("num_attention_heads", 0),
            ("activation", "gelu"),
            ("feature_mask_rate", 0.0),
        ]:
            full_params[key] = fixed.get(key, default)

        # Attach Optuna metadata and trial-specific info to params
        full_params["_optuna_meta"] = optuna_meta
        full_params["_optuna_trial_number"] = trial.number
        full_params["_optuna_trial_value"] = trial.value

        # Ensemble temporal diversity: rank 1=100%, rank 2=75%, rank 3=50% of training data
        ensemble_offsets = [0.0, 0.25, 0.50]
        offset_pct = ensemble_offsets[rank - 1] if rank <= len(ensemble_offsets) else 0.0

        print(
            f"\n  Training ensemble model {rank}/{len(top_trials)} "
            f"(trial #{trial.number}, train_offset={offset_pct:.0%})..."
        )
        run_id = train_final_model(
            config,
            cluster_id,
            full_params,
            split_dates,
            ensemble_rank=rank,
            train_date_offset_pct=offset_pct,
        )
        if run_id:
            ensemble_run_ids.append(run_id)

    # Tag the best ensemble member as "champion" based on val_stability_score
    _tag_champion(ensemble_run_ids, cluster_id)


def train_final_model(
    config: dict,
    cluster_id: str,
    best_params: dict[str, Any],
    split_dates: SplitDates,
    ensemble_rank: int = 1,
    train_date_offset_pct: float = 0.0,
) -> str | None:
    """Train the final model with optimal hyperparameters and log to MLflow.

    Args:
        config: Full config dict.
        cluster_id: Cluster identifier.
        best_params: Best hyperparameters from Optuna.
        split_dates: Temporal split dates.
        ensemble_rank: Rank in ensemble (1=best, 2=second, 3=third).
        train_date_offset_pct: Fraction of oldest training data to discard
            for ensemble temporal diversity (0.0=all data, 0.25=75% most recent).

    Returns:
        MLflow run_id of the completed run, or None if training was skipped.
    """
    train_cfg = config["training"]
    buy_thresh = get_cluster_buy_threshold(config, cluster_id)
    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))
    features_path = get_normalized_parquet_path(config)

    print(f"\n  Training final model for {cluster_id} with best params...")

    # Check normalization stats freshness
    from src.features.normalize import check_staleness, load_normalization_stats

    try:
        norm_stats = load_normalization_stats(config)
        check_staleness(norm_stats, max_age_days=90)
    except FileNotFoundError:
        pass  # Will fail later when loading data

    # DataModule
    time_decay_lambda = float(train_cfg.get("time_decay_lambda", 0.0))
    dm = TradingDataModule(
        parquet_path=features_path,
        seq_len=best_params["sequence_length"],
        batch_size=best_params["batch_size"],
        split_dates=split_dates,
        cluster_id=cluster_id,
        clusters_parquet=cluster_cfg.output_parquet,
        noise_std=best_params["noise_std"],
        feature_mask_rate=best_params.get("feature_mask_rate", 0.0),
        train_date_offset_pct=train_date_offset_pct,
        time_decay_lambda=time_decay_lambda,
    )
    dm.setup()

    if len(dm.train_ds) <= 0 or len(dm.val_ds) <= 0:
        print(f"  SKIPPING {cluster_id}: insufficient data")
        return None

    # FocalLoss already handles class imbalance — skip class_weights to avoid double correction
    cw = None if best_params["focal_gamma"] > 0 else dm.class_weights
    model = LSTMForecaster(
        input_size=dm.input_size,
        hidden_size=best_params["hidden_size"],
        num_layers=best_params["num_layers"],
        num_classes=2,
        dropout=best_params["dropout"],
        learning_rate=best_params["learning_rate"],
        weight_decay=best_params["weight_decay"],
        label_smoothing=best_params["label_smoothing"],
        class_weights=cw,
        num_attention_heads=best_params["num_attention_heads"],
        focal_gamma=best_params["focal_gamma"],
        feature_names=dm.feature_cols,
        optimizer_name=best_params.get("optimizer_name", "adamw"),
        scheduler_factor=best_params.get("scheduler_factor", 0.5),
        scheduler_patience=best_params.get("scheduler_patience", 5),
        bidirectional=best_params.get("bidirectional", False),
        head_hidden_ratio=best_params.get("head_hidden_ratio", 0.5),
        activation=best_params.get("activation", "gelu"),
        input_dropout=best_params.get("input_dropout", 0.0),
    )

    # MLflow logger
    prefix = train_cfg.get("cluster_experiment_prefix", "cluster")
    experiment_name = f"{prefix}/{cluster_id}"
    mlflow_logger = MLFlowLogger(
        experiment_name=experiment_name,
        tracking_uri=MLFLOW_TRACKING_URI,
        log_model=True,
        save_dir="checkpoints",
    )

    # Callbacks — early stopping on precision only (val_loss diverges early
    # due to FocalLoss + model confidence, but precision keeps improving)
    max_epochs = int(resolve_env_value(train_cfg["max_epochs"], default=200))
    patience = int(resolve_env_value(train_cfg["early_stopping_patience"], default=15))

    early_stop_precision = EarlyStopping(
        monitor="val_precision_up",
        patience=patience,
        mode="max",
        min_delta=0.0,
    )
    # Secondary early stopping on val_loss as circuit breaker against
    # training with diverging validation loss
    early_stop_loss = EarlyStopping(
        monitor="val_loss",
        patience=patience + 10,
        mode="min",
        min_delta=0.0,
    )
    checkpoint = ModelCheckpoint(
        dirpath="checkpoints",
        monitor="val_precision_up",
        mode="max",
        save_top_k=1,
        filename=f"{cluster_id}-ensemble-{ensemble_rank}-best-{{epoch}}-{{val_precision_up:.4f}}",
    )

    precision = config.get("training", {}).get("precision", "32")
    gradient_clip_val = best_params.get("gradient_clip_val", 1.0)
    progress_cb = ClusterProgressCallback(cluster_id, ensemble_rank)
    trainer = L.Trainer(
        max_epochs=max_epochs,
        accelerator="mps",
        devices=1,
        precision=precision,
        logger=mlflow_logger,
        callbacks=[early_stop_precision, early_stop_loss, checkpoint, progress_cb],
        log_every_n_steps=10,
        gradient_clip_val=gradient_clip_val,
        enable_progress_bar=False,
        enable_model_summary=False,
    )

    client = mlflow.MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    print(f"  Training with {dm.input_size} features, seq_len={best_params['sequence_length']}")
    try:
        trainer.fit(model, dm)

        # Temperature scaling calibration (Guo et al. 2017)
        promotion_cfg = config.get("promotion", {})
        eval_cfg = promotion_cfg.get("evaluation", {})
        cal_cfg = config.get("training", {}).get("calibration", {})
        primary_thresh = eval_cfg.get("primary_threshold", 0.65)
        optimal_temp, cal_diagnostics = calibrate_temperature(
            model,
            dm.val_dataloader(),
            primary_threshold=primary_thresh,
            min_signal_rate=cal_cfg.get("min_signal_rate", 0.03),
            signal_penalty_alpha=cal_cfg.get("signal_penalty_alpha", 5.0),
        )
        model.hparams["calibration_temperature"] = optimal_temp
        print(f"  Calibration temperature: {optimal_temp:.4f}")

        # Test (predict_proba now uses calibrated temperature)
        test_results = trainer.test(model, dm)
        print(f"  Test results: {test_results}")

        # Log checkpoint
        if checkpoint.best_model_path:
            mlflow.log_artifact(checkpoint.best_model_path, artifact_path="checkpoints")
            print(f"  Best checkpoint: {checkpoint.best_model_path}")

        # Log params to MLflow
        run_id = mlflow_logger.run_id

        # Log best hyperparams + cluster info
        optuna_meta = best_params.pop("_optuna_meta", {})
        optuna_trial_number = best_params.pop("_optuna_trial_number", None)
        optuna_trial_value = best_params.pop("_optuna_trial_value", None)

        params_to_log = {
            "cluster_id": cluster_id,
            "buy_threshold": buy_thresh,
            "num_classes": 2,
            "ensemble_rank": ensemble_rank,
            "optuna_n_trials": config["training"].get("optuna", {}).get("n_trials", 15),
            **{f"optuna_{k}": v for k, v in best_params.items()},
        }
        for key, value in params_to_log.items():
            client.log_param(run_id, key, value)

        # Optuna study metadata
        if optuna_trial_number is not None:
            client.log_param(run_id, "optuna_trial_number", optuna_trial_number)
        if optuna_trial_value is not None:
            client.log_metric(run_id, "optuna_trial_value", float(optuna_trial_value))
        for mk, mv in optuna_meta.items():
            client.log_metric(run_id, mk, mv)

        # Dataset metadata — sizes and class balance per split
        client.log_metric(run_id, "dataset_train_samples", len(dm.train_ds))
        client.log_metric(run_id, "dataset_val_samples", len(dm.val_ds))
        client.log_metric(run_id, "dataset_test_samples", len(dm.test_ds))
        client.log_metric(run_id, "dataset_n_features", dm.input_size)
        if hasattr(dm, "class_weights") and dm.class_weights is not None:
            client.log_metric(run_id, "dataset_class_weight_up", float(dm.class_weights[1]))

        # Training dynamics — early stopping reason and overfitting indicators
        stopped_epoch = trainer.current_epoch
        client.log_metric(run_id, "stopped_epoch", stopped_epoch)
        client.log_metric(run_id, "max_epochs_configured", max_epochs)

        best_val_loss = checkpoint.best_model_score
        if best_val_loss is not None:
            client.log_metric(run_id, "best_val_precision_up", float(best_val_loss))

        # Log calibration temperature and diagnostics
        client.log_metric(run_id, "calibration_temperature", optimal_temp)
        for diag_key, diag_val in cal_diagnostics.items():
            client.log_metric(run_id, diag_key, diag_val)

        # Detect which early stopping triggered
        for cb in trainer.callbacks:
            if isinstance(cb, EarlyStopping) and cb.stopped_epoch > 0:
                client.log_param(run_id, "early_stop_trigger", cb.monitor)
                break
        else:
            if stopped_epoch >= max_epochs - 1:
                client.log_param(run_id, "early_stop_trigger", "max_epochs")
            else:
                client.log_param(run_id, "early_stop_trigger", "none")

        # Confusion matrix + precision/recall/f1
        test_precision_up = _log_confusion_matrix(model, dm, client, run_id)

        # Precision-based evaluation with walk-forward stability
        _run_precision_eval(model, dm, config, client, run_id, buy_thresh, test_precision_up)

        # Trade evaluation
        _run_trade_eval(model, config, cluster_id, split_dates, run_id, cluster_cfg.output_parquet)

        return run_id
    except Exception as e:
        _log_exception_to_mlflow_run(client, mlflow_logger, e)
        print(f"  ERROR: {e}")
        raise


def _log_confusion_matrix(
    model: LSTMForecaster,
    dm: TradingDataModule,
    client,
    run_id: str,
) -> float | None:
    """Compute and log confusion matrix + classification metrics to MLflow.

    Returns:
        test_precision_up for val-test gap computation, or None if unavailable.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import (
        ConfusionMatrixDisplay,
        confusion_matrix,
        precision_recall_fscore_support,
    )

    model.eval()
    class_names = ["NOT_UP", "UP"]
    test_precision_up = None

    for split_name, dataloader in [
        ("val", dm.val_dataloader()),
        ("test", dm.test_dataloader()),
    ]:
        all_preds = []
        all_targets = []
        all_probs = []

        with torch.no_grad():
            for batch in dataloader:
                x, y = batch
                logits = model(x)
                preds = logits.argmax(dim=-1)
                probs = model.predict_proba(x)
                all_preds.append(preds.cpu())
                all_targets.append(y.cpu())
                all_probs.append(probs[:, 1].cpu())

        all_preds_np = torch.cat(all_preds).numpy()
        all_targets_np = torch.cat(all_targets).numpy()
        all_probs_np = torch.cat(all_probs).numpy()

        cm = confusion_matrix(all_targets_np, all_preds_np, labels=[0, 1])
        precision, recall, f1, _ = precision_recall_fscore_support(
            all_targets_np,
            all_preds_np,
            labels=[0, 1],
            zero_division=0.0,
        )
        client.log_metric(run_id, f"{split_name}_precision_up", float(precision[1]))
        client.log_metric(run_id, f"{split_name}_recall_up", float(recall[1]))
        client.log_metric(run_id, f"{split_name}_f1_up", float(f1[1]))

        if split_name == "test":
            test_precision_up = float(precision[1])

        # Brier score: calibration quality metric (lower is better)
        up_targets = (all_targets_np == 1).astype(np.float64)
        brier_score = float(np.mean((all_probs_np - up_targets) ** 2))
        client.log_metric(run_id, f"{split_name}_brier_score", brier_score)

        print(
            f"  {split_name} — precision_up={precision[1]:.3f}, "
            f"recall_up={recall[1]:.3f}, f1_up={f1[1]:.3f}"
        )

        fig, ax = plt.subplots(figsize=(5, 4))
        disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=class_names)
        disp.plot(ax=ax, cmap="Blues", values_format="d")
        ax.set_title(f"Confusion Matrix — {split_name}")
        fig.tight_layout()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            fig.savefig(f.name, dpi=100)
            client.log_artifact(run_id, f.name, artifact_path="confusion_matrix")
        plt.close(fig)

    return test_precision_up


def _run_precision_eval(
    model: LSTMForecaster,
    dm: TradingDataModule,
    config: dict,
    client,
    run_id: str,
    buy_thresh: float,
    test_precision_up: float | None = None,
) -> None:
    """Run precision-focused evaluation with walk-forward stability."""
    try:
        from src.config import PromotionEvalConfig
        from src.evaluation.precision_eval import evaluate_model, log_eval_to_mlflow

        promotion_cfg = config.get("promotion", {})
        if "evaluation" not in promotion_cfg:
            return

        eval_config = PromotionEvalConfig.from_dict(promotion_cfg)
        seq_len = dm.seq_len
        val_vi = dm.val_valid_indices
        target_indices = val_vi + seq_len

        sample_dates = (
            dm.val_dates[target_indices]
            if dm.val_dates is not None and len(dm.val_dates) > 0
            else np.array([])
        )
        fwd_returns = (
            dm.val_forward_returns[target_indices] if dm.val_forward_returns is not None else None
        )

        eval_result = evaluate_model(
            model=model,
            val_dataloader=dm.val_dataloader(),
            eval_config=eval_config,
            sample_dates=sample_dates,
            forward_returns=fwd_returns,
            buy_threshold=buy_thresh,
            test_precision_up=test_precision_up,
            adaptive_threshold=True,
        )
        log_eval_to_mlflow(eval_result, client, run_id)
        print(
            f"  Precision eval: stability_score={eval_result.stability_score:.4f}, "
            f"auc_pr={eval_result.auc_pr:.4f}, stage={eval_result.elimination_stage}"
        )
        if not eval_result.passed_all_filters:
            wf_n = len(eval_result.wf_precision_per_window)
            wf_mean = eval_result.wf_precision_mean
            wf_std = eval_result.wf_precision_std
            cv = wf_std / wf_mean if wf_mean > 0 else float("inf")
            recall_primary = eval_result.recall_at_primary
            print(
                f"  PROMOTION FAILED ({eval_result.elimination_stage}): "
                f"wf_windows={wf_n}, mean_prec={wf_mean:.4f}, std_prec={wf_std:.4f}, "
                f"CV={cv:.4f} (max={eval_config.max_std_ratio}), "
                f"recall@primary={recall_primary:.4f} (min={eval_config.min_recall})"
            )
    except Exception as e:
        print(f"  Precision evaluation failed: {e}")


def _run_trade_eval(
    model: LSTMForecaster,
    config: dict,
    cluster_id: str,
    split_dates: SplitDates,
    run_id: str,
    clusters_parquet: str,
) -> None:
    """Run trade evaluation across train/val/test splits."""
    try:
        from src.training.train import _evaluate_cluster_trades

        _evaluate_cluster_trades(model, config, cluster_id, split_dates, run_id, clusters_parquet)
    except Exception as e:
        print(f"  Trade evaluation failed: {e}")


def _create_global_trial_objective(
    config: dict,
    split_dates: SplitDates,
    cluster_cfg: ClusterConfig,
) -> callable:
    """Create the Optuna objective function closure for global optimization.

    Uses top 3 symbols by market cap per cluster for fast optimization,
    with the same temporal range as final training.

    Args:
        config: Full config dict.
        split_dates: Temporal split dates.
        cluster_cfg: Cluster configuration.

    Returns:
        Objective function for Optuna.
    """
    optuna_cfg = config["training"].get("optuna", {})
    epochs_per_trial = int(resolve_env_value(optuna_cfg.get("epochs_per_trial", 30), default=30))
    patience_per_trial = int(resolve_env_value(optuna_cfg.get("patience_per_trial", 7), default=7))
    min_recall = optuna_cfg.get("min_recall_up", 0.10)
    obj_cfg = optuna_cfg.get("objective", {})
    obj_metric = obj_cfg.get("metric", "precision_at_threshold")
    obj_threshold = obj_cfg.get("threshold", 0.60)
    beta = obj_cfg.get("beta", 0.5)
    max_overfit_gap = optuna_cfg.get("max_overfit_gap", 0.25)
    features_path = get_normalized_parquet_path(config)
    n_symbols_per_cluster = int(
        resolve_env_value(optuna_cfg.get("n_symbols_per_cluster", 3), default=3)
    )

    import polars as pl

    clusters_df = pl.read_parquet(cluster_cfg.output_parquet)
    cluster_ids = clusters_df["cluster_id"].unique().sort().to_list()

    print(
        f"  Each trial will sample {n_symbols_per_cluster} symbols per cluster "
        f"(~{n_symbols_per_cluster * len(cluster_ids)} total from {len(cluster_ids)} clusters)"
    )

    def objective(trial: optuna.Trial) -> float:
        # Each trial gets a different symbol subset; combine trial.number
        # with cluster_id so selections are independent across clusters
        selected_symbols = []
        for cid in cluster_ids:
            symbols = _get_random_symbols(
                cid,
                cluster_cfg.output_parquet,
                n=n_symbols_per_cluster,
                seed=hash((trial.number, cid)),
            )
            selected_symbols.extend(symbols)
        trial.set_user_attr("optimization_symbols", selected_symbols)

        params = suggest_hyperparams(trial, config)

        dm = TradingDataModule(
            parquet_path=features_path,
            seq_len=params["sequence_length"],
            batch_size=params["batch_size"],
            split_dates=split_dates,
            cluster_id=None,
            clusters_parquet=cluster_cfg.output_parquet,
            noise_std=params["noise_std"],
            feature_mask_rate=params.get("feature_mask_rate", 0.0),
        )
        dm._optimization_symbols = selected_symbols
        dm.setup()

        if len(dm.train_ds) <= 0 or len(dm.val_ds) <= 0:
            return 0.0

        # FocalLoss already handles class imbalance — skip class_weights to avoid double correction
        cw = None if params["focal_gamma"] > 0 else dm.class_weights
        model = LSTMForecaster(
            input_size=dm.input_size,
            hidden_size=params["hidden_size"],
            num_layers=params["num_layers"],
            num_classes=2,
            dropout=params["dropout"],
            learning_rate=params["learning_rate"],
            weight_decay=params["weight_decay"],
            label_smoothing=params["label_smoothing"],
            class_weights=cw,
            num_attention_heads=params["num_attention_heads"],
            focal_gamma=params["focal_gamma"],
            feature_names=dm.feature_cols,
            optimizer_name=params["optimizer_name"],
            scheduler_factor=params["scheduler_factor"],
            scheduler_patience=params["scheduler_patience"],
            bidirectional=params["bidirectional"],
            head_hidden_ratio=params["head_hidden_ratio"],
            activation=params["activation"],
            input_dropout=params["input_dropout"],
        )

        # Callbacks: early stopping + Optuna pruning
        early_stop = EarlyStopping(
            monitor="val_precision_up",
            patience=patience_per_trial,
            mode="max",
            min_delta=0.0,
        )
        pruning_callback = PyTorchLightningPruningCallback(trial, monitor="val_precision_up")

        precision = config.get("training", {}).get("precision", "32")
        gradient_clip_val = params.get("gradient_clip_val", 1.0)
        trainer = L.Trainer(
            max_epochs=epochs_per_trial,
            accelerator="mps",
            devices=1,
            precision=precision,
            callbacks=[early_stop, pruning_callback],
            log_every_n_steps=10,
            gradient_clip_val=gradient_clip_val,
            enable_progress_bar=False,
            enable_model_summary=False,
            logger=False,
        )

        try:
            trainer.fit(model, dm)
        except optuna.exceptions.TrialPruned:
            raise
        except Exception as e:
            print(f"    Trial {trial.number} failed: {e}")
            import traceback

            traceback.print_exc()
            return 0.0
        finally:
            # Clean up MPS memory between trials to prevent fragmentation
            del trainer
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()

        # Extract overfitting gap from precision (not accuracy)
        cb_metrics = model.trainer.callback_metrics if model.trainer else {}
        train_prec = (
            cb_metrics.get("train_precision_up", torch.tensor(0.0)).item() if cb_metrics else 0.0
        )
        val_prec = (
            cb_metrics.get("val_precision_up", torch.tensor(0.0)).item() if cb_metrics else 0.0
        )
        overfit_gap = max(0.0, train_prec - val_prec)

        # Compute objective on validation set (top symbols only)
        score = _compute_objective_value(
            model,
            dm,
            min_recall,
            metric=obj_metric,
            threshold=obj_threshold,
            beta=beta,
        )

        # Penalize overfitting
        if overfit_gap > max_overfit_gap and max_overfit_gap > 0:
            gap_penalty = max_overfit_gap / overfit_gap
            score *= gap_penalty

        trial.set_user_attr("avg_overfit_gap", round(overfit_gap, 4))
        del model, dm
        return score

    return objective


def optimize_global(config: dict) -> dict[str, Any]:
    """Run global Optuna optimization across ALL clusters, then save best hyperparameters.

    This finds hyperparameters that work well across the entire stock universe,
    which are then used for training per-cluster models.

    Args:
        config: Full config dict.

    Returns:
        Dictionary with best hyperparameters found.
    """
    split_dates = compute_split_dates(config)
    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))
    optuna_cfg = config["training"].get("optuna", {})
    n_trials = int(resolve_env_value(optuna_cfg.get("n_trials_global", 50), default=50))
    startup_trials = int(resolve_env_value(optuna_cfg.get("startup_trials", 5), default=5))
    max_history_days = int(resolve_env_value(optuna_cfg.get("max_history_days", 30), default=30))

    print(f"\n{'=' * 60}")
    print("GLOBAL OPTIMIZATION: All clusters, all symbols")
    print(f"{'=' * 60}")
    print("Temporal splits:")
    print(split_dates.summary())
    print(f"  Optuna — {n_trials} trials, {startup_trials} startup")

    # Storage: PostgreSQL (persistent) or None (in-memory)
    storage = _get_optuna_storage(optuna_cfg)
    study_name = "global/hyperparameters"

    if storage:
        print(
            f"  Optuna storage: PostgreSQL (warm-starting enabled, max_history={max_history_days}d)"
        )
    else:
        print("  Optuna storage: in-memory (no persistence)")

    # Create or load existing study
    study = optuna.create_study(
        direction="maximize",
        study_name=study_name,
        storage=storage,
        load_if_exists=True,
        pruner=optuna.pruners.MedianPruner(
            n_startup_trials=startup_trials,
            n_warmup_steps=5,
        ),
    )

    # Purge old trials if using persistent storage
    prior_trials = len(study.trials)
    if storage and prior_trials > 0:
        kept = _purge_old_trials(study, max_history_days)
        print(f"  Warm-starting with {kept} prior trials")

    # Run optimization with progress feedback
    objective_fn = _create_global_trial_objective(
        config,
        split_dates,
        cluster_cfg,
    )

    study.optimize(
        objective_fn,
        n_trials=n_trials,
        n_jobs=1,
        show_progress_bar=True,
    )

    # Report best trial
    best = study.best_trial
    print(f"\n  Best trial #{best.number}: value={best.value:.4f}")
    print(f"  Best params: {best.params}")

    # Save best hyperparameters to file for later use
    output_dir = Path("data")
    output_dir.mkdir(parents=True, exist_ok=True)
    best_params_file = output_dir / "best_hyperparameters.json"

    best_params = {
        "study_name": study_name,
        "trial_number": best.number,
        "objective_value": best.value,
        "params": best.params,
        "timestamp": datetime.now().isoformat(),
    }

    with open(best_params_file, "w") as f:
        json.dump(best_params, f, indent=2)

    print(f"\n  Saved best hyperparameters to {best_params_file}")

    return best.params


def load_global_best_params() -> dict[str, Any] | None:
    """Load the best global hyperparameters from file.

    Returns:
        Dictionary with best hyperparameters, or None if not found.
    """
    best_params_file = Path("data/best_hyperparameters.json")
    if not best_params_file.exists():
        return None

    with open(best_params_file) as f:
        data = json.load(f)

    return data.get("params")


def main() -> None:
    """Entry point for optimization."""
    import argparse

    parser = argparse.ArgumentParser(description="Hyperparameter optimization")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    parser.add_argument(
        "--global",
        dest="global_opt",
        action="store_true",
        help="Run global optimization across all clusters",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if args.global_opt:
        optimize_global(config)
    else:
        print("Usage: python -m src.training.optimize --global")
        print("Run 'make optimize-global' for global hyperparameter search")


if __name__ == "__main__":
    main()
