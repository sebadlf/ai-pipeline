"""Strategy runner — load per-cluster champion models and generate prob_up predictions.

Generates prob_up (probability of rising >= buy_threshold) for each symbol
using its cluster's binary classification model.

Usage:
    uv run python -m src.strategy.runner
    uv run python -m src.strategy.runner --symbols AAPL MSFT GOOGL
"""

from __future__ import annotations

import argparse

import numpy as np
import polars as pl
import torch

from src.aggregation.consolidate import resolve_feature_cols
from src.config import ClusterConfig, compute_split_dates, load_config
from src.evaluation.champion import download_champion_checkpoint
from src.features.technical import build_features, fill_nulls, load_ohlcv
from src.models.base_model import LSTMForecaster



def load_cluster_model(cluster_id: str) -> LSTMForecaster | None:
    """Load the champion checkpoint for a cluster from MLflow registry.

    Args:
        cluster_id: Cluster identifier.

    Returns:
        Loaded model or None if no champion found.
    """
    try:
        ckpt_path, run_id = download_champion_checkpoint(cluster_id)
        print(f"    champion run {run_id[:12]}")
        model = LSTMForecaster.load_from_checkpoint(
            str(ckpt_path), map_location="cpu", weights_only=False,
        )
        model.eval()
        return model
    except FileNotFoundError:
        return None


def generate_signals(
    symbols: list[str],
    config: dict,
) -> pl.DataFrame:
    """Generate prob_up predictions for all symbols using per-cluster binary models.

    Args:
        symbols: List of ticker symbols.
        config: Full config dict.

    Returns:
        DataFrame with columns [symbol, date, prob_up, cluster_id].
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

    # Fill nulls (forward-fill fundamentals, median-fill rest)
    df = fill_nulls(df)

    # Drop all-null columns
    all_null_cols = [c for c in df.columns if df[c].null_count() == len(df)]
    if all_null_cols:
        df = df.drop(all_null_cols)

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

    # Resolve features and normalization per cluster (cached)
    cluster_feature_cols: dict[str, list[str]] = {}
    cluster_norm: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    FeatureMismatch_clusters = []
    for cid, model in models.items():
        try:
            fcols = resolve_feature_cols(model, df, config)
        except ValueError as e:
            if "features not in DataFrame" in str(e) or "Feature mismatch" in str(e):
                print(f"  Feature mismatch for {cid}: skipping this cluster. Retrain model after feature selection changes.")
                FeatureMismatch_clusters.append(cid)
                continue
            raise
        cluster_feature_cols[cid] = fcols
        cluster_symbols = clusters_df.filter(pl.col("cluster_id") == cid)["symbol"].to_list()
        train_df = df.filter(
            (pl.col("date") < train_end) & pl.col("symbol").is_in(cluster_symbols)
        ).drop_nulls(subset=fcols)
        if train_df.is_empty():
            continue
        train_matrix = train_df.select(fcols).to_numpy()
        np.nan_to_num(train_matrix, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
        mean = train_matrix.mean(axis=0)
        std = train_matrix.std(axis=0)
        std[std == 0] = 1.0
        cluster_norm[cid] = (mean, std)

    if FeatureMismatch_clusters:
        print(f"\n  WARNING: {len(FeatureMismatch_clusters)} clusters skipped due to feature mismatch: {', '.join(FeatureMismatch_clusters)}")
        print("  Recommendation: Retrain models after feature selection changes.\n")

    # Generate predictions per symbol
    results = []
    for symbol in symbols:
        # Find cluster for this symbol
        sym_cluster = clusters_df.filter(pl.col("symbol") == symbol)
        if sym_cluster.is_empty():
            print(f"  {symbol}: not in any cluster, skipping")
            continue

        cluster_id = sym_cluster["cluster_id"][0]
        if cluster_id not in models or cluster_id not in cluster_norm:
            print(f"  {symbol}: no model for cluster {cluster_id}")
            continue

        model = models[cluster_id]
        feature_cols = cluster_feature_cols[cluster_id]
        train_mean, train_std = cluster_norm[cluster_id]
        sym_df = df.filter(pl.col("symbol") == symbol).sort("date")

        if len(sym_df) < seq_len:
            print(f"  {symbol}: not enough data ({len(sym_df)} rows)")
            continue

        recent = sym_df.tail(seq_len)
        features = recent.select(feature_cols).to_numpy()
        np.nan_to_num(features, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
        features = (features - train_mean) / train_std

        x = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            probs = model.predict_proba(x).squeeze(0).numpy()

        last_date = sym_df["date"].tail(1).item()
        prob_up = float(probs[1])

        results.append({
            "symbol": symbol,
            "date": last_date,
            "prob_up": round(prob_up, 4),
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

    print(f"Generating predictions for {len(args.symbols)} symbols...\n")
    signals = generate_signals(args.symbols, config)

    if signals.is_empty():
        print("No predictions generated.")
        return

    target_cfg = config.get("target", {})
    buy_threshold = target_cfg.get("buy_threshold", 0.025)
    min_prob_up = config.get("portfolio", {}).get("profiles", {}).get(
        "aggressive", {}
    ).get("min_prob_up", 0.70)

    # Display actionable stocks (above min threshold)
    actionable = signals.filter(pl.col("prob_up") >= min_prob_up).sort("prob_up", descending=True)
    below = signals.filter(pl.col("prob_up") < min_prob_up).sort("prob_up", descending=True)

    if len(actionable) > 0:
        print(f"\n=== ACTIONABLE — prob_up >= {min_prob_up:.0%} ({len(actionable)} stocks) ===")
        for row in actionable.iter_rows(named=True):
            print(f"  {row['symbol']:6s}  prob_up={row['prob_up']:.1%}  [{row['cluster_id']}]")

    if len(below) > 0:
        print(f"\n=== BELOW THRESHOLD ({len(below)} stocks) ===")
        for row in below.head(20).iter_rows(named=True):
            print(f"  {row['symbol']:6s}  prob_up={row['prob_up']:.1%}  [{row['cluster_id']}]")
        if len(below) > 20:
            print(f"  ... and {len(below) - 20} more")

    print(f"\nTarget: UP >= +{buy_threshold:.1%} in {target_cfg.get('horizon', 21)} trading days (~1 month)")


if __name__ == "__main__":
    main()
