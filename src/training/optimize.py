"""Optuna hyperparameter optimization for per-cluster LSTM training.

Replaces brute-force repeated training with systematic search over
architecture and training hyperparameters. Optimizes for precision
of the UP class (minimize false positives) with a recall floor.

Usage:
    Called from train.py via optimize_cluster().
"""

from __future__ import annotations

import tempfile
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
from src.keys import MLFLOW_TRACKING_URI
from src.models.base_model import LSTMForecaster
from src.models.dataset import TradingDataModule


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
        "num_attention_heads": trial.suggest_categorical("num_attention_heads", [0, 2, 4]),
        "sequence_length": trial.suggest_categorical("sequence_length", [10, 20, 30]),
    }


def _compute_objective_value(
    model: LSTMForecaster,
    dm: TradingDataModule,
    min_recall: float,
) -> float:
    """Compute the optimization objective: precision_up with recall penalty.

    Args:
        model: Trained model in eval mode.
        dm: DataModule with validation data.
        min_recall: Minimum recall threshold before penalizing.

    Returns:
        Objective value to maximize (higher is better).
    """
    model.eval()
    all_preds = []
    all_targets = []

    with torch.no_grad():
        for batch in dm.val_dataloader():
            x, y = batch
            logits = model(x)
            preds = logits.argmax(dim=-1)
            all_preds.append(preds.cpu())
            all_targets.append(y.cpu())

    preds = torch.cat(all_preds).numpy()
    targets = torch.cat(all_targets).numpy()

    up_preds = preds == 1
    up_targets = targets == 1
    tp = int((up_preds & up_targets).sum())
    fp = int((up_preds & ~up_targets).sum())
    fn = int((~up_preds & up_targets).sum())

    precision_up = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall_up = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    # Penalize if recall is below minimum threshold
    if recall_up < min_recall:
        return precision_up * (recall_up / min_recall) if min_recall > 0 else 0.0
    return precision_up


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
            return 0.0

        # Compute objective on validation set
        return _compute_objective_value(model, dm, min_recall)

    return objective


def optimize_cluster(config: dict, cluster_id: str) -> None:
    """Run Optuna optimization for a cluster, then train final model.

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

    print(f"\n{'='*60}")
    print(f"Optimizing cluster: {cluster_id}")
    print(f"{'='*60}")
    print("Temporal splits:")
    print(split_dates.summary())
    print(f"  Threshold — UP: +{buy_thresh:.1%}")
    print(f"  Optuna — {n_trials} trials, {startup_trials} startup")

    # Create study
    study = optuna.create_study(
        direction="maximize",
        study_name=f"cluster/{cluster_id}",
        pruner=optuna.pruners.MedianPruner(
            n_startup_trials=startup_trials,
            n_warmup_steps=5,
        ),
    )

    # Run optimization
    objective_fn = _create_trial_objective(
        config, cluster_id, split_dates, cluster_cfg, buy_thresh,
    )
    study.optimize(objective_fn, n_trials=n_trials, show_progress_bar=True)

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

    # Train
    print(f"  Training with {dm.input_size} features, seq_len={best_params['sequence_length']}")
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
    client = mlflow.MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)

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
    _run_trade_eval(model, config, cluster_id, split_dates, run_id, cluster_cfg.output_parquet)


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

    for split_name, dataloader in [("val", dm.val_dataloader()), ("test", dm.test_dataloader())]:
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
            all_targets_np, all_preds_np, labels=[0, 1], zero_division=0.0,
        )
        client.log_metric(run_id, f"{split_name}_precision_up", float(precision[1]))
        client.log_metric(run_id, f"{split_name}_recall_up", float(recall[1]))
        client.log_metric(run_id, f"{split_name}_f1_up", float(f1[1]))

        print(f"  {split_name} — precision_up={precision[1]:.3f}, "
              f"recall_up={recall[1]:.3f}, f1_up={f1[1]:.3f}")

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
        print(f"  Precision eval: stability_score={eval_result.stability_score:.4f}, "
              f"auc_pr={eval_result.auc_pr:.4f}, stage={eval_result.elimination_stage}")
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
