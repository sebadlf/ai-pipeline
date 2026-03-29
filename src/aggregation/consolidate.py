"""Consolidate per-cluster predictions into unified results (Stage 3).

Loads the best model checkpoint for each cluster, runs inference on
the most recent data, and produces a single predictions table.

Usage:
    uv run python -m src.aggregation.consolidate
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import os
from pathlib import Path

import mlflow
import numpy as np
import polars as pl
import torch
from sqlalchemy import text

from src.config import ClusterConfig, compute_split_dates, load_config
from src.db import get_engine
from src.keys import MLFLOW_TRACKING_URI
from src.models.base_model import LSTMForecaster
from src.models.dataset import EXCLUDE_COLS

CLASS_MAP = {0: "HOLD", 1: "BUY", 2: "SELL"}


def find_best_checkpoint(cluster_id: str, config: dict) -> str | None:
    """Find the best model checkpoint for a cluster.

    Searches both local checkpoints and MLflow artifacts.

    Args:
        cluster_id: Cluster identifier.
        config: Full config dict.

    Returns:
        Path to the best checkpoint, or None if not found.
    """
    # Search for checkpoints in mlflow/ directory (primary) and fallback to mlruns/
    for search_dir in ["checkpoints", "mlruns", "."]:
        pattern = f"{search_dir}/**/{cluster_id}-best-*.ckpt"
        checkpoints = sorted(
            glob.glob(pattern, recursive=True),
            key=lambda p: os.path.getmtime(p),
        )
        if checkpoints:
            return checkpoints[-1]

    return None


def run_inference_for_cluster(
    cluster_id: str,
    model: LSTMForecaster,
    features_df: pl.DataFrame,
    clusters_df: pl.DataFrame,
    config: dict,
    split_dates,
) -> list[dict]:
    """Run inference for all symbols in a cluster.

    Args:
        cluster_id: Cluster identifier.
        model: Loaded model.
        features_df: Full features DataFrame.
        clusters_df: Cluster assignments.
        config: Full config dict.
        split_dates: SplitDates instance.

    Returns:
        List of prediction dicts.
    """
    model_cfg = config["model"]
    seq_len = model_cfg["sequence_length"]

    cluster_symbols = (
        clusters_df.filter(pl.col("cluster_id") == cluster_id)["symbol"].to_list()
    )
    feature_cols = [c for c in features_df.columns if c not in EXCLUDE_COLS]

    # Compute normalization from training period
    train_df = features_df.filter(
        (pl.col("date") < split_dates.train_end)
        & pl.col("symbol").is_in(cluster_symbols)
    ).drop_nulls(subset=feature_cols)

    if train_df.is_empty():
        return []

    train_matrix = train_df.select(feature_cols).to_numpy()
    train_mean = train_matrix.mean(axis=0)
    train_std = train_matrix.std(axis=0)
    train_std[train_std == 0] = 1.0

    predictions = []
    for symbol in cluster_symbols:
        sym_df = features_df.filter(pl.col("symbol") == symbol).sort("date")
        sym_df = sym_df.drop_nulls(subset=feature_cols)

        if len(sym_df) < seq_len:
            continue

        # Use the most recent seq_len rows for prediction
        recent = sym_df.tail(seq_len)
        features = recent.select(feature_cols).to_numpy()
        norm_features = (features - train_mean) / train_std

        x = torch.tensor(norm_features, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            probs = model.predict_proba(x).squeeze(0).numpy()

        pred_class = int(np.argmax(probs))
        predictions.append({
            "symbol": symbol,
            "cluster_id": cluster_id,
            "prediction": CLASS_MAP[pred_class],
            "confidence": float(probs.max()),
            "prob_hold": float(probs[0]),
            "prob_buy": float(probs[1]),
            "prob_sell": float(probs[2]),
        })

    return predictions


def aggregate_predictions(config: dict) -> pl.DataFrame:
    """Run inference on all clusters and consolidate predictions.

    Args:
        config: Full config dict.

    Returns:
        DataFrame with columns [symbol, cluster_id, prediction, confidence,
        prob_buy, prob_sell, prob_hold, model_run_id].
    """
    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))
    split_dates = compute_split_dates(config)

    clusters_df = pl.read_parquet(cluster_cfg.output_parquet)
    cluster_ids = clusters_df["cluster_id"].unique().sort().to_list()

    features_df = pl.read_parquet("data/features.parquet").sort(["symbol", "date"])

    # Drop all-null columns
    all_null_cols = [c for c in features_df.columns if features_df[c].null_count() == len(features_df)]
    if all_null_cols:
        features_df = features_df.drop(all_null_cols)

    all_predictions = []

    for cluster_id in cluster_ids:
        ckpt_path = find_best_checkpoint(cluster_id, config)
        if ckpt_path is None:
            print(f"  WARNING: No checkpoint found for {cluster_id}, skipping")
            continue

        print(f"  Loading model for {cluster_id} from {ckpt_path}")
        model = LSTMForecaster.load_from_checkpoint(ckpt_path, map_location="cpu")
        model.eval()

        preds = run_inference_for_cluster(
            cluster_id, model, features_df, clusters_df, config, split_dates
        )
        for p in preds:
            p["model_run_id"] = None  # Could be populated from MLflow
        all_predictions.extend(preds)

    result_df = pl.DataFrame(all_predictions)

    # Summary
    if not result_df.is_empty():
        for signal in ["BUY", "SELL", "HOLD"]:
            count = result_df.filter(pl.col("prediction") == signal).height
            print(f"  {signal}: {count} stocks")

    return result_df


def save_predictions(
    result_df: pl.DataFrame,
    config: dict,
    run_date: dt.date | None = None,
) -> None:
    """Save predictions to database and parquet.

    Args:
        result_df: DataFrame from aggregate_predictions().
        config: Full config dict.
        run_date: Date for the run. Defaults to today.
    """
    run_date = run_date or dt.date.today()
    output_path = config.get("aggregation", {}).get("output_parquet", "data/predictions.parquet")

    # Save parquet
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    result_df.write_parquet(output_path)
    print(f"Saved predictions to {output_path}")

    # Save to database
    engine = get_engine()
    with engine.begin() as conn:
        for row in result_df.iter_rows(named=True):
            stmt = text("""
                INSERT INTO predictions
                    (run_date, symbol, cluster_id, prediction, confidence,
                     prob_buy, prob_sell, prob_hold, model_run_id)
                VALUES
                    (:run_date, :symbol, :cluster_id, :prediction, :confidence,
                     :prob_buy, :prob_sell, :prob_hold, :model_run_id)
                ON CONFLICT (run_date, symbol) DO UPDATE SET
                    cluster_id = EXCLUDED.cluster_id,
                    prediction = EXCLUDED.prediction,
                    confidence = EXCLUDED.confidence,
                    prob_buy = EXCLUDED.prob_buy,
                    prob_sell = EXCLUDED.prob_sell,
                    prob_hold = EXCLUDED.prob_hold,
                    model_run_id = EXCLUDED.model_run_id
            """)
            conn.execute(stmt, {**row, "run_date": run_date})
    print(f"Saved {len(result_df)} predictions to database")


def main() -> None:
    """Run prediction aggregation pipeline."""
    parser = argparse.ArgumentParser(description="Aggregate per-cluster predictions")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    args = parser.parse_args()

    config = load_config(args.config)

    print("Aggregating predictions from all clusters...")
    result_df = aggregate_predictions(config)

    if result_df.is_empty():
        print("No predictions generated. Ensure models are trained first.")
        return

    save_predictions(result_df, config)

    # Log to MLflow
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("aggregation")
    with mlflow.start_run(run_name="prediction-aggregation"):
        mlflow.log_metric("total_predictions", len(result_df))
        for signal in ["BUY", "SELL", "HOLD"]:
            count = result_df.filter(pl.col("prediction") == signal).height
            mlflow.log_metric(f"n_{signal.lower()}", count)
        output_path = config.get("aggregation", {}).get("output_parquet", "data/predictions.parquet")
        mlflow.log_artifact(output_path)
    print("Logged aggregation results to MLflow")


if __name__ == "__main__":
    main()
