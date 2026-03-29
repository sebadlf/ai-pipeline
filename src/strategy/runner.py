"""Strategy runner — load champion model and generate buy signals.

Usage:
    uv run python -m src.strategy.runner
    uv run python -m src.strategy.runner --symbols AAPL MSFT GOOGL
"""

from __future__ import annotations

import argparse
import datetime as dt

import numpy as np
import polars as pl
import torch
from mlflow.tracking import MlflowClient

from src.config import compute_split_dates, load_config
from src.features.technical import build_features, load_ohlcv
from src.keys import MLFLOW_TRACKING_URI
from src.models.base_model import LSTMForecaster
from src.models.dataset import EXCLUDE_COLS


MODEL_NAME = "trading-forecaster"


def load_champion_model() -> LSTMForecaster:
    """Load the best training checkpoint from MLflow.

    Finds the training run with the highest val_acc that has a checkpoint
    artifact, downloads it, and loads the model.
    """
    import mlflow

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)

    experiment = client.get_experiment_by_name("trading-forecaster")
    if experiment is None:
        raise RuntimeError("No 'trading-forecaster' experiment found. Run training first.")

    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="metrics.val_acc > 0",
        order_by=["start_time DESC"],
        max_results=10,
    )

    for run in runs:
        top_artifacts = [a.path for a in client.list_artifacts(run.info.run_id)]
        ckpt_dirs = [a for a in top_artifacts if a.startswith("best-")]
        if not ckpt_dirs:
            continue

        inner = client.list_artifacts(run.info.run_id, ckpt_dirs[0])
        ckpt_files = [a.path for a in inner if a.path.endswith(".ckpt")]
        if not ckpt_files:
            continue

        run_name = run.data.tags.get("mlflow.runName", run.info.run_id[:12])
        val_acc = run.data.metrics.get("val_acc", 0)
        print(f"Latest training run: {run_name} (val_acc={val_acc:.4f})")

        local_path = client.download_artifacts(run.info.run_id, ckpt_files[0])
        print(f"Loaded checkpoint: {ckpt_files[0]}")

        model = LSTMForecaster.load_from_checkpoint(local_path, map_location="cpu")
        model.eval()
        return model

    raise FileNotFoundError("No training run with a checkpoint found.")


def generate_signals(
    model: LSTMForecaster,
    symbols: list[str],
    config: dict,
) -> pl.DataFrame:
    """Generate buy signals using current data and training-set normalization.

    Args:
        model: Loaded champion model.
        symbols: List of ticker symbols.
        config: Full config dict.
    """
    seq_len = config["model"]["sequence_length"]
    split_dates = compute_split_dates(config)
    train_end = split_dates.train_end
    confidence = config["evaluation"].get("confidence_threshold", 0.6)

    df = load_ohlcv(symbols)
    df = build_features(df, config)

    # Drop columns that are entirely null (e.g. adj_close)
    all_null_cols = [c for c in df.columns if df[c].null_count() == len(df)]
    if all_null_cols:
        df = df.drop(all_null_cols)

    feature_cols = [c for c in df.columns if c not in EXCLUDE_COLS]

    # Drop rows where any *feature* column is null (warmup period)
    df = df.drop_nulls(subset=feature_cols)

    # Compute normalization stats from training period only
    train_df = df.filter(pl.col("date") < train_end)
    train_matrix = train_df.select(feature_cols).to_numpy()
    train_mean = train_matrix.mean(axis=0)
    train_std = train_matrix.std(axis=0)
    train_std[train_std == 0] = 1.0

    results = []
    for symbol in symbols:
        sym_df = df.filter(pl.col("symbol") == symbol).sort("date")

        if len(sym_df) < seq_len:
            print(f"  {symbol}: not enough data ({len(sym_df)} rows, need {seq_len})")
            continue

        recent = sym_df.tail(seq_len)
        features = recent.select(feature_cols).to_numpy()
        features = (features - train_mean) / train_std

        x = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            prob = model.predict_proba(x).item()

        last_date = sym_df["date"].tail(1).item()
        signal = "BUY" if prob >= confidence else "HOLD"

        results.append({
            "symbol": symbol,
            "date": last_date,
            "probability": round(prob, 4),
            "signal": signal,
        })

    return pl.DataFrame(results)


def main() -> None:
    """Generate buy recommendations from the champion model."""
    config = load_config()

    parser = argparse.ArgumentParser(description="Generate trading signals")
    parser.add_argument("--symbols", nargs="+", default=config["ingestion"]["symbols"])
    args = parser.parse_args()

    confidence = config["evaluation"].get("confidence_threshold", 0.6)

    print("Loading champion model...")
    model = load_champion_model()

    print(f"Generating signals for {args.symbols} (threshold: {confidence})...\n")
    signals = generate_signals(model, args.symbols, config)

    buys = signals.filter(pl.col("signal") == "BUY")
    holds = signals.filter(pl.col("signal") == "HOLD")

    if len(buys) > 0:
        print("=== BUY Recommendations ===")
        for row in buys.sort("probability", descending=True).iter_rows(named=True):
            print(f"  {row['symbol']:6s}  prob={row['probability']:.1%}  ({row['date']})")
    else:
        print("No buy signals above confidence threshold.")

    if len(holds) > 0:
        print("\n--- HOLD ---")
        for row in holds.sort("probability", descending=True).iter_rows(named=True):
            print(f"  {row['symbol']:6s}  prob={row['probability']:.1%}  ({row['date']})")

    print(f"\nModel: probability of ≥{config['target']['threshold']:.0%} gain "
          f"in {config['target']['horizon']} trading days (~3 months)")


if __name__ == "__main__":
    main()
