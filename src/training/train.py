"""Model training with PyTorch Lightning and MLflow logging.

Supports per-cluster training (Stage 2) where each cluster gets its own
MLflow experiment and model checkpoint.

Usage:
    uv run python -m src.training.train
    uv run python -m src.training.train --cluster Technology_0
    uv run python -m src.training.train --config configs/default.yaml
"""

from __future__ import annotations

import argparse

import lightning as L
import mlflow
import polars as pl
from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint, RichProgressBar
from lightning.pytorch.loggers import MLFlowLogger

from src.config import ClusterConfig, compute_split_dates, get_cluster_thresholds, load_config
from src.keys import MLFLOW_TRACKING_URI
from src.models.base_model import LSTMForecaster
from src.models.dataset import TradingDataModule


def train_single_cluster(config: dict, cluster_id: str) -> None:
    """Train a model for a single cluster.

    Args:
        config: Full config dict.
        cluster_id: Cluster identifier (e.g. "Technology_0").
    """
    model_cfg = config["model"]
    train_cfg = config["training"]

    split_dates = compute_split_dates(config)
    print(f"\n{'='*60}")
    print(f"Training cluster: {cluster_id}")
    print(f"{'='*60}")
    print("Temporal splits:")
    print(split_dates.summary())

    # Resolve per-cluster thresholds
    buy_thresh, sell_thresh = get_cluster_thresholds(config, cluster_id)
    print(f"  Thresholds — BUY: +{buy_thresh:.1%}, SELL: -{sell_thresh:.1%}")

    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))

    # Data
    dm = TradingDataModule(
        parquet_path="data/features.parquet",
        seq_len=model_cfg["sequence_length"],
        batch_size=train_cfg["batch_size"],
        split_dates=split_dates,
        cluster_id=cluster_id,
        clusters_parquet=cluster_cfg.output_parquet,
    )
    dm.setup()

    # Skip clusters with insufficient data for sequence creation
    seq_len = model_cfg["sequence_length"]
    train_samples = dm.train_ds.features.shape[0] - seq_len
    val_samples = dm.val_ds.features.shape[0] - seq_len
    if train_samples <= 0 or val_samples <= 0:
        print(f"  SKIPPING {cluster_id}: insufficient data for training (need >{seq_len} samples per split, got train={dm.train_ds.features.shape[0]}, val={dm.val_ds.features.shape[0]})")
        return

    # Model
    num_classes = model_cfg.get("num_classes", 3)
    model = LSTMForecaster(
        input_size=dm.input_size,
        hidden_size=model_cfg["hidden_size"],
        num_layers=model_cfg["num_layers"],
        num_classes=num_classes,
        dropout=model_cfg["dropout"],
        learning_rate=train_cfg["learning_rate"],
        weight_decay=train_cfg.get("weight_decay", 0.0),
        label_smoothing=train_cfg.get("label_smoothing", 0.05),
    )

    # MLflow logger — separate experiment per cluster
    prefix = train_cfg.get("cluster_experiment_prefix", "cluster")
    experiment_name = f"{prefix}/{cluster_id}"
    mlflow_logger = MLFlowLogger(
        experiment_name=experiment_name,
        tracking_uri=MLFLOW_TRACKING_URI,
        log_model=True,
        save_dir="checkpoints",
    )

    # Callbacks
    early_stop = EarlyStopping(
        monitor="val_acc",
        patience=train_cfg["early_stopping_patience"],
        mode="max",
    )
    checkpoint = ModelCheckpoint(
        monitor="val_acc",
        mode="max",
        save_top_k=1,
        filename=f"{cluster_id}-best-{{epoch}}-{{val_acc:.4f}}",
    )

    # Trainer
    trainer = L.Trainer(
        max_epochs=train_cfg["max_epochs"],
        accelerator="mps",
        devices=1,
        logger=mlflow_logger,
        callbacks=[early_stop, checkpoint, RichProgressBar()],
        log_every_n_steps=10,
        gradient_clip_val=1.0,
    )

    # Train
    print(f"Training with {dm.input_size} features, seq_len={model_cfg['sequence_length']}")
    trainer.fit(model, dm)

    # Test
    test_results = trainer.test(model, dm)
    print(f"Test results: {test_results}")

    # Log best checkpoint and cluster params to MLflow
    if checkpoint.best_model_path:
        mlflow.log_artifact(checkpoint.best_model_path, artifact_path="checkpoints")
        print(f"Best checkpoint: {checkpoint.best_model_path}")

    # Log cluster params to the same MLflow run used by the Lightning logger
    run_id = mlflow_logger.run_id
    client = mlflow.MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    for key, value in {
        "cluster_id": cluster_id,
        "buy_threshold": buy_thresh,
        "sell_threshold": sell_thresh,
        "num_classes": num_classes,
    }.items():
        client.log_param(run_id, key, value)


def train_all_clusters(config: dict) -> None:
    """Train one model per cluster.

    Args:
        config: Full config dict.
    """
    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))
    clusters_df = pl.read_parquet(cluster_cfg.output_parquet)
    cluster_ids = clusters_df["cluster_id"].unique().sort().to_list()

    print(f"Found {len(cluster_ids)} clusters to train")
    failed = []
    for i, cluster_id in enumerate(cluster_ids, 1):
        n_symbols = clusters_df.filter(pl.col("cluster_id") == cluster_id).height
        print(f"\n[{i}/{len(cluster_ids)}] Cluster {cluster_id} ({n_symbols} symbols)")
        try:
            train_single_cluster(config, cluster_id)
        except Exception as e:
            print(f"  ERROR training {cluster_id}: {e}")
            failed.append(cluster_id)

    print(f"\nTraining complete: {len(cluster_ids) - len(failed)}/{len(cluster_ids)} clusters succeeded.")
    if failed:
        print(f"  Failed clusters: {', '.join(failed)}")


def main() -> None:
    """Entry point for training."""
    parser = argparse.ArgumentParser(description="Train trading model")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    parser.add_argument("--cluster", default=None, help="Train a single cluster ID")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.cluster:
        train_single_cluster(config, args.cluster)
    else:
        train_all_clusters(config)


if __name__ == "__main__":
    main()
