"""Global stock clustering with KMeans (Stage 1).

Clusters all stocks together using behavioral, fundamental, and macro
features computed from the training period only. Optionally includes
one-hot encoded sector as a clustering feature. Uses PCA for
dimensionality reduction and automatic K selection via silhouette analysis.

Usage:
    uv run python -m src.features.clustering
    uv run python -m src.features.clustering --config configs/default.yaml
"""

from __future__ import annotations

import argparse
import logging
import datetime as dt
from pathlib import Path

import mlflow
import warnings

import numpy as np
import polars as pl
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text

from src.config import ClusterConfig, compute_split_dates, load_config
from src.db import get_engine, in_params, init_db
from src.keys import MLFLOW_TRACKING_URI

logger = logging.getLogger(__name__)

_KM_FIELDS = [
    "returnOnEquity", "earningsYield", "freeCashFlowYield", "evToEBITDA",
]
_FR_FIELDS = [
    "grossProfitMargin", "netProfitMargin", "debtToEquityRatio",
    "priceToEarningsRatio", "priceToBookRatio", "dividendYield",
]


def load_sectors(engine) -> pl.DataFrame:
    """Load GICS sector assignments from the database.

    Returns:
        DataFrame with columns [symbol, sector, sub_industry].
    """
    query = "SELECT symbol, sector, sub_industry FROM stock_sectors ORDER BY symbol"
    return pl.read_database(query, engine)


def _load_fundamentals_for_clustering(
    engine,
    symbols: list[str],
    train_end: dt.date,
) -> dict[str, dict[str, float]]:
    """Load most recent quarterly fundamental metrics per symbol before train_end.

    Returns dict of {symbol: {feature_name: value}}.
    """
    ph, params = in_params("s", symbols)
    params["train_end"] = train_end

    km_extracts = ", ".join(
        f"(data->>'{f}')::double precision AS {f}" for f in _KM_FIELDS
    )
    km_query = text(f"""
        SELECT DISTINCT ON (symbol) symbol, {km_extracts}
        FROM key_metrics_quarterly
        WHERE symbol IN ({ph}) AND date <= :train_end
        ORDER BY symbol, date DESC
    """).bindparams(**params)

    fr_extracts = ", ".join(
        f"(data->>'{f}')::double precision AS {f}" for f in _FR_FIELDS
    )
    fr_query = text(f"""
        SELECT DISTINCT ON (symbol) symbol, {fr_extracts}
        FROM financial_ratios_quarterly
        WHERE symbol IN ({ph}) AND date <= :train_end
        ORDER BY symbol, date DESC
    """).bindparams(**params)

    result: dict[str, dict[str, float]] = {}

    with engine.connect() as conn:
        try:
            km_df = pl.read_database(km_query, conn)
            for row in km_df.iter_rows(named=True):
                sym = row["symbol"]
                result.setdefault(sym, {})
                for f in _KM_FIELDS:
                    result[sym][f"km_{f}"] = row.get(f)
        except Exception as e:
            logger.warning("Failed to load key_metrics for clustering: %s", e)

        try:
            fr_df = pl.read_database(fr_query, conn)
            for row in fr_df.iter_rows(named=True):
                sym = row["symbol"]
                result.setdefault(sym, {})
                for f in _FR_FIELDS:
                    result[sym][f"fr_{f}"] = row.get(f)
        except Exception as e:
            logger.warning("Failed to load financial_ratios for clustering: %s", e)

    return result


def _load_macro_series(
    engine,
    train_end: dt.date,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Load VIX and treasury spread series up to train_end for sensitivity computation."""
    vix_query = text(
        "SELECT date, close AS vix_close FROM vix_daily WHERE date <= :train_end ORDER BY date"
    ).bindparams(train_end=train_end)
    treasury_query = text(
        "SELECT date, year10 - year2 AS spread_10y_2y FROM treasury_rates WHERE date <= :train_end ORDER BY date"
    ).bindparams(train_end=train_end)

    with engine.connect() as conn:
        try:
            vix_df = pl.read_database(vix_query, conn)
        except Exception:
            vix_df = pl.DataFrame(schema={"date": pl.Date, "vix_close": pl.Float64})

        try:
            treasury_df = pl.read_database(treasury_query, conn)
        except Exception:
            treasury_df = pl.DataFrame(schema={"date": pl.Date, "spread_10y_2y": pl.Float64})

    return vix_df, treasury_df


def _load_sector_avg_returns(
    engine,
    train_end: dt.date,
) -> dict[str, float]:
    """Load average sector daily return over last 252 days before train_end."""
    query = text("""
        SELECT sector, AVG(average_change) AS avg_change
        FROM sector_performance_daily
        WHERE date <= :train_end
          AND date >= :train_end::date - INTERVAL '252 days'
        GROUP BY sector
    """).bindparams(train_end=train_end)
    try:
        with engine.connect() as conn:
            df = pl.read_database(query, conn)
        return {row["sector"]: row["avg_change"] for row in df.iter_rows(named=True)}
    except Exception:
        return {}


def compute_clustering_features(
    engine,
    symbols: list[str],
    train_end: dt.date,
    sectors_df: pl.DataFrame,
    spy_symbol: str = "SPY",
) -> pl.DataFrame:
    """Compute per-stock behavioral, fundamental, and macro features for clustering.

    Uses only data up to train_end to avoid leakage.

    Args:
        engine: SQLAlchemy engine.
        symbols: List of symbols to compute features for.
        train_end: End date of the training period.
        sectors_df: DataFrame with [symbol, sector] mapping.
        spy_symbol: Benchmark symbol for beta computation.
    """
    ph, params = in_params("s", symbols)
    params["train_end"] = train_end
    query = text(f"""
        SELECT symbol, date, close, volume
        FROM ohlcv_daily
        WHERE symbol IN ({ph})
          AND date <= :train_end
        ORDER BY symbol, date
    """).bindparams(**params)
    with engine.connect() as conn:
        df = pl.read_database(query, conn)

    if df.is_empty():
        return pl.DataFrame(schema={"symbol": pl.Utf8})

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

    # Load macro series for sensitivity
    vix_df, treasury_df = _load_macro_series(engine, train_end)
    vix_df = vix_df.sort("date").with_columns(
        pl.col("vix_close").pct_change().alias("vix_return"),
    )
    treasury_df = treasury_df.sort("date").with_columns(
        pl.col("spread_10y_2y").diff().alias("spread_change"),
    )
    df = df.join(vix_df.select(["date", "vix_return"]), on="date", how="left")
    df = df.join(treasury_df.select(["date", "spread_change"]), on="date", how="left")

    # Load fundamentals
    fund_data = _load_fundamentals_for_clustering(engine, symbols, train_end)

    # Load sector average returns for relative computation
    sector_avgs = _load_sector_avg_returns(engine, train_end)
    symbol_to_sector = {
        row["symbol"]: row["sector"]
        for row in sectors_df.iter_rows(named=True)
    }

    # Per-symbol aggregated features
    features = []
    for symbol in df["symbol"].unique().sort().to_list():
        sym_df = df.filter(pl.col("symbol") == symbol).drop_nulls(subset=["daily_return"])
        if len(sym_df) < 60:
            continue

        returns = sym_df["daily_return"].to_numpy()
        closes = sym_df["close"].to_numpy()

        # --- Behavioral features (original 5) ---

        return_20d = sym_df.with_columns(
            pl.col("daily_return").rolling_mean(20).alias("r20")
        )["r20"].drop_nulls()
        return_20d_mean = float(return_20d.mean()) if len(return_20d) > 0 else 0.0

        tail_returns = returns[-min(252, len(returns)):]
        volatility_60d = float(np.std(tail_returns[-60:])) if len(tail_returns) >= 60 else float(np.std(tail_returns))

        vol_sma = sym_df.with_columns(
            pl.col("volume").rolling_mean(20).alias("vol_sma")
        ).with_columns(
            (pl.col("volume") / pl.col("vol_sma")).alias("rel_vol")
        )["rel_vol"].drop_nulls()
        volume_profile = float(vol_sma.mean()) if len(vol_sma) > 0 else 1.0

        delta = sym_df["daily_return"]
        gain = delta.clip(lower_bound=0).rolling_mean(14)
        loss = (-delta.clip(upper_bound=0)).rolling_mean(14)
        rsi_vals = (100 - 100 / (1 + gain / loss)).drop_nulls()
        rsi_14_mean = float(rsi_vals.mean()) if len(rsi_vals) > 0 else 50.0

        spy_col = sym_df.filter(pl.col("spy_return").is_not_null())
        if len(spy_col) >= 60:
            s_ret = spy_col["daily_return"].tail(60).to_numpy()
            b_ret = spy_col["spy_return"].tail(60).to_numpy()
            cov_val = np.cov(s_ret, b_ret)[0, 1]
            var_b = np.var(b_ret)
            beta_60d = float(cov_val / var_b) if var_b > 0 else 1.0
        else:
            beta_60d = 1.0

        # --- New behavioral features ---

        # momentum_60d: cumulative return over last 60 trading days
        if len(closes) >= 60:
            momentum_60d = float(closes[-1] / closes[-60] - 1)
        else:
            momentum_60d = float(closes[-1] / closes[0] - 1) if len(closes) > 1 else 0.0

        # drawdown_max: maximum drawdown in the training period
        cummax = np.maximum.accumulate(closes)
        drawdowns = (closes - cummax) / cummax
        drawdown_max = float(np.min(drawdowns))

        # --- Macro sensitivity features ---

        # vix_beta: cov(stock_return, vix_return) / var(vix_return)
        vix_col = sym_df.filter(pl.col("vix_return").is_not_null())
        if len(vix_col) >= 60:
            s_ret_v = vix_col["daily_return"].tail(252).to_numpy()
            v_ret = vix_col["vix_return"].tail(252).to_numpy()
            min_len = min(len(s_ret_v), len(v_ret))
            s_ret_v, v_ret = s_ret_v[-min_len:], v_ret[-min_len:]
            var_v = np.var(v_ret)
            vix_beta = float(np.cov(s_ret_v, v_ret)[0, 1] / var_v) if var_v > 0 else 0.0
        else:
            vix_beta = 0.0

        # yield_sensitivity: cov(stock_return, spread_change) / var(spread_change)
        yield_col = sym_df.filter(pl.col("spread_change").is_not_null())
        if len(yield_col) >= 60:
            s_ret_y = yield_col["daily_return"].tail(252).to_numpy()
            sp_chg = yield_col["spread_change"].tail(252).to_numpy()
            min_len = min(len(s_ret_y), len(sp_chg))
            s_ret_y, sp_chg = s_ret_y[-min_len:], sp_chg[-min_len:]
            var_sp = np.var(sp_chg)
            yield_sensitivity = float(np.cov(s_ret_y, sp_chg)[0, 1] / var_sp) if var_sp > 0 else 0.0
        else:
            yield_sensitivity = 0.0

        # --- Sector-relative feature ---
        sector = symbol_to_sector.get(symbol, "Unknown")
        sector_avg = sector_avgs.get(sector, 0.0) or 0.0
        avg_daily_return = float(np.mean(tail_returns)) if len(tail_returns) > 0 else 0.0
        relative_to_sector_avg = avg_daily_return - sector_avg / 100

        # --- Fundamental features ---
        sym_fund = fund_data.get(symbol, {})

        row_data = {
            "symbol": symbol,
            "return_20d_mean": return_20d_mean,
            "volatility_60d": volatility_60d,
            "volume_profile": volume_profile,
            "rsi_14_mean": rsi_14_mean,
            "beta_60d": beta_60d,
            "momentum_60d": momentum_60d,
            "drawdown_max": drawdown_max,
            "vix_beta": vix_beta,
            "yield_sensitivity": yield_sensitivity,
            "relative_to_sector_avg": relative_to_sector_avg,
        }
        for f in _KM_FIELDS:
            row_data[f"km_{f}"] = sym_fund.get(f"km_{f}")
        for f in _FR_FIELDS:
            row_data[f"fr_{f}"] = sym_fund.get(f"fr_{f}")

        features.append(row_data)

    return pl.DataFrame(features)


def _find_optimal_k(
    X: np.ndarray,
    max_k: int,
    min_cluster_size: int,
    min_k: int = 2,
) -> tuple[int, float]:
    """Find the optimal number of clusters via silhouette analysis.

    Args:
        X: Scaled feature matrix.
        max_k: Maximum number of clusters to try.
        min_cluster_size: Minimum samples per cluster.
        min_k: Minimum number of clusters to try.

    Returns:
        Tuple of (best_k, best_silhouette_score).
    """
    n_samples = X.shape[0]
    max_k = min(max_k, n_samples - 1)

    if max_k < 2:
        return 1, 0.0

    best_k = 1
    best_score = 0.0

    for k in range(min_k, max_k + 1):
        if n_samples < k + 1:
            break

        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X)

        # Check minimum cluster size constraint
        counts = np.bincount(labels)
        if np.any(counts < min_cluster_size):
            continue

        score = float(silhouette_score(X, labels))
        if score > best_score:
            best_score = score
            best_k = k

    return best_k, best_score


def run_clustering(
    config: dict,
    reference_date: dt.date | None = None,
) -> tuple[pl.DataFrame, dict]:
    """Assign stocks to clusters using global KMeans.

    Uses PCA for dimensionality reduction and automatic K selection
    via silhouette analysis. Optionally includes one-hot encoded sector
    as a clustering feature.

    Args:
        config: Full config dict.
        reference_date: Date for split computation. Defaults to today.

    Returns:
        Tuple of (result_df, cluster_stats) where result_df has columns
        [symbol, sector, cluster_id, silhouette_score] and cluster_stats
        contains global diagnostics for MLflow logging.
    """
    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))
    split_dates = compute_split_dates(config, reference_date)

    engine = get_engine()
    sectors_df = load_sectors(engine)

    if sectors_df.is_empty():
        raise RuntimeError("No sector data found. Run ingestion first.")

    all_symbols = sectors_df["symbol"].to_list()
    print(f"Computing clustering features for {len(all_symbols)} symbols...")
    feat_df = compute_clustering_features(
        engine, all_symbols, split_dates.train_end, sectors_df
    )

    feat_df = feat_df.join(sectors_df.select(["symbol", "sector"]), on="symbol", how="left")

    feature_cols = [c for c in feat_df.columns if c not in {"symbol", "sector"}]
    print(f"  {len(feature_cols)} clustering features computed")

    n_stocks = len(feat_df)
    X = feat_df.select(feature_cols).to_numpy()

    # Optionally add one-hot encoded sector as clustering features
    if cluster_cfg.include_sector_features:
        sector_dummies = feat_df.select("sector").to_dummies()
        X = np.hstack([X, sector_dummies.to_numpy().astype(float)])
        print(f"  Added {sector_dummies.width} sector one-hot features")

    # Fill NaN with column medians before scaling
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="All-NaN slice encountered")
        col_medians = np.nanmedian(X, axis=0)
    for j in range(X.shape[1]):
        mask = np.isnan(X[:, j])
        X[mask, j] = col_medians[j] if not np.isnan(col_medians[j]) else 0.0

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_scaled = np.nan_to_num(X_scaled, nan=0.0, posinf=0.0, neginf=0.0)

    # PCA dimensionality reduction
    n_components_before = X_scaled.shape[1]
    max_components = min(n_stocks - 1, n_components_before)
    if max_components >= 2:
        pca = PCA(n_components=min(cluster_cfg.pca_variance_ratio, max_components))
        X_reduced = pca.fit_transform(X_scaled)
        variance_explained = float(np.sum(pca.explained_variance_ratio_))
        n_components_after = X_reduced.shape[1]
    else:
        X_reduced = X_scaled
        variance_explained = 1.0
        n_components_after = n_components_before

    if n_stocks < 4:
        # Too few stocks for meaningful clustering
        symbols = feat_df["symbol"].to_list()
        sectors = feat_df["sector"].to_list()
        results = [
            {"symbol": s, "sector": sec, "cluster_id": "Miscellaneous", "silhouette_score": None}
            for s, sec in zip(symbols, sectors)
        ]
        cluster_stats = {
            "n_stocks": n_stocks, "k_selected": 1, "silhouette": 0.0,
            "pca_components": n_components_after, "pca_variance": variance_explained,
        }
        return pl.DataFrame(results), cluster_stats

    # Auto-select optimal K
    best_k, best_sil = _find_optimal_k(
        X_reduced, cluster_cfg.max_clusters, cluster_cfg.min_cluster_size,
        min_k=cluster_cfg.min_clusters,
    )

    kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_reduced)

    # Merge small clusters to nearest centroid
    symbols = feat_df["symbol"].to_list()
    sectors = feat_df["sector"].to_list()
    cluster_counts: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        cluster_counts.setdefault(label, []).append(idx)

    for label, indices in list(cluster_counts.items()):
        if len(indices) < cluster_cfg.min_cluster_size and best_k > 1:
            for idx in indices:
                distances = np.linalg.norm(
                    kmeans.cluster_centers_ - X_reduced[idx], axis=1
                )
                sorted_clusters = np.argsort(distances)
                for candidate in sorted_clusters:
                    if candidate != label:
                        labels[idx] = candidate
                        break

    unique_labels = sorted(set(labels))

    # Compute silhouette AFTER merging so K=1 post-merge reports 0.0
    n_unique = len(unique_labels)
    if n_unique > 1 and n_stocks > n_unique:
        sil_score = float(silhouette_score(X_reduced, labels))
    else:
        sil_score = 0.0

    # Build descriptive cluster names based on sector composition
    cluster_sectors: dict[int, set[str]] = {}
    for idx, label in enumerate(labels):
        cluster_sectors.setdefault(label, set()).add(sectors[idx])

    name_counts: dict[str, int] = {}
    label_to_name: dict[int, str] = {}
    for label in unique_labels:
        label_sectors = sorted(cluster_sectors[label])
        if len(label_sectors) <= 3:
            base_name = "-".join(s.replace(" ", "") for s in label_sectors)
        else:
            base_name = "Miscellaneous"
        count = name_counts.get(base_name, 0)
        name_counts[base_name] = count + 1
        label_to_name[label] = f"{base_name}_{count}"

    # If a base name appeared only once, strip the _0 suffix
    single_names = {name for name, count in name_counts.items() if count == 1}
    for label, name in label_to_name.items():
        base = name.rsplit("_", 1)[0]
        if base in single_names:
            label_to_name[label] = base

    results = []
    for idx, symbol in enumerate(symbols):
        results.append({
            "symbol": symbol,
            "sector": sectors[idx],
            "cluster_id": label_to_name[labels[idx]],
            "silhouette_score": sil_score,
        })

    cluster_stats = {
        "n_stocks": n_stocks,
        "k_selected": len(unique_labels),
        "silhouette": sil_score,
        "pca_components": n_components_after,
        "pca_variance": variance_explained,
    }
    print(f"  Global: K={len(unique_labels)}, silhouette={sil_score:.3f}, "
          f"PCA {n_components_before}->{n_components_after} ({variance_explained:.1%})")

    result_df = pl.DataFrame(results)

    print(f"\nClustering summary ({len(result_df)} stocks, {result_df['cluster_id'].n_unique()} clusters):")
    for cluster_id in result_df["cluster_id"].unique().sort().to_list():
        count = result_df.filter(pl.col("cluster_id") == cluster_id).height
        print(f"  {cluster_id}: {count} stocks")

    return result_df, cluster_stats


def run_sector_clustering(
    config: dict,
    reference_date: dt.date | None = None,
) -> tuple[pl.DataFrame, dict]:
    """Assign stocks to clusters by GICS sector directly (fast, dev mode).

    Instead of computing features and running KMeans, simply use the
    GICS sector as the cluster_id. This is much faster and sufficient
    for development/testing.

    Args:
        config: Full config dict.
        reference_date: Date for split computation. Defaults to today.

    Returns:
        Tuple of (result_df, cluster_stats) with same format as run_clustering().
    """
    engine = get_engine()
    sectors_df = load_sectors(engine)

    if sectors_df.is_empty():
        raise RuntimeError("No sector data found. Run ingestion first.")

    # Use sector as cluster_id directly
    result_df = sectors_df.select(["symbol", "sector"]).with_columns(
        pl.col("sector").alias("cluster_id"),
        pl.lit(0.0).alias("silhouette_score"),
    )

    cluster_stats = {
        "n_stocks": len(result_df),
        "k_selected": result_df["cluster_id"].n_unique(),
        "silhouette": 0.0,
        "pca_components": 0,
        "pca_variance": 0.0,
        "method": "sector",
    }

    print(f"Sector clustering (dev mode): {len(result_df)} stocks, "
          f"{result_df['cluster_id'].n_unique()} clusters (by GICS sector)")

    for cluster_id in result_df["cluster_id"].unique().sort().to_list():
        count = result_df.filter(pl.col("cluster_id") == cluster_id).height
        print(f"  {cluster_id}: {count} stocks")

    return result_df, cluster_stats


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

    output_path = Path(cluster_cfg.output_parquet)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result_df.write_parquet(str(output_path))
    print(f"Saved clusters to {output_path}")

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
    from src.keys import PIPELINE_ENV

    parser = argparse.ArgumentParser(description="Cluster stocks globally")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    args = parser.parse_args()

    config = load_config(args.config)

    # In dev, use sector-based clustering (fast)
    # In prod, use full KMeans clustering
    if PIPELINE_ENV == "dev":
        print("Running in DEV mode: Using sector-based clustering (fast)")
        result_df, cluster_stats = run_sector_clustering(config)
    else:
        print("Running in PROD mode: Using KMeans clustering")
        result_df, cluster_stats = run_clustering(config)

    # Cluster stability check: compare with previous assignments
    cluster_cfg_obj = ClusterConfig.from_dict(config.get("clustering", {}))
    prev_path = Path(cluster_cfg_obj.output_parquet)
    if prev_path.exists():
        prev_df = pl.read_parquet(str(prev_path))
        merged = result_df.select(["symbol", "cluster_id"]).join(
            prev_df.select(["symbol", "cluster_id"]).rename({"cluster_id": "prev_cluster"}),
            on="symbol", how="inner",
        )
        changed = merged.filter(pl.col("cluster_id") != pl.col("prev_cluster"))
        if changed.is_empty():
            print("\nCluster stability: all assignments unchanged.")
        else:
            print(f"\nCluster stability: {len(changed)}/{len(merged)} stocks changed cluster:")
            for row in changed.head(20).iter_rows(named=True):
                print(f"  {row['symbol']}: {row['prev_cluster']} -> {row['cluster_id']}")

    save_clusters(result_df, config)

    # Log to MLflow
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("clustering")
    with mlflow.start_run(run_name="cluster-assignment"):
        cluster_cfg = config.get("clustering", {})
        mlflow.log_params({
            "method": cluster_cfg.get("method", "kmeans"),
            "max_clusters": cluster_cfg.get("max_clusters", 10),
            "min_clusters": cluster_cfg.get("min_clusters", 3),
            "include_sector_features": cluster_cfg.get("include_sector_features", True),
            "min_cluster_size": cluster_cfg.get("min_cluster_size", 10),
            "pca_variance_ratio": cluster_cfg.get("pca_variance_ratio", 0.95),
            "n_stocks": len(result_df),
            "n_clusters": result_df["cluster_id"].n_unique(),
        })

        mlflow.log_metrics({
            "k_selected": cluster_stats["k_selected"],
            "silhouette": cluster_stats["silhouette"],
            "pca_components": cluster_stats["pca_components"],
            "pca_variance": cluster_stats["pca_variance"],
        })

        mlflow.log_artifact(cluster_cfg.get("output_parquet", "data/clusters.parquet"))
    print("Logged clustering results to MLflow")


if __name__ == "__main__":
    main()
