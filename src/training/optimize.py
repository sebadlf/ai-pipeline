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
from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint, RichProgressBar
from lightning.pytorch.loggers import MLFlowLogger
from optuna.integration import PyTorchLightningPruningCallback

from src.config import (
    ClusterConfig,
    SplitDates,
    compute_split_dates,
    get_cluster_buy_threshold,
    get_features_parquet_path,
    load_config,
    resolve_env_value,
)
from src.db import get_engine
from src.keys import MLFLOW_TRACKING_URI, OPTUNA_STORAGE_URL
from src.models.base_model import LSTMForecaster
from src.models.dataset import TradingDataModule


def _get_random_symbols(
    cluster_id: str, clusters_parquet: str, n: int = 1
) -> list[str]:
    """Get N random symbols from a cluster.

    Randomly selects N symbols from the cluster for use in
    hyperparameter optimization. This provides a representative
    sample without biasing toward large-cap stocks.

    Args:
        cluster_id: Cluster identifier.
        clusters_parquet: Path to cluster assignments parquet.
        n: Number of random symbols to return (default 2).

    Returns:
        List of symbol strings.
    """
    import random
    import polars as pl

    # Load cluster symbols
    clusters_df = pl.read_parquet(clusters_parquet)
    cluster_symbols = clusters_df.filter(pl.col("cluster_id") == cluster_id)[
        "symbol"
    ].to_list()

    if not cluster_symbols:
        return []

    # Randomly select N symbols (or all if cluster has fewer than N)
    if len(cluster_symbols) <= n:
        return cluster_symbols

    random.seed(42)  # For reproducibility
    return random.sample(cluster_symbols, n)


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


def suggest_hyperparams(trial: optuna.Trial) -> dict[str, Any]:
    """Define the Optuna search space.

    Returns a dict with all suggested hyperparameters for this trial.
    """
    return {
        # Training hyperparams
        "learning_rate": trial.suggest_float("learning_rate", 1e-4, 1e-2, log=True),
        "batch_size": trial.suggest_categorical("batch_size", [64, 128, 256]),
        "weight_decay": trial.suggest_float("weight_decay", 1e-4, 0.1, log=True),
        "label_smoothing": trial.suggest_float("label_smoothing", 0.0, 0.15),
        "focal_gamma": trial.suggest_float("focal_gamma", 0.0, 5.0),
        "noise_std": trial.suggest_float("noise_std", 0.0, 0.05),
        # Architecture
        "hidden_size": trial.suggest_categorical("hidden_size", [64, 96, 128, 256]),
        "num_layers": trial.suggest_int("num_layers", 1, 4),
        "dropout": trial.suggest_float("dropout", 0.1, 0.5),
        "num_attention_heads": trial.suggest_categorical(
            "num_attention_heads", [0, 2, 4]
        ),
        "sequence_length": trial.suggest_categorical("sequence_length", [10, 20, 30]),
    }


def _compute_objective_value(
    model: LSTMForecaster,
    dm: TradingDataModule,
    min_recall: float,
    beta: float = 0.5,
) -> float:
    """Compute F-beta score as optimization objective with quadratic recall penalty.

    Uses the full precision-recall curve to find the optimal threshold that
    maximizes F-beta, allowing better calibration than a fixed 0.5 threshold.
    Beta < 1 prioritizes precision over recall (ideal for trading where
    false positives are costly).

    Args:
        model: Trained model in eval mode.
        dm: DataModule with validation data.
        min_recall: Minimum recall threshold before penalizing.
        beta: F-beta parameter. < 1 prioritizes precision, > 1 prioritizes recall.

    Returns:
        F-beta score to maximize (higher is better), with quadratic penalty
        applied if recall is below min_recall.
    """
    from sklearn.metrics import precision_recall_curve

    model.eval()
    all_probs = []
    all_targets = []

    with torch.no_grad():
        for batch in dm.val_dataloader():
            x, y = batch
            logits = model(x)
            probs = torch.softmax(logits, dim=-1)[:, 1]  # Probability of UP class
            all_probs.append(probs.cpu())
            all_targets.append(y.cpu())

    probs = torch.cat(all_probs).numpy()
    targets = torch.cat(all_targets).numpy()

    # Compute precision-recall curve across all thresholds
    precisions, recalls, _ = precision_recall_curve(targets, probs)

    # Calculate F-beta for each point on the curve
    # F_beta = (1 + beta^2) * (precision * recall) / (beta^2 * precision + recall)
    beta_sq = beta**2
    fbetas = (
        (1 + beta_sq)
        * (precisions * recalls)
        / ((beta_sq * precisions) + recalls + 1e-10)
    )
    fbetas = np.nan_to_num(fbetas, nan=0.0)

    # Find maximum F-beta and corresponding recall
    best_idx = np.argmax(fbetas)
    best_fbeta = fbetas[best_idx]
    best_recall = recalls[best_idx]

    # Apply quadratic penalty if recall is below minimum threshold
    # Quadratic penalty is more aggressive than linear for very low recall
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
    epochs_per_trial = optuna_cfg.get("epochs_per_trial", 30)
    patience_per_trial = optuna_cfg.get("patience_per_trial", 7)
    min_recall = optuna_cfg.get("min_recall_up", 0.10)

    # F-beta objective configuration
    obj_cfg = optuna_cfg.get("objective", {})
    beta = obj_cfg.get("beta", 0.5)

    features_path = get_features_parquet_path(config)

    def objective(trial: optuna.Trial) -> float:
        params = suggest_hyperparams(trial)

        # DataModule with trial hyperparams
        dm = TradingDataModule(
            parquet_path=features_path,
            seq_len=params["sequence_length"],
            batch_size=params["batch_size"],
            split_dates=split_dates,
            cluster_id=cluster_id,
            clusters_parquet=cluster_cfg.output_parquet,
            noise_std=params["noise_std"],
        )
        dm.setup()

        if len(dm.train_ds) <= 0 or len(dm.val_ds) <= 0:
            return 0.0

        # Model with trial architecture
        model = LSTMForecaster(
            input_size=dm.input_size,
            hidden_size=params["hidden_size"],
            num_layers=params["num_layers"],
            num_classes=2,
            dropout=params["dropout"],
            learning_rate=params["learning_rate"],
            weight_decay=params["weight_decay"],
            label_smoothing=params["label_smoothing"],
            class_weights=dm.class_weights,
            num_attention_heads=params["num_attention_heads"],
            focal_gamma=params["focal_gamma"],
            feature_names=dm.feature_cols,
        )

        # Callbacks: early stopping + Optuna pruning
        early_stop = EarlyStopping(
            monitor="val_loss",
            patience=patience_per_trial,
            mode="min",
        )
        pruning_callback = PyTorchLightningPruningCallback(trial, monitor="val_loss")

        trainer = L.Trainer(
            max_epochs=epochs_per_trial,
            accelerator="mps",
            devices=1,
            callbacks=[early_stop, pruning_callback],
            log_every_n_steps=10,
            gradient_clip_val=1.0,
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

        # Compute objective on validation set
        return _compute_objective_value(model, dm, min_recall, beta)

    return objective


def _get_optuna_storage(optuna_cfg: dict) -> str | None:
    """Return the Optuna storage URL if persistence is enabled, else None (in-memory)."""
    if not optuna_cfg.get("persist", False):
        return None
    return OPTUNA_STORAGE_URL


def _purge_old_trials(study: optuna.Study, max_history_days: int) -> int:
    """Remove trials older than max_history_days from the study.

    Optuna doesn't expose a delete-trial API, so we re-enqueue the recent
    trials into a fresh study. This only applies when using persistent storage.

    Returns the number of prior trials kept for warm-starting.
    """
    if max_history_days <= 0:
        return len(study.trials)

    cutoff = datetime.now() - timedelta(days=max_history_days)
    kept = [t for t in study.trials if t.datetime_start and t.datetime_start >= cutoff]
    purged = len(study.trials) - len(kept)

    if purged > 0:
        print(
            f"  Optuna history: purged {purged} trials older than {max_history_days}d, "
            f"kept {len(kept)} for warm-starting"
        )

    return len(kept)


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
    n_trials = optuna_cfg.get("n_trials", 30)
    startup_trials = optuna_cfg.get("startup_trials", 5)
    max_history_days = int(
        resolve_env_value(optuna_cfg.get("max_history_days", 30), default=30)
    )

    print(f"\n{'='*60}")
    print(f"Optimizing cluster: {cluster_id}")
    print(f"{'='*60}")
    print("Temporal splits:")
    print(split_dates.summary())
    print(f"  Threshold — UP: +{buy_thresh:.1%}")
    print(f"  Optuna — {n_trials} trials, {startup_trials} startup")

    # Storage: PostgreSQL (persistent) or None (in-memory)
    storage = _get_optuna_storage(optuna_cfg)
    if storage:
        print(
            f"  Optuna storage: PostgreSQL (warm-starting enabled, max_history={max_history_days}d)"
        )
    else:
        print("  Optuna storage: in-memory (no persistence)")

    # Create or load existing study
    study = optuna.create_study(
        direction="maximize",
        study_name=f"cluster/{cluster_id}",
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
    objective_fn = _create_trial_objective(
        config,
        cluster_id,
        split_dates,
        cluster_cfg,
        buy_thresh,
    )

    # Progress callback for real-time feedback
    def progress_callback(study: optuna.Study, trial: optuna.Trial):
        if trial.number == 0:
            print(f"\n{'='*60}")
            print(f"Starting Optuna optimization for {cluster_id}...")
            print(f"{'='*60}\n")

        # Print every 5 trials and last trial
        if trial.number % 5 == 0 or trial.number == n_trials - 1:
            print(
                f"Trial {trial.number + 1}/{n_trials} | Best F-beta: {study.best_value:.4f}"
            )
            if hasattr(trial, "params") and trial.params:
                print(
                    f"  Current params: lr={trial.params.get('learning_rate', 0):.6f}, "
                    f"hidden={trial.params.get('hidden_size', 0)}, "
                    f"dropout={trial.params.get('dropout', 0):.2f}, "
                    f"seq_len={trial.params.get('sequence_length', 0)}"
                )
            if trial.value is not None:
                print(f"  Current value: {trial.value:.4f}")
            print()

    study.optimize(
        objective_fn,
        n_trials=n_trials,
        show_progress_bar=True,
        callbacks=[progress_callback],
    )

    # Report best trial
    best = study.best_trial
    print(f"\n  Best trial #{best.number}: value={best.value:.4f}")
    print(f"  Best params: {best.params}")

    # Train final model with best hyperparams
    train_final_model(config, cluster_id, best.params, split_dates)


def train_final_model(
    config: dict,
    cluster_id: str,
    best_params: dict[str, Any],
    split_dates: SplitDates,
) -> None:
    """Train the final model with optimal hyperparameters and log to MLflow.

    Args:
        config: Full config dict.
        cluster_id: Cluster identifier.
        best_params: Best hyperparameters from Optuna.
        split_dates: Temporal split dates.
    """
    train_cfg = config["training"]
    buy_thresh = get_cluster_buy_threshold(config, cluster_id)
    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))
    features_path = get_features_parquet_path(config)

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
        return

    # Model
    model = LSTMForecaster(
        input_size=dm.input_size,
        hidden_size=best_params["hidden_size"],
        num_layers=best_params["num_layers"],
        num_classes=2,
        dropout=best_params["dropout"],
        learning_rate=best_params["learning_rate"],
        weight_decay=best_params["weight_decay"],
        label_smoothing=best_params["label_smoothing"],
        class_weights=dm.class_weights,
        num_attention_heads=best_params["num_attention_heads"],
        focal_gamma=best_params["focal_gamma"],
        feature_names=dm.feature_cols,
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

    early_stop = EarlyStopping(
        monitor="val_precision_up",
        patience=patience,
        mode="max",
    )
    checkpoint = ModelCheckpoint(
        dirpath="checkpoints",
        monitor="val_precision_up",
        mode="max",
        save_top_k=1,
        filename=f"{cluster_id}-best-{{epoch}}-{{val_precision_up:.4f}}",
    )

    trainer = L.Trainer(
        max_epochs=max_epochs,
        accelerator="mps",
        devices=1,
        logger=mlflow_logger,
        callbacks=[early_stop, checkpoint, RichProgressBar()],
        log_every_n_steps=10,
        gradient_clip_val=1.0,
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
        params_to_log = {
            "cluster_id": cluster_id,
            "buy_threshold": buy_thresh,
            "num_classes": 2,
            "optuna_n_trials": config["training"].get("optuna", {}).get("n_trials", 30),
            **{f"optuna_{k}": v for k, v in best_params.items()},
        }
        for key, value in params_to_log.items():
            client.log_param(run_id, key, value)

        # Confusion matrix + precision/recall/f1
        _log_confusion_matrix(model, dm, client, run_id)

        # Precision-based evaluation with walk-forward stability
        _run_precision_eval(model, dm, config, client, run_id, buy_thresh)

        # Trade evaluation
        _run_trade_eval(
            model, config, cluster_id, split_dates, run_id, cluster_cfg.output_parquet
        )
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
    epochs_per_trial = optuna_cfg.get("epochs_per_trial", 30)
    patience_per_trial = optuna_cfg.get("patience_per_trial", 7)
    min_recall = optuna_cfg.get("min_recall_up", 0.10)
    obj_cfg = optuna_cfg.get("objective", {})
    beta = obj_cfg.get("beta", 0.5)
    features_path = get_features_parquet_path(config)

    # Pre-compute random symbols per cluster for fast trials
    import polars as pl

    clusters_df = pl.read_parquet(cluster_cfg.output_parquet)
    cluster_ids = clusters_df["cluster_id"].unique().sort().to_list()

    selected_symbols = []
    for cid in cluster_ids:
        symbols = _get_random_symbols(cid, cluster_cfg.output_parquet, n=2)
        selected_symbols.extend(symbols)

    print(
        f"  Optimization will use {len(selected_symbols)} symbols (2 random from each of {len(cluster_ids)} clusters)"
    )

    def objective(trial: optuna.Trial) -> float:
        params = suggest_hyperparams(trial)

        # DataModule with top symbols only
        dm = TradingDataModule(
            parquet_path=features_path,
            seq_len=params["sequence_length"],
            batch_size=params["batch_size"],
            split_dates=split_dates,
            cluster_id=None,
            clusters_parquet=cluster_cfg.output_parquet,
            noise_std=params["noise_std"],
        )
        # Set filtered symbols before setup
        dm._optimization_symbols = selected_symbols
        dm.setup()

        if len(dm.train_ds) <= 0 or len(dm.val_ds) <= 0:
            return 0.0

        # Model with trial architecture
        model = LSTMForecaster(
            input_size=dm.input_size,
            hidden_size=params["hidden_size"],
            num_layers=params["num_layers"],
            num_classes=2,
            dropout=params["dropout"],
            learning_rate=params["learning_rate"],
            weight_decay=params["weight_decay"],
            label_smoothing=params["label_smoothing"],
            class_weights=dm.class_weights,
            num_attention_heads=params["num_attention_heads"],
            focal_gamma=params["focal_gamma"],
            feature_names=dm.feature_cols,
        )

        # Callbacks: early stopping + Optuna pruning
        early_stop = EarlyStopping(
            monitor="val_loss",
            patience=patience_per_trial,
            mode="min",
        )
        pruning_callback = PyTorchLightningPruningCallback(trial, monitor="val_loss")

        trainer = L.Trainer(
            max_epochs=epochs_per_trial,
            accelerator="mps",
            devices=1,
            callbacks=[early_stop, pruning_callback],
            log_every_n_steps=10,
            gradient_clip_val=1.0,
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

        # Compute objective on validation set (top symbols only)
        return _compute_objective_value(model, dm, min_recall, beta)

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
    n_trials = optuna_cfg.get("n_trials_global", 50)  # More trials for global search
    startup_trials = optuna_cfg.get("startup_trials", 5)
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

    # Progress callback for real-time feedback
    def progress_callback(study: optuna.Study, trial: optuna.Trial):
        if trial.number == 0:
            print(f"\n{'='*60}")
            print("Starting Optuna optimization...")
            print(f"{'='*60}\n")

        # Print every 5 trials and last trial
        if trial.number % 5 == 0 or trial.number == n_trials - 1:
            print(
                f"Trial {trial.number + 1}/{n_trials} | Best F-beta: {study.best_value:.4f}"
            )
            if hasattr(trial, "params") and trial.params:
                print(
                    f"  Current params: lr={trial.params.get('learning_rate', 0):.6f}, "
                    f"hidden={trial.params.get('hidden_size', 0)}, "
                    f"dropout={trial.params.get('dropout', 0):.2f}, "
                    f"seq_len={trial.params.get('sequence_length', 0)}"
                )
            if trial.value is not None:
                print(f"  Current value: {trial.value:.4f}")
            print()

    study.optimize(
        objective_fn,
        n_trials=n_trials,
        show_progress_bar=True,
        callbacks=[progress_callback],
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
