"""Strategy runner — load per-cluster champion models and generate ternary signals.

Generates BUY/SELL/HOLD recommendations for each symbol using its
cluster's trained model.

Usage:
    uv run python -m src.strategy.runner
    uv run python -m src.strategy.runner --symbols AAPL MSFT GOOGL
"""

from __future__ import annotations

import argparse
import glob
import os

import numpy as np
import polars as pl
import torch

from src.config import ClusterConfig, compute_split_dates, load_config
from src.features.technical import build_features, load_ohlcv
from src.models.base_model import LSTMForecaster
from src.models.dataset import EXCLUDE_COLS

CLASS_MAP = {0: "HOLD", 1: "BUY", 2: "SELL"}


def load_cluster_model(cluster_id: str) -> LSTMForecaster | None:
    """Load the best checkpoint for a cluster.

    Args:
        cluster_id: Cluster identifier.

    Returns:
        Loaded model or None if no checkpoint found.
    """
    pattern = f"**/{cluster_id}-best-*.ckpt"
    checkpoints = sorted(
        glob.glob(pattern, recursive=True),
        key=lambda p: os.path.getmtime(p),
    )
    checkpoints = [c for c in checkpoints if not c.startswith("mlruns/")]

    if not checkpoints:
        # Try mlruns
        mlruns_pattern = f"mlruns/**/{cluster_id}-best-*.ckpt"
        checkpoints = sorted(
            glob.glob(mlruns_pattern, recursive=True),
            key=lambda p: os.path.getmtime(p),
        )

    if not checkpoints:
        return None

    model = LSTMForecaster.load_from_checkpoint(checkpoints[-1], map_location="cpu")
    model.eval()
    return model


def generate_signals(
    symbols: list[str],
    config: dict,
) -> pl.DataFrame:
    """Generate ternary signals for all symbols using per-cluster models.

    Args:
        symbols: List of ticker symbols.
        config: Full config dict.

    Returns:
        DataFrame with columns [symbol, date, signal, confidence,
        prob_buy, prob_sell, prob_hold, cluster_id].
    """
    seq_len = config["model"]["sequence_length"]
    split_dates = compute_split_dates(config)
    train_end = split_dates.train_end
    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))

    # Load cluster assignments
    clusters_df = pl.read_parquet(cluster_cfg.output_parquet)

    # Load and prepare features
    print("Loading OHLCV data and building features...")
    df = load_ohlcv(symbols)
    df = build_features(df, config)

    # Drop all-null columns
    all_null_cols = [c for c in df.columns if df[c].null_count() == len(df)]
    if all_null_cols:
        df = df.drop(all_null_cols)

    feature_cols = [c for c in df.columns if c not in EXCLUDE_COLS]
    df = df.drop_nulls(subset=feature_cols)

    # Compute normalization from training period
    train_df = df.filter(pl.col("date") < train_end)
    if train_df.is_empty():
        print("No training data available for normalization.")
        return pl.DataFrame()

    train_matrix = train_df.select(feature_cols).to_numpy()
    train_mean = train_matrix.mean(axis=0)
    train_std = train_matrix.std(axis=0)
    train_std[train_std == 0] = 1.0

    # Load models per cluster
    cluster_ids = clusters_df["cluster_id"].unique().sort().to_list()
    models: dict[str, LSTMForecaster] = {}
    for cid in cluster_ids:
        model = load_cluster_model(cid)
        if model is not None:
            models[cid] = model
            print(f"  Loaded model for {cid}")
        else:
            print(f"  WARNING: No model found for {cid}")

    # Generate signals per symbol
    results = []
    for symbol in symbols:
        # Find cluster for this symbol
        sym_cluster = clusters_df.filter(pl.col("symbol") == symbol)
        if sym_cluster.is_empty():
            print(f"  {symbol}: not in any cluster, skipping")
            continue

        cluster_id = sym_cluster["cluster_id"][0]
        if cluster_id not in models:
            print(f"  {symbol}: no model for cluster {cluster_id}")
            continue

        model = models[cluster_id]
        sym_df = df.filter(pl.col("symbol") == symbol).sort("date")

        if len(sym_df) < seq_len:
            print(f"  {symbol}: not enough data ({len(sym_df)} rows)")
            continue

        recent = sym_df.tail(seq_len)
        features = recent.select(feature_cols).to_numpy()
        features = (features - train_mean) / train_std

        x = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            probs = model.predict_proba(x).squeeze(0).numpy()

        pred_class = int(np.argmax(probs))
        last_date = sym_df["date"].tail(1).item()

        results.append({
            "symbol": symbol,
            "date": last_date,
            "signal": CLASS_MAP[pred_class],
            "confidence": round(float(probs.max()), 4),
            "prob_buy": round(float(probs[1]), 4),
            "prob_sell": round(float(probs[2]), 4),
            "prob_hold": round(float(probs[0]), 4),
            "cluster_id": cluster_id,
        })

    return pl.DataFrame(results)


def main() -> None:
    """Generate trading recommendations from per-cluster champion models."""
    config = load_config()

    parser = argparse.ArgumentParser(description="Generate trading signals")
    # Default symbols: read from cluster assignments (all stocks in pipeline)
    cluster_cfg = config.get("clustering", {})
    clusters_path = cluster_cfg.get("output_parquet", "data/clusters.parquet")
    try:
        default_symbols = pl.read_parquet(clusters_path)["symbol"].unique().sort().to_list()
    except FileNotFoundError:
        default_symbols = config.get("ingestion", {}).get("symbols", [])
    parser.add_argument("--symbols", nargs="+", default=default_symbols)
    args = parser.parse_args()

    print(f"Generating signals for {len(args.symbols)} symbols...\n")
    signals = generate_signals(args.symbols, config)

    if signals.is_empty():
        print("No signals generated.")
        return

    # Display results by signal type
    for signal_type in ["BUY", "SELL", "HOLD"]:
        subset = signals.filter(pl.col("signal") == signal_type)
        if len(subset) > 0:
            print(f"\n=== {signal_type} ({len(subset)} stocks) ===")
            for row in subset.sort("confidence", descending=True).iter_rows(named=True):
                print(
                    f"  {row['symbol']:6s}  conf={row['confidence']:.1%}  "
                    f"buy={row['prob_buy']:.1%}  sell={row['prob_sell']:.1%}  "
                    f"hold={row['prob_hold']:.1%}  [{row['cluster_id']}]"
                )

    target_cfg = config.get("target", {})
    print(f"\nTarget: +{target_cfg.get('buy_threshold', 0.05):.0%} BUY / "
          f"-{target_cfg.get('sell_threshold', 0.03):.0%} SELL "
          f"in {target_cfg.get('horizon', 63)} trading days (~3 months)")


if __name__ == "__main__":
    main()
