"""Stock clustering by GICS sector with KMeans (Stage 1).

Divides stocks first by sector, then clusters within each sector using
behavioral features computed from the training period only.

Usage:
    uv run python -m src.features.clustering
    uv run python -m src.features.clustering --config configs/default.yaml
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import mlflow
import numpy as np
import polars as pl
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text

from src.config import ClusterConfig, compute_split_dates, load_config
from src.db import get_engine, init_db
from src.keys import MLFLOW_TRACKING_URI


def load_sectors(engine) -> pl.DataFrame:
    """Load GICS sector assignments from the database.

    Returns:
        DataFrame with columns [symbol, sector, sub_industry].
    """
    query = "SELECT symbol, sector, sub_industry FROM stock_sectors ORDER BY symbol"
    return pl.read_database(query, engine)


def compute_clustering_features(
    engine,
    symbols: list[str],
    train_end: dt.date,
    spy_symbol: str = "SPY",
) -> pl.DataFrame:
    """Compute per-stock behavioral features for clustering.

    Uses only data up to train_end to avoid leakage.

    Args:
        engine: SQLAlchemy engine.
        symbols: List of symbols to compute features for.
        train_end: End date of the training period.
        spy_symbol: Benchmark symbol for beta computation.

    Returns:
        DataFrame with columns [symbol, return_20d_mean, volatility_60d,
        volume_profile, rsi_14_mean, beta_60d].
    """
    placeholders = ", ".join(f"'{s}'" for s in symbols)
    query = f"""
        SELECT symbol, date, close, volume
        FROM ohlcv_daily
        WHERE symbol IN ({placeholders})
          AND date <= '{train_end}'
        ORDER BY symbol, date
    """
    df = pl.read_database(query, engine)

    if df.is_empty():
        return pl.DataFrame(schema={
            "symbol": pl.Utf8,
            "return_20d_mean": pl.Float64,
            "volatility_60d": pl.Float64,
            "volume_profile": pl.Float64,
            "rsi_14_mean": pl.Float64,
            "beta_60d": pl.Float64,
        })

    # Compute daily returns
    df = df.sort(["symbol", "date"]).with_columns(
        pl.col("close").pct_change().over("symbol").alias("daily_return"),
    )

    # Load SPY for beta computation
    spy_query = f"""
        SELECT date, close FROM ohlcv_daily
        WHERE symbol = '{spy_symbol}' AND date <= '{train_end}'
        ORDER BY date
    """
    spy_df = pl.read_database(spy_query, engine)
    spy_df = spy_df.sort("date").with_columns(
        pl.col("close").pct_change().alias("spy_return"),
    ).select(["date", "spy_return"])

    df = df.join(spy_df, on="date", how="left")

    # Per-symbol aggregated features
    features = []
    for symbol in df["symbol"].unique().sort().to_list():
        sym_df = df.filter(pl.col("symbol") == symbol).drop_nulls(subset=["daily_return"])
        if len(sym_df) < 60:
            continue

        returns = sym_df["daily_return"].to_numpy()

        # return_20d_mean: average of 20-day rolling returns
        return_20d = sym_df.with_columns(
            pl.col("daily_return").rolling_mean(20).alias("r20")
        )["r20"].drop_nulls()
        return_20d_mean = float(return_20d.mean()) if len(return_20d) > 0 else 0.0

        # volatility_60d: std of daily returns over trailing 60 days (use last chunk)
        tail_returns = returns[-min(252, len(returns)):]
        volatility_60d = float(np.std(tail_returns[-60:])) if len(tail_returns) >= 60 else float(np.std(tail_returns))

        # volume_profile: average relative volume
        vol_sma = sym_df.with_columns(
            pl.col("volume").rolling_mean(20).alias("vol_sma")
        ).with_columns(
            (pl.col("volume") / pl.col("vol_sma")).alias("rel_vol")
        )["rel_vol"].drop_nulls()
        volume_profile = float(vol_sma.mean()) if len(vol_sma) > 0 else 1.0

        # rsi_14_mean: average RSI-14 over trailing period
        delta = sym_df["daily_return"]
        gain = delta.clip(lower_bound=0).rolling_mean(14)
        loss = (-delta.clip(upper_bound=0)).rolling_mean(14)
        rsi_vals = (100 - 100 / (1 + gain / loss)).drop_nulls()
        rsi_14_mean = float(rsi_vals.mean()) if len(rsi_vals) > 0 else 50.0

        # beta_60d: covariance(stock, spy) / variance(spy) over last 60 days
        spy_col = sym_df["spy_return"].drop_nulls()
        stock_col = sym_df.filter(pl.col("spy_return").is_not_null())["daily_return"]
        if len(stock_col) >= 60 and len(spy_col) >= 60:
            s_ret = stock_col.tail(60).to_numpy()
            b_ret = spy_col.tail(60).to_numpy()
            cov = np.cov(s_ret, b_ret)[0, 1]
            var_b = np.var(b_ret)
            beta_60d = float(cov / var_b) if var_b > 0 else 1.0
        else:
            beta_60d = 1.0

        features.append({
            "symbol": symbol,
            "return_20d_mean": return_20d_mean,
            "volatility_60d": volatility_60d,
            "volume_profile": volume_profile,
            "rsi_14_mean": rsi_14_mean,
            "beta_60d": beta_60d,
        })

    return pl.DataFrame(features)


def run_clustering(
    config: dict,
    reference_date: dt.date | None = None,
) -> pl.DataFrame:
    """Assign stocks to clusters within GICS sectors.

    Args:
        config: Full config dict.
        reference_date: Date for split computation. Defaults to today.

    Returns:
        DataFrame with columns [symbol, sector, cluster_id, silhouette_score].
    """
    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))
    split_dates = compute_split_dates(config, reference_date)

    engine = get_engine()
    sectors_df = load_sectors(engine)

    if sectors_df.is_empty():
        raise RuntimeError("No sector data found. Run ingestion first.")

    all_symbols = sectors_df["symbol"].to_list()
    feat_df = compute_clustering_features(engine, all_symbols, split_dates.train_end)

    # Join sector info
    feat_df = feat_df.join(sectors_df.select(["symbol", "sector"]), on="symbol", how="left")

    feature_cols = [
        "return_20d_mean", "volatility_60d", "volume_profile", "rsi_14_mean", "beta_60d"
    ]

    results = []
    sector_list = feat_df["sector"].unique().sort().to_list()

    for sector in sector_list:
        sector_df = feat_df.filter(pl.col("sector") == sector)
        n_stocks = len(sector_df)

        if n_stocks == 0:
            continue

        X = sector_df.select(feature_cols).to_numpy()

        # Standardize within sector
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Replace NaN/Inf with 0 after scaling
        X_scaled = np.nan_to_num(X_scaled, nan=0.0, posinf=0.0, neginf=0.0)

        # Determine actual number of clusters
        n_clusters = min(cluster_cfg.n_clusters_per_sector, n_stocks)
        if n_clusters < 2:
            # Not enough stocks to cluster — assign all to cluster 0
            for symbol in sector_df["symbol"].to_list():
                results.append({
                    "symbol": symbol,
                    "sector": sector,
                    "cluster_id": f"{sector}_0",
                    "silhouette_score": None,
                })
            continue

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)

        # Compute silhouette score (needs n_samples > n_labels)
        n_unique_labels = len(set(labels))
        if n_unique_labels > 1 and n_stocks > n_unique_labels:
            sil_score = float(silhouette_score(X_scaled, labels))
        else:
            sil_score = 0.0

        # Check for small clusters and merge them
        symbols = sector_df["symbol"].to_list()
        cluster_counts: dict[int, list[int]] = {}
        for idx, label in enumerate(labels):
            cluster_counts.setdefault(label, []).append(idx)

        # Find small clusters and reassign to nearest centroid
        for label, indices in list(cluster_counts.items()):
            if len(indices) < cluster_cfg.min_cluster_size and n_clusters > 1:
                # Reassign to nearest non-small cluster
                for idx in indices:
                    distances = np.linalg.norm(
                        kmeans.cluster_centers_ - X_scaled[idx], axis=1
                    )
                    # Find nearest cluster that is not this one
                    sorted_clusters = np.argsort(distances)
                    for candidate in sorted_clusters:
                        if candidate != label:
                            labels[idx] = candidate
                            break

        # Renumber labels to be contiguous
        unique_labels = sorted(set(labels))
        label_map = {old: new for new, old in enumerate(unique_labels)}

        for idx, symbol in enumerate(symbols):
            results.append({
                "symbol": symbol,
                "sector": sector,
                "cluster_id": f"{sector}_{label_map[labels[idx]]}",
                "silhouette_score": sil_score,
            })

    result_df = pl.DataFrame(results)

    # Print summary
    print(f"\nClustering summary ({len(result_df)} stocks, {len(sector_list)} sectors):")
    for cluster_id in result_df["cluster_id"].unique().sort().to_list():
        count = result_df.filter(pl.col("cluster_id") == cluster_id).height
        print(f"  {cluster_id}: {count} stocks")

    return result_df


def save_clusters(
    result_df: pl.DataFrame,
    config: dict,
    run_date: dt.date | None = None,
) -> None:
    """Save cluster assignments to database and parquet.

    Args:
        result_df: DataFrame from run_clustering().
        config: Full config dict.
        run_date: Date for the run. Defaults to today.
    """
    run_date = run_date or dt.date.today()
    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))

    # Save to parquet
    output_path = Path(cluster_cfg.output_parquet)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result_df.write_parquet(str(output_path))
    print(f"Saved clusters to {output_path}")

    # Save to database
    engine = get_engine()
    with engine.begin() as conn:
        for row in result_df.iter_rows(named=True):
            stmt = text("""
                INSERT INTO cluster_assignments (run_date, symbol, sector, cluster_id, silhouette_score)
                VALUES (:run_date, :symbol, :sector, :cluster_id, :silhouette_score)
                ON CONFLICT (run_date, symbol) DO UPDATE SET
                    sector = EXCLUDED.sector,
                    cluster_id = EXCLUDED.cluster_id,
                    silhouette_score = EXCLUDED.silhouette_score
            """)
            conn.execute(stmt, {
                "run_date": run_date,
                "symbol": row["symbol"],
                "sector": row["sector"],
                "cluster_id": row["cluster_id"],
                "silhouette_score": row["silhouette_score"],
            })
    print(f"Saved {len(result_df)} cluster assignments to database")


def main() -> None:
    """Run stock clustering pipeline."""
    parser = argparse.ArgumentParser(description="Cluster stocks by sector")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    args = parser.parse_args()

    config = load_config(args.config)
    result_df = run_clustering(config)
    save_clusters(result_df, config)

    # Log to MLflow
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("clustering")
    with mlflow.start_run(run_name="cluster-assignment"):
        cluster_cfg = config.get("clustering", {})
        mlflow.log_params({
            "method": cluster_cfg.get("method", "kmeans"),
            "n_clusters_per_sector": cluster_cfg.get("n_clusters_per_sector", 3),
            "min_cluster_size": cluster_cfg.get("min_cluster_size", 3),
            "n_stocks": len(result_df),
            "n_clusters": result_df["cluster_id"].n_unique(),
        })
        # Log cluster parquet as artifact
        mlflow.log_artifact(cluster_cfg.get("output_parquet", "data/clusters.parquet"))
    print("Logged clustering results to MLflow")


if __name__ == "__main__":
    main()
