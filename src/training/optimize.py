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
import tempfile
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import lightning as L
import mlflow
import numpy as np
import optuna
import torch
from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint
from lightning.pytorch.loggers import MLFlowLogger
from optuna.integration import PyTorchLightningPruningCallback

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
import logging
import warnings

from src.db import get_engine
from src.keys import MLFLOW_TRACKING_URI, OPTUNA_STORAGE_URL
from src.models.base_model import LSTMForecaster
from src.models.dataset import TradingDataModule

# Suppress noisy Lightning warnings and tips
warnings.filterwarnings("ignore", message=".*num_workers.*bottleneck.*")
logging.getLogger("lightning.pytorch.trainer.connectors.logger_connector").setLevel(logging.WARNING)
logging.getLogger("lightning.pytorch.trainer.connectors.callback_connector").setLevel(logging.WARNING)


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
    cluster_symbols = clusters_df.filter(pl.col("cluster_id") == cluster_id)[
        "symbol"
    ].to_list()

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

    # Tunable params (~10) — optimized per cluster
    tuned = {
        "learning_rate": _suggest("learning_rate", {"low": 1e-4, "high": 1e-2, "log": True}),
        "batch_size": _suggest("batch_size", [64, 128, 256]),
        "weight_decay": _suggest("weight_decay", {"low": 1e-4, "high": 0.1, "log": True}),
        "label_smoothing": _suggest("label_smoothing", {"low": 0.0, "high": 0.15}),
        "focal_gamma": _suggest("focal_gamma", {"low": 0.0, "high": 5.0}),
        "hidden_size": _suggest("hidden_size", [64, 96, 128, 256]),
        "num_layers": _suggest("num_layers", {"low": 1, "high": 4}),
        "dropout": _suggest("dropout", {"low": 0.1, "high": 0.5}),
        "sequence_length": _suggest("sequence_length", [10, 20, 30]),
        "input_dropout": _suggest("input_dropout", {"low": 0.0, "high": 0.3}),
    }

    # Fixed params (~9) — sensible defaults, not searched
    fixed_defaults = {
        "optimizer_name": fixed.get("optimizer_name", "adamw"),
        "scheduler_factor": fixed.get("scheduler_factor", 0.5),
        "scheduler_patience": fixed.get("scheduler_patience", 5),
        "gradient_clip_val": fixed.get("gradient_clip_val", 2.0),
        "bidirectional": fixed.get("bidirectional", False),
        "num_attention_heads": fixed.get("num_attention_heads", 0),
        "head_hidden_ratio": fixed.get("head_hidden_ratio", 0.5),
        "activation": fixed.get("activation", "gelu"),
        "noise_std": fixed.get("noise_std", 0.02),
    }

    return {**tuned, **fixed_defaults}


def _trial_matches_current_config(
    trial: optuna.trial.FrozenTrial, config: dict
) -> bool:
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
        "hidden_size", "num_layers", "learning_rate", "dropout", "sequence_length",
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

        is_dup = any(
            all(sig.get(p) == prev.get(p) for p in key_params)
            for prev in seen_signatures
        )

        if not is_dup:
            selected.append(trial)
            seen_signatures.append(sig)

        if len(selected) >= top_k:
            break

    if len(selected) < top_k:
        print(
            f"  WARNING: Only {len(selected)} unique configs found "
            f"for ensemble (wanted {top_k})"
        )
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
            return 0.0

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
    fbetas = (
        (1 + beta_sq)
        * (precisions * recalls)
        / ((beta_sq * precisions) + recalls + 1e-10)
    )
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

    features_path = get_normalized_parquet_path(config)

    # Pre-compute CV fold splits
    fold_splits = compute_cv_fold_splits(split_dates, n_folds, purge_days)

    def _train_fold(
        params: dict, fold_sd: SplitDates, fold_idx: int, trial: optuna.Trial,
    ) -> float:
        """Train and evaluate a single CV fold. Returns F-beta score."""
        dm = TradingDataModule(
            parquet_path=features_path,
            seq_len=params["sequence_length"],
            batch_size=params["batch_size"],
            split_dates=fold_sd,
            cluster_id=cluster_id,
            clusters_parquet=cluster_cfg.output_parquet,
            noise_std=params["noise_std"],
        )
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

        early_stop = EarlyStopping(
            monitor="val_loss", patience=patience_per_trial, mode="min",
        )
        # Only add pruning callback on last fold to avoid premature pruning
        callbacks = [early_stop]
        if fold_idx == len(fold_splits) - 1:
            callbacks.append(PyTorchLightningPruningCallback(trial, monitor="val_loss"))

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
            return 0.0
        finally:
            del trainer
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()

        score = _compute_objective_value(
            model, dm, min_recall,
            metric=obj_metric, threshold=obj_threshold, beta=beta,
        )
        del model, dm
        return score

    def objective(trial: optuna.Trial) -> float:
        params = suggest_hyperparams(trial, config)

        # Evaluate on each CV fold, report mean F-beta
        fold_scores = []
        for fold_idx, fold_sd in enumerate(fold_splits):
            try:
                score = _train_fold(params, fold_sd, fold_idx, trial)
                fold_scores.append(score)
            except optuna.exceptions.TrialPruned:
                raise
            except Exception as e:
                print(f"    Trial {trial.number} fold {fold_idx+1} failed: {e}")
                fold_scores.append(0.0)

        mean_score = float(np.mean(fold_scores)) if fold_scores else 0.0
        trial.set_user_attr("fold_scores", fold_scores)
        print(f"    Trial {trial.number}: folds={[f'{s:.4f}' for s in fold_scores]}, mean={mean_score:.4f}")
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
        completed = [
            t for t in study.trials
            if t.state == optuna.trial.TrialState.COMPLETE
        ]
        if len(completed) < patience:
            return
        best_value = study.best_value
        recent = completed[-patience:]
        if all(t.value <= best_value for t in recent) and recent[-1].number != study.best_trial.number:
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
    """Tag the best ensemble run as 'champion' based on val_stability_score.

    Compares all ensemble runs for a cluster and sets the 'champion' tag
    on the one with the highest val_stability_score (or val_precision_up
    as fallback). Non-champion runs are tagged as 'ensemble'.
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
        if score is not None and score > best_score:
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
    max_history_days = int(
        resolve_env_value(optuna_cfg.get("max_history_days", 30), default=30)
    )

    print(f"\n{'='*60}")
    print(f"Optimizing cluster: {cluster_id}")
    print(f"{'='*60}")
    print("Temporal splits:")
    print(split_dates.summary())
    print(f"  Threshold — UP: +{buy_thresh:.1%}")
    print(f"  Optuna — {n_trials} trials, {startup_trials} startup, convergence patience {conv_patience}")

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

    study.optimize(
        objective_fn,
        n_trials=n_trials,
        n_jobs=1,
        show_progress_bar=True,
        callbacks=[_convergence_callback(conv_patience)],
    )

    # Get top-K completed trials for ensemble, filtering incompatible configs
    ensemble_k = optuna_cfg.get("ensemble_top_k", 3)
    all_completed = [
        t for t in study.trials
        if t.state == optuna.trial.TrialState.COMPLETE and t.value is not None
    ]
    completed = [
        t for t in all_completed
        if _trial_matches_current_config(t, config)
    ]
    filtered_count = len(all_completed) - len(completed)
    if filtered_count > 0:
        print(f"  Filtered {filtered_count} trials with incompatible param config")

    completed.sort(key=lambda t: t.value, reverse=True)
    top_trials = _deduplicate_trials(completed, ensemble_k)

    # Optuna study summary for logging
    optuna_meta = {
        "optuna_total_trials": len(study.trials),
        "optuna_completed_trials": len(all_completed),
        "optuna_compatible_trials": len(completed),
        "optuna_filtered_trials": filtered_count,
        "optuna_unique_ensemble_configs": len(top_trials),
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
            ("optimizer_name", "adamw"), ("scheduler_factor", 0.5),
            ("scheduler_patience", 5), ("gradient_clip_val", 2.0),
            ("bidirectional", False), ("num_attention_heads", 0),
            ("head_hidden_ratio", 0.5), ("activation", "gelu"),
            ("noise_std", 0.02),
        ]:
            full_params[key] = fixed.get(key, default)

        # Attach Optuna metadata and trial-specific info to params
        full_params["_optuna_meta"] = optuna_meta
        full_params["_optuna_trial_number"] = trial.number
        full_params["_optuna_trial_value"] = trial.value

        print(f"\n  Training ensemble model {rank}/{len(top_trials)} (trial #{trial.number})...")
        run_id = train_final_model(config, cluster_id, full_params, split_dates, ensemble_rank=rank)
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
) -> str | None:
    """Train the final model with optimal hyperparameters and log to MLflow.

    Args:
        config: Full config dict.
        cluster_id: Cluster identifier.
        best_params: Best hyperparameters from Optuna.
        split_dates: Temporal split dates.
        ensemble_rank: Rank in ensemble (1=best, 2=second, 3=third).

    Returns:
        MLflow run_id of the completed run, or None if training was skipped.
    """
    train_cfg = config["training"]
    buy_thresh = get_cluster_buy_threshold(config, cluster_id)
    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))
    features_path = get_normalized_parquet_path(config)

    print(f"\n  Training final model for {cluster_id} with best params...")

    # DataModule
    dm = TradingDataModule(
        parquet_path=features_path,
        seq_len=best_params["sequence_length"],
        batch_size=best_params["batch_size"],
        split_dates=split_dates,
        cluster_id=cluster_id,
        clusters_parquet=cluster_cfg.output_parquet,
        noise_std=best_params["noise_std"],
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

    # Callbacks — full training with proper patience
    max_epochs = int(resolve_env_value(train_cfg["max_epochs"], default=200))
    patience = int(resolve_env_value(train_cfg["early_stopping_patience"], default=15))

    early_stop_precision = EarlyStopping(
        monitor="val_precision_up",
        patience=patience,
        mode="max",
    )
    early_stop_loss = EarlyStopping(
        monitor="val_loss",
        patience=patience,
        mode="min",
        min_delta=0.005,
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
    trainer = L.Trainer(
        max_epochs=max_epochs,
        accelerator="mps",
        devices=1,
        precision=precision,
        logger=mlflow_logger,
        callbacks=[early_stop_precision, early_stop_loss, checkpoint],
        log_every_n_steps=10,
        gradient_clip_val=gradient_clip_val,
    )

    client = mlflow.MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    print(
        f"  Training with {dm.input_size} features, seq_len={best_params['sequence_length']}"
    )
    try:
        trainer.fit(model, dm)

        # Test
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
        _log_confusion_matrix(model, dm, client, run_id)

        # Precision-based evaluation with walk-forward stability
        _run_precision_eval(model, dm, config, client, run_id, buy_thresh)

        # Trade evaluation
        _run_trade_eval(
            model, config, cluster_id, split_dates, run_id, cluster_cfg.output_parquet
        )

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
) -> None:
    """Compute and log confusion matrix + classification metrics to MLflow."""
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

    for split_name, dataloader in [
        ("val", dm.val_dataloader()),
        ("test", dm.test_dataloader()),
    ]:
        all_preds = []
        all_targets = []

        with torch.no_grad():
            for batch in dataloader:
                x, y = batch
                logits = model(x)
                preds = logits.argmax(dim=-1)
                all_preds.append(preds.cpu())
                all_targets.append(y.cpu())

        all_preds_np = torch.cat(all_preds).numpy()
        all_targets_np = torch.cat(all_targets).numpy()

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


def _run_precision_eval(
    model: LSTMForecaster,
    dm: TradingDataModule,
    config: dict,
    client,
    run_id: str,
    buy_thresh: float,
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
            dm.val_forward_returns[target_indices]
            if dm.val_forward_returns is not None
            else None
        )

        eval_result = evaluate_model(
            model=model,
            val_dataloader=dm.val_dataloader(),
            eval_config=eval_config,
            sample_dates=sample_dates,
            forward_returns=fwd_returns,
            buy_threshold=buy_thresh,
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

        _evaluate_cluster_trades(
            model, config, cluster_id, split_dates, run_id, clusters_parquet
        )
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
    features_path = get_normalized_parquet_path(config)
    n_symbols_per_cluster = int(resolve_env_value(
        optuna_cfg.get("n_symbols_per_cluster", 3), default=3
    ))

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
                cid, cluster_cfg.output_parquet,
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
            monitor="val_loss",
            patience=patience_per_trial,
            mode="min",
        )
        pruning_callback = PyTorchLightningPruningCallback(trial, monitor="val_loss")

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

        # Compute objective on validation set (top symbols only)
        result = _compute_objective_value(
            model, dm, min_recall,
            metric=obj_metric, threshold=obj_threshold, beta=beta,
        )
        del model, dm
        return result

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
    max_history_days = int(
        resolve_env_value(optuna_cfg.get("max_history_days", 30), default=30)
    )

    print(f"\n{'='*60}")
    print(f"GLOBAL OPTIMIZATION: All clusters, all symbols")
    print(f"{'='*60}")
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
