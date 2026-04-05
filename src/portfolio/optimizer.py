"""Portfolio optimization for multiple risk profiles (Stage 4).

Constructs three portfolios (aggressive, moderate, conservative) by
optimizing weights to maximize each profile's primary metric, estimated
from historical validation-period returns.

Usage:
    uv run python -m src.portfolio.optimizer
    uv run python -m src.portfolio.optimizer --config configs/default.yaml
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import mlflow
import numpy as np
import polars as pl
from scipy.optimize import minimize
from sqlalchemy import text

from src.config import (
    ClusterConfig,
    PortfolioProfileConfig,
    compute_split_dates,
    load_config,
)
from src.db import get_engine
from src.keys import MLFLOW_TRACKING_URI
from src.portfolio.metrics import (
    calmar_ratio,
    compute_all_metrics,
    information_ratio,
    omega_ratio,
    sharpe_ratio,
    sortino_ratio,
)

METRIC_FUNCTIONS = {
    "sharpe": lambda r, eq, br: sharpe_ratio(r),
    "sortino": lambda r, eq, br: sortino_ratio(r),
    "omega": lambda r, eq, br: omega_ratio(r),
    "calmar": lambda r, eq, br: calmar_ratio(r, eq),
    "information": lambda r, eq, br: information_ratio(r, br) if br is not None else 0.0,
}


def load_historical_returns(
    symbols: list[str],
    start_date: dt.date,
    end_date: dt.date,
) -> pl.DataFrame:
    """Load daily returns for symbols from the database.

    Args:
        symbols: List of ticker symbols.
        start_date: Start date for the period.
        end_date: End date for the period.

    Returns:
        DataFrame with columns [date, symbol, daily_return].
    """
    engine = get_engine()
    placeholders = ", ".join(f"'{s}'" for s in symbols)
    query = f"""
        SELECT date, symbol, close FROM ohlcv_daily
        WHERE symbol IN ({placeholders})
          AND date >= '{start_date}' AND date <= '{end_date}'
        ORDER BY symbol, date
    """
    df = pl.read_database(query, engine)

    if df.is_empty():
        return pl.DataFrame(schema={"date": pl.Date, "symbol": pl.Utf8, "daily_return": pl.Float64})

    df = df.sort(["symbol", "date"]).with_columns(
        pl.col("close").pct_change().over("symbol").alias("daily_return"),
    ).drop_nulls(subset=["daily_return"]).select(["date", "symbol", "daily_return"])

    return df


def load_benchmark_returns(
    benchmark: str,
    start_date: dt.date,
    end_date: dt.date,
) -> np.ndarray:
    """Load benchmark daily returns.

    Args:
        benchmark: Benchmark symbol (e.g. "SPY").
        start_date: Start date.
        end_date: End date.

    Returns:
        Array of daily returns.
    """
    engine = get_engine()
    query = f"""
        SELECT date, close FROM ohlcv_daily
        WHERE symbol = '{benchmark}'
          AND date >= '{start_date}' AND date <= '{end_date}'
        ORDER BY date
    """
    df = pl.read_database(query, engine)
    if df.is_empty():
        return np.array([0.0])

    returns = df.sort("date").with_columns(
        pl.col("close").pct_change().alias("ret")
    ).drop_nulls(subset=["ret"])["ret"].to_numpy()

    return returns


def _build_returns_matrix(
    returns_df: pl.DataFrame,
    symbols: list[str],
) -> tuple[np.ndarray, list[str]]:
    """Build a (n_days, n_symbols) returns matrix from long-format DataFrame.

    Returns:
        Tuple of (returns_matrix, dates_list).
    """
    pivot = returns_df.pivot(on="symbol", index="date", values="daily_return").sort("date")

    # Keep only requested symbols that exist in the data
    available = [s for s in symbols if s in pivot.columns]
    if not available:
        return np.array([]).reshape(0, 0), []

    dates = pivot["date"].to_list()
    matrix = pivot.select(available).to_numpy()

    # Replace NaN with 0
    matrix = np.nan_to_num(matrix, nan=0.0)

    return matrix, dates


def optimize_portfolio(
    predictions: pl.DataFrame,
    returns_df: pl.DataFrame,
    profile_config: PortfolioProfileConfig,
    constraints: dict,
    benchmark_returns: np.ndarray | None = None,
    sectors_df: pl.DataFrame | None = None,
    commission_pct: float = 0.001,
    rebalance_frequency_days: int = 21,
) -> pl.DataFrame:
    """Optimize portfolio weights for a single profile.

    Args:
        predictions: DataFrame with columns [symbol, cluster_id, prob_up].
        returns_df: Historical daily returns [date, symbol, daily_return].
        profile_config: Profile configuration (metrics, constraints).
        constraints: Global constraints dict.
        benchmark_returns: Optional benchmark returns for information ratio.
        sectors_df: Optional DataFrame with [symbol, sector] for sector constraints.

    Returns:
        DataFrame with columns [symbol, weight, cluster_id, prob_up].
    """
    empty_schema = {
        "symbol": pl.Utf8, "weight": pl.Float64,
        "cluster_id": pl.Utf8, "prob_up": pl.Float64,
    }

    # Filter by min_prob_up threshold
    candidates = predictions.filter(pl.col("prob_up") >= profile_config.min_prob_up)

    if candidates.is_empty():
        return pl.DataFrame(schema=empty_schema)

    # Limit to max_positions (sorted by prob_up)
    candidates = candidates.sort("prob_up", descending=True).head(profile_config.max_positions)
    symbols = candidates["symbol"].to_list()
    n = len(symbols)

    if n == 0:
        return pl.DataFrame(schema=empty_schema)

    # Build returns matrix for candidates
    returns_matrix, _ = _build_returns_matrix(returns_df, symbols)

    if returns_matrix.size == 0 or returns_matrix.shape[0] < 10:
        # Not enough data — equal weight fallback
        weights = np.ones(n) / n
    else:
        # Optimization objective: maximize primary metric (long-only)
        def _objective(w: np.ndarray) -> float:
            portfolio_returns = returns_matrix[:, :n] @ w
            # Deduct transaction costs at each rebalance period
            if commission_pct > 0 and rebalance_frequency_days > 0:
                for day in range(0, len(portfolio_returns), rebalance_frequency_days):
                    turnover = 2.0 * np.sum(np.abs(w))  # round-trip estimate
                    portfolio_returns[day] -= commission_pct * turnover
            equity = np.cumprod(1 + portfolio_returns) * 100000
            primary_fn = METRIC_FUNCTIONS[profile_config.primary_metric]
            comp_fn = METRIC_FUNCTIONS[profile_config.complementary_metric]

            primary_val = primary_fn(portfolio_returns, equity, benchmark_returns)
            comp_val = comp_fn(portfolio_returns, equity, benchmark_returns)

            # Weighted objective: 80% primary + 20% complementary
            return -(0.8 * primary_val + 0.2 * comp_val)

        # Constraints
        max_pos = constraints.get("max_single_position", 0.10)
        min_pos = constraints.get("min_single_position", 0.01)

        bounds = [(min_pos, max_pos) for _ in range(n)]
        constraint_list = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},  # weights sum to 1
        ]

        # Sector constraints
        if sectors_df is not None:
            sector_map = dict(zip(
                sectors_df["symbol"].to_list(),
                sectors_df["sector"].to_list(),
            ))
            sectors_in_portfolio = set(sector_map.get(s, "Unknown") for s in symbols)
            for sector in sectors_in_portfolio:
                sector_indices = [
                    i for i, s in enumerate(symbols)
                    if sector_map.get(s, "Unknown") == sector
                ]
                if sector_indices:
                    constraint_list.append({
                        "type": "ineq",
                        "fun": lambda w, idx=sector_indices: (
                            profile_config.max_sector_weight - sum(w[i] for i in idx)
                        ),
                    })

        # Initial guess: equal weight
        w0 = np.ones(n) / n

        result = minimize(
            _objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraint_list,
            options={"maxiter": 500, "ftol": 1e-8},
        )

        weights = result.x if result.success else w0
        # Normalize to sum to 1
        weights = weights / weights.sum()

    # Build result DataFrame
    rows = []
    for i, symbol in enumerate(symbols):
        row = candidates.filter(pl.col("symbol") == symbol).row(0, named=True)
        rows.append({
            "symbol": symbol,
            "weight": float(weights[i]),
            "cluster_id": row["cluster_id"],
            "prob_up": row["prob_up"],
        })

    return pl.DataFrame(rows)


def optimize_all_portfolios(config: dict) -> dict[str, pl.DataFrame]:
    """Optimize portfolios for all profiles.

    Args:
        config: Full config dict.

    Returns:
        Dict mapping profile name to allocation DataFrame.
    """
    split_dates = compute_split_dates(config)
    portfolio_cfg = config.get("portfolio", {})
    profiles = portfolio_cfg.get("profiles", {})
    constraints = portfolio_cfg.get("constraints", {})
    benchmark_symbol = portfolio_cfg.get("benchmark", "SPY")

    # Load predictions
    agg_cfg = config.get("aggregation", {})
    pred_path = agg_cfg.get("output_parquet", "data/predictions.parquet")
    predictions = pl.read_parquet(pred_path)

    if predictions.is_empty():
        print("No predictions found. Run aggregation first.")
        return {}

    # Load historical returns from validation period (for optimization estimation)
    all_symbols = predictions["symbol"].to_list()
    returns_df = load_historical_returns(
        all_symbols, split_dates.val_start, split_dates.val_end
    )

    # Load benchmark returns
    benchmark_returns = load_benchmark_returns(
        benchmark_symbol, split_dates.val_start, split_dates.val_end
    )

    # Load sector data for constraints
    engine = get_engine()
    sectors_df = pl.read_database(
        "SELECT symbol, sector FROM stock_sectors", engine
    )

    results = {}
    for profile_name, profile_dict in profiles.items():
        print(f"\nOptimizing {profile_name} portfolio...")
        profile_config = PortfolioProfileConfig.from_dict(profile_dict)

        bt_cfg = config.get("backtest", {})
        allocation = optimize_portfolio(
            predictions=predictions,
            returns_df=returns_df,
            profile_config=profile_config,
            constraints=constraints,
            benchmark_returns=benchmark_returns,
            sectors_df=sectors_df,
            commission_pct=bt_cfg.get("commission_pct", 0.001),
            rebalance_frequency_days=constraints.get("rebalance_frequency_days", 21),
        )

        if not allocation.is_empty():
            allocation = allocation.with_columns(
                pl.lit(profile_name).alias("profile")
            )
            print(f"  {profile_name}: {len(allocation)} positions, "
                  f"max weight: {allocation['weight'].max():.2%}, "
                  f"min weight: {allocation['weight'].min():.2%}")

            # Validation metric
            if returns_df.height > 0:
                syms = allocation["symbol"].to_list()
                wts = allocation["weight"].to_numpy()
                ret_matrix, _ = _build_returns_matrix(returns_df, syms)
                if ret_matrix.size > 0 and ret_matrix.shape[1] == len(wts):
                    port_ret = ret_matrix @ wts
                    equity = np.cumprod(1 + port_ret) * 100000
                    all_metrics = compute_all_metrics(port_ret, equity, benchmark_returns)
                    for k, v in all_metrics.items():
                        print(f"    {k}: {v:.4f}")
        else:
            print(f"  {profile_name}: No positions (no candidates met criteria)")

        results[profile_name] = allocation

    return results


def save_portfolios(
    results: dict[str, pl.DataFrame],
    config: dict,
    run_date: dt.date | None = None,
) -> None:
    """Save portfolio allocations to database and parquet.

    Args:
        results: Dict mapping profile name to allocation DataFrame.
        config: Full config dict.
        run_date: Date for the run. Defaults to today.
    """
    run_date = run_date or dt.date.today()
    output_path = config.get("portfolio", {}).get("output_parquet", "data/portfolios.parquet")

    # Combine all profiles
    all_dfs = [df for df in results.values() if not df.is_empty()]
    if not all_dfs:
        print("No portfolio allocations to save.")
        return

    combined = pl.concat(all_dfs)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    combined.write_parquet(output_path)
    print(f"\nSaved portfolios to {output_path}")

    # Save to database
    engine = get_engine()
    with engine.begin() as conn:
        for row in combined.iter_rows(named=True):
            stmt = text("""
                INSERT INTO portfolio_allocations
                    (run_date, profile, symbol, weight, prob_up, cluster_id)
                VALUES
                    (:run_date, :profile, :symbol, :weight, :prob_up, :cluster_id)
                ON CONFLICT (run_date, profile, symbol) DO UPDATE SET
                    weight = EXCLUDED.weight,
                    prob_up = EXCLUDED.prob_up,
                    cluster_id = EXCLUDED.cluster_id
            """)
            conn.execute(stmt, {**row, "run_date": run_date})
    print(f"Saved {len(combined)} allocations to database")


def main() -> None:
    """Run portfolio optimization pipeline."""
    parser = argparse.ArgumentParser(description="Optimize portfolios")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    args = parser.parse_args()

    config = load_config(args.config)
    results = optimize_all_portfolios(config)

    if not results:
        return

    save_portfolios(results, config)

    # Log to MLflow
    output_path = config.get("portfolio", {}).get("output_parquet", "data/portfolios.parquet")
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("portfolio-optimization")
    with mlflow.start_run(run_name="portfolio-design"):
        for profile_name, allocation in results.items():
            if not allocation.is_empty():
                mlflow.log_metric(f"{profile_name}_n_positions", len(allocation))
                mlflow.log_metric(f"{profile_name}_max_weight", float(allocation["weight"].max()))
        if Path(output_path).exists():
            mlflow.log_artifact(output_path)
    print("Logged portfolio results to MLflow")


if __name__ == "__main__":
    main()
