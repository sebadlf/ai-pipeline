"""Model training with PyTorch Lightning and MLflow logging.

Usage:
    uv run python -m src.training.train
    uv run python -m src.training.train --config configs/default.yaml
"""

from __future__ import annotations

import argparse

import lightning as L
import mlflow
from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint, RichProgressBar
from lightning.pytorch.loggers import MLFlowLogger

from src.config import compute_split_dates, load_config
from src.keys import MLFLOW_TRACKING_URI
from src.models.base_model import LSTMForecaster
from src.models.dataset import TradingDataModule


def train(config: dict) -> None:
    """Run training loop.

    Args:
        config: Full config dict with model, training, and features sections.
    """
    model_cfg = config["model"]
    train_cfg = config["training"]

    split_dates = compute_split_dates(config)
    print("Temporal splits:")
    print(split_dates.summary())

    # Data
    dm = TradingDataModule(
        parquet_path="data/features.parquet",
        seq_len=model_cfg["sequence_length"],
        batch_size=train_cfg["batch_size"],
        split_dates=split_dates,
    )
    dm.setup()

    # Model
    model = LSTMForecaster(
        input_size=dm.input_size,
        hidden_size=model_cfg["hidden_size"],
        num_layers=model_cfg["num_layers"],
        dropout=model_cfg["dropout"],
        learning_rate=train_cfg["learning_rate"],
        weight_decay=train_cfg.get("weight_decay", 0.0),
        label_smoothing=train_cfg.get("label_smoothing", 0.05),
    )

    # MLflow logger
    tracking_uri = MLFLOW_TRACKING_URI
    mlflow_logger = MLFlowLogger(
        experiment_name="trading-forecaster",
        tracking_uri=tracking_uri,
        log_model=True,
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
        filename="best-{epoch}-{val_acc:.4f}",
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

    # Log best checkpoint to MLflow
    if checkpoint.best_model_path:
        mlflow.log_artifact(checkpoint.best_model_path, artifact_path="checkpoints")
        print(f"Best checkpoint: {checkpoint.best_model_path}")


def main() -> None:
    """Entry point for training."""
    parser = argparse.ArgumentParser(description="Train trading model")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    args = parser.parse_args()

    config = load_config(args.config)
    train(config)


if __name__ == "__main__":
    main()
