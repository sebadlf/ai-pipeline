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
from src.config import ClusterConfig, load_config
from src.evaluation.champion import download_ensemble_checkpoints
from src.features.normalize import apply_normalization_to_array, load_normalization_stats
from src.features.technical import build_features, fill_nulls, load_ohlcv
from src.models.base_model import LSTMForecaster


def load_cluster_ensemble(
    cluster_id: str,
    ensemble_k: int = 3,
) -> list[LSTMForecaster]:
    """Load ensemble of champion models for a cluster from MLflow registry.

    Args:
        cluster_id: Cluster identifier.
        ensemble_k: Maximum ensemble members to load.

    Returns:
        List of loaded models (may be 1 for pre-ensemble checkpoints).
        Empty list if no champion found.
    """
    try:
        paths = download_ensemble_checkpoints(cluster_id, ensemble_k)
        models = []
        run_ids = []
        for ckpt_path, run_id in paths:
            model = LSTMForecaster.load_from_checkpoint(
                str(ckpt_path),
                map_location="cpu",
                weights_only=False,
            )
            model.eval()
            models.append(model)
            run_ids.append(run_id[:12] if run_id else "local")
        print(f"    ensemble: {len(models)} models (runs {', '.join(run_ids)})")
        return models
    except FileNotFoundError:
        return []


def generate_signals(
    symbols: list[str],
    config: dict,
) -> pl.DataFrame:
    """Generate prob_up predictions for all symbols using per-cluster ensemble models.

    Args:
        symbols: List of ticker symbols.
        config: Full config dict.

    Returns:
        DataFrame with columns [symbol, date, prob_up, cluster_id].
    """
    seq_len = config["model"]["sequence_length"]
    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))
    ensemble_k = config.get("training", {}).get("optuna", {}).get("ensemble_top_k", 3)

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

    # Load ensemble models per cluster
    cluster_ids = clusters_df["cluster_id"].unique().sort().to_list()
    cluster_ensembles: dict[str, list[LSTMForecaster]] = {}
    for cid in cluster_ids:
        models = load_cluster_ensemble(cid, ensemble_k)
        if models:
            cluster_ensembles[cid] = models
            print(f"  Loaded {len(models)} model(s) for {cid}")
        else:
            print(f"  WARNING: No model found for {cid}")

    # Load normalization stats (shared across all clusters)
    try:
        norm_stats = load_normalization_stats(config)
        print(f"  Loaded normalization stats ({norm_stats['n_features']} features)")
    except FileNotFoundError:
        print("  WARNING: No normalization stats found. Run `make normalize` first.")
        norm_stats = None

    # Resolve feature columns per cluster (using first model in ensemble)
    cluster_feature_cols: dict[str, list[str]] = {}
    feature_mismatch_clusters = []
    for cid, models in cluster_ensembles.items():
        try:
            fcols = resolve_feature_cols(models[0], df, config)
        except ValueError as e:
            if "features not in DataFrame" in str(e) or "Feature mismatch" in str(e):
                print(
                    f"  Feature mismatch for {cid}: skipping. "
                    "Retrain after feature selection changes."
                )
                feature_mismatch_clusters.append(cid)
                continue
            raise
        cluster_feature_cols[cid] = fcols

    if feature_mismatch_clusters:
        print(
            f"\n  WARNING: {len(feature_mismatch_clusters)} clusters skipped due "
            f"to feature mismatch: {', '.join(feature_mismatch_clusters)}"
        )
        print("  Recommendation: Retrain models after feature selection changes.\n")

    # Generate predictions per symbol (ensemble-averaged)
    results = []
    for symbol in symbols:
        sym_cluster = clusters_df.filter(pl.col("symbol") == symbol)
        if sym_cluster.is_empty():
            print(f"  {symbol}: not in any cluster, skipping")
            continue

        cluster_id = sym_cluster["cluster_id"][0]
        if cluster_id not in cluster_ensembles or cluster_id not in cluster_feature_cols:
            print(f"  {symbol}: no model for cluster {cluster_id}")
            continue

        models = cluster_ensembles[cluster_id]
        feature_cols = cluster_feature_cols[cluster_id]
        sym_df = df.filter(pl.col("symbol") == symbol).sort("date")

        if len(sym_df) < seq_len:
            print(f"  {symbol}: not enough data ({len(sym_df)} rows)")
            continue

        recent = sym_df.tail(seq_len)
        features = recent.select(feature_cols).to_numpy()
        if norm_stats is not None:
            features = apply_normalization_to_array(features, feature_cols, norm_stats)
        else:
            np.nan_to_num(features, copy=False, nan=0.0, posinf=0.0, neginf=0.0)

        x = torch.tensor(features, dtype=torch.float32).unsqueeze(0)

        # Average prob_up across ensemble models
        prob_ups = []
        for model in models:
            with torch.no_grad():
                probs = model.predict_proba(x).squeeze(0).numpy()
            prob_ups.append(float(probs[1]))

        last_date = sym_df["date"].tail(1).item()
        avg_prob_up = sum(prob_ups) / len(prob_ups)

        results.append(
            {
                "symbol": symbol,
                "date": last_date,
                "prob_up": round(avg_prob_up, 4),
                "cluster_id": cluster_id,
            }
        )

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
    min_prob_up = (
        config.get("portfolio", {})
        .get("profiles", {})
        .get("aggressive", {})
        .get("min_prob_up", 0.70)
    )

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

    print(
        f"\nTarget: UP >= +{buy_threshold:.1%} in "
        f"{target_cfg.get('horizon', 21)} trading days (~1 month)"
    )


if __name__ == "__main__":
    main()
