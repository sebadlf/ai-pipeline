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
import tempfile

import lightning as L
import mlflow
import numpy as np
import polars as pl
from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint, RichProgressBar
from lightning.pytorch.loggers import MLFlowLogger

from src.config import ClusterConfig, SplitDates, compute_split_dates, get_cluster_buy_threshold, get_features_parquet_path, load_config
from src.keys import MLFLOW_TRACKING_URI
from src.models.base_model import LSTMForecaster
from src.models.dataset import TradingDataModule


def _run_split_eval(
    prefix: str,
    preds: list[dict],
    period_start,
    period_end,
    client,
    run_id: str,
    config: dict,
) -> None:
    """Evaluate and log trade metrics for a single split period.

    Args:
        prefix: Metric prefix (e.g. "train", "val", "test").
        preds: List of prediction dicts from run_inference_for_period().
        period_start: Start date of the evaluation period.
        period_end: End date of the evaluation period.
        client: MLflow client instance.
        run_id: MLflow run ID.
        config: Full config dict.
    """
    from src.evaluation.backtest import load_test_prices, run_portfolio_backtest

    if not preds:
        print(f"    {prefix}: no predictions")
        return

    # Summarize prob_up distribution
    min_prob_up = 0.70  # default actionable threshold for eval
    n_actionable = sum(1 for p in preds if p["prob_up"] >= min_prob_up)
    n_total = len(preds)
    mean_prob = sum(p["prob_up"] for p in preds) / n_total if n_total else 0
    print(f"    {prefix}: {n_total} predictions, {n_actionable} actionable (prob_up >= {min_prob_up:.0%}), mean={mean_prob:.2%}")

    # Log counts
    client.log_metric(run_id, f"{prefix}_trade_n_actionable", n_actionable)
    client.log_metric(run_id, f"{prefix}_trade_n_total", n_total)

    # Save CSV artifact
    trades_df = pl.DataFrame(preds)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        trades_df.write_csv(f.name)
        client.log_artifact(run_id, f.name, artifact_path=f"trade_details/{prefix}_trades")

    # Filter actionable predictions (prob_up >= threshold) for backtest
    actionable = [p for p in preds if p["prob_up"] >= min_prob_up]
    if not actionable:
        print(f"    {prefix}: no actionable predictions, skipping backtest")
        for key in ["total_return", "sharpe", "sortino", "calmar",
                     "max_drawdown", "win_rate", "num_trades", "avg_return"]:
            client.log_metric(run_id, f"{prefix}_trade_{key}", 0.0)
        return

    # Equal-weight allocation across actionable predictions (long-only)
    weight = 1.0 / len(actionable)
    allocations_df = pl.DataFrame([
        {"symbol": p["symbol"], "weight": weight}
        for p in actionable
    ])

    # Load prices for the period
    symbols = [p["symbol"] for p in actionable]
    prices_df = load_test_prices(symbols, period_start, period_end)

    if prices_df.is_empty():
        print(f"    {prefix}: no price data for period")
        return

    # Run backtest
    bt_config = config.get("backtest", {})
    result = run_portfolio_backtest(allocations_df, prices_df, bt_config)

    # Log all backtest metrics with prefix
    metrics = {
        f"{prefix}_trade_total_return": result.total_return,
        f"{prefix}_trade_sharpe": result.sharpe_ratio,
        f"{prefix}_trade_sortino": result.sortino_ratio,
        f"{prefix}_trade_calmar": result.calmar_ratio,
        f"{prefix}_trade_max_drawdown": result.max_drawdown,
        f"{prefix}_trade_win_rate": result.win_rate,
        f"{prefix}_trade_num_trades": result.num_trades,
        f"{prefix}_trade_avg_return": result.avg_trade_return,
        f"{prefix}_trade_final_value": result.final_value,
    }
    for key, value in metrics.items():
        val = float(value) if value is not None and np.isfinite(value) else 0.0
        client.log_metric(run_id, key, val)

    print(f"    {prefix}: return={result.total_return:+.2%}, "
          f"sharpe={result.sharpe_ratio:.3f}, trades={result.num_trades}, "
          f"win_rate={result.win_rate:.1%}")


def _log_confusion_matrix(
    model: LSTMForecaster,
    dm: TradingDataModule,
    client,
    run_id: str,
) -> None:
    """Compute and log confusion matrix + classification metrics to MLflow.

    Evaluates the model on both validation and test sets, logs precision/recall/f1
    for the UP class, and saves confusion matrix images as artifacts.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import ConfusionMatrixDisplay, confusion_matrix, precision_recall_fscore_support

    import torch

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

        all_preds = torch.cat(all_preds).numpy()
        all_targets = torch.cat(all_targets).numpy()

        # Confusion matrix
        cm = confusion_matrix(all_targets, all_preds, labels=[0, 1])

        # Precision, recall, F1 for UP class (index 1)
        precision, recall, f1, _ = precision_recall_fscore_support(
            all_targets, all_preds, labels=[0, 1], zero_division=0.0,
        )
        client.log_metric(run_id, f"{split_name}_precision_up", float(precision[1]))
        client.log_metric(run_id, f"{split_name}_recall_up", float(recall[1]))
        client.log_metric(run_id, f"{split_name}_f1_up", float(f1[1]))

        print(f"  {split_name} — precision_up={precision[1]:.3f}, "
              f"recall_up={recall[1]:.3f}, f1_up={f1[1]:.3f}")

        # Save confusion matrix image
        fig, ax = plt.subplots(figsize=(5, 4))
        disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=class_names)
        disp.plot(ax=ax, cmap="Blues", values_format="d")
        ax.set_title(f"Confusion Matrix — {split_name}")
        fig.tight_layout()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            fig.savefig(f.name, dpi=100)
            client.log_artifact(run_id, f.name, artifact_path="confusion_matrix")
        plt.close(fig)


def _evaluate_cluster_trades(
    model: LSTMForecaster,
    config: dict,
    cluster_id: str,
    split_dates: SplitDates,
    run_id: str,
    clusters_parquet: str,
) -> None:
    """Run mini-backtests for a cluster across train/val/test splits.

    Generates predictions for each temporal split, simulates trades with
    equal-weight allocation, and logs all metrics + trade details as
    MLflow artifacts with split-specific prefixes.
    """
    from src.aggregation.consolidate import run_inference_for_period

    features_path = get_features_parquet_path(config)
    features_df = pl.read_parquet(features_path).sort(["symbol", "date"])

    # Drop all-null columns (same as aggregation)
    all_null_cols = [c for c in features_df.columns if features_df[c].null_count() == len(features_df)]
    if all_null_cols:
        features_df = features_df.drop(all_null_cols)

    clusters_df = pl.read_parquet(clusters_parquet)
    client = mlflow.MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)

    model.eval()
    print(f"  Trade eval across splits:")

    splits = [
        ("train", split_dates.start_date, split_dates.train_end),
        ("val", split_dates.val_start, split_dates.val_end),
        ("test", split_dates.test_start, split_dates.today),
    ]

    for prefix, period_start, period_end in splits:
        preds = run_inference_for_period(
            cluster_id, model, features_df, clusters_df, config,
            split_dates, period_start, period_end,
        )
        _run_split_eval(
            prefix, preds, period_start, period_end,
            client, run_id, config,
        )


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

    # Resolve per-cluster threshold
    buy_thresh = get_cluster_buy_threshold(config, cluster_id)
    print(f"  Threshold — UP: +{buy_thresh:.1%}")

    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))

    # Data
    features_path = get_features_parquet_path(config)
    print(f"  Features source: {features_path}")
    dm = TradingDataModule(
        parquet_path=features_path,
        seq_len=model_cfg["sequence_length"],
        batch_size=train_cfg["batch_size"],
        split_dates=split_dates,
        cluster_id=cluster_id,
        clusters_parquet=cluster_cfg.output_parquet,
    )
    dm.setup()

    # Skip clusters with insufficient data for sequence creation
    train_samples = len(dm.train_ds)
    val_samples = len(dm.val_ds)
    if train_samples <= 0 or val_samples <= 0:
        print(f"  SKIPPING {cluster_id}: insufficient valid sequences (train={train_samples}, val={val_samples})")
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
        class_weights=dm.class_weights,
        num_attention_heads=model_cfg.get("num_attention_heads", 4),
        focal_gamma=train_cfg.get("focal_gamma", 2.0),
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
        dirpath="checkpoints",
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
        "num_classes": num_classes,
    }.items():
        client.log_param(run_id, key, value)

    # Confusion matrix + precision/recall/f1
    try:
        _log_confusion_matrix(model, dm, client, run_id)
    except Exception as e:
        print(f"  Confusion matrix logging failed: {e}")

    # Evaluate trading performance on test set
    try:
        _evaluate_cluster_trades(
            model, config, cluster_id, split_dates,
            run_id, cluster_cfg.output_parquet,
        )
    except Exception as e:
        print(f"  Trade evaluation failed: {e}")


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
