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
import traceback
from pathlib import Path

import mlflow
import numpy as np
import polars as pl
from scipy.optimize import minimize
from sqlalchemy import text

from src.config import (
    PortfolioProfileConfig,
    compute_split_dates,
    load_config,
)
from src.db import get_engine, in_params
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
    ph, params = in_params("s", symbols)
    params["start_date"] = start_date
    params["end_date"] = end_date
    query = text(f"""
        SELECT date, symbol, close FROM ohlcv_daily
        WHERE symbol IN ({ph})
          AND date >= :start_date AND date <= :end_date
        ORDER BY symbol, date
    """).bindparams(**params)
    with engine.connect() as conn:
        df = pl.read_database(query, conn)

    if df.is_empty():
        return pl.DataFrame(schema={"date": pl.Date, "symbol": pl.Utf8, "daily_return": pl.Float64})

    df = (
        df.sort(["symbol", "date"])
        .with_columns(
            pl.col("close").pct_change().over("symbol").alias("daily_return"),
        )
        .drop_nulls(subset=["daily_return"])
        .select(["date", "symbol", "daily_return"])
    )

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
    query = text("""
        SELECT date, close FROM ohlcv_daily
        WHERE symbol = :benchmark
          AND date >= :start_date AND date <= :end_date
        ORDER BY date
    """).bindparams(benchmark=benchmark, start_date=start_date, end_date=end_date)
    with engine.connect() as conn:
        df = pl.read_database(query, conn)
    if df.is_empty():
        return np.array([0.0])

    returns = (
        df.sort("date")
        .with_columns(pl.col("close").pct_change().alias("ret"))
        .drop_nulls(subset=["ret"])["ret"]
        .to_numpy()
    )

    return returns


def _enforce_sector_cap(
    weights: np.ndarray,
    symbols: list[str],
    sector_map: dict[str, str],
    max_sector_weight: float,
    min_pos: float,
    max_pos: float,
    max_iterations: int = 100,
    tol: float = 1e-9,
) -> np.ndarray:
    """Project weights onto the feasible set with both per-position and per-sector caps.

    The feasible set enforced here:
      * ``sum(weights) == 1``
      * ``min_pos <= weights[i] <= max_pos`` for all i
      * ``sum(weights[i] for i in sector) <= max_sector_weight`` for all sectors

    The projection iteratively clips over-cap weights/sectors and redistributes the
    removed mass to positions with headroom (respecting both the per-position
    ``max_pos`` and the per-sector ``max_sector_weight``). This is a hard guarantee
    that complements SLSQP's inequality constraints and also saves the equal-weight
    fallback path (see BEC-40).

    Infeasibility is handled gracefully: if the inputs cannot satisfy all three
    invariants simultaneously (e.g. ``n * max_pos < 1`` or the cap is looser than
    the floor), the function returns the closest feasible point it can reach and
    renormalizes to sum to 1.

    Args:
        weights: Input weight vector (not modified in place).
        symbols: Symbol list aligned with ``weights``.
        sector_map: Mapping from symbol to sector name. Unknown symbols are bucketed.
        max_sector_weight: Per-sector cap (e.g. 0.20).
        min_pos: Minimum per-position weight.
        max_pos: Maximum per-position weight.
        max_iterations: Fixed-point iteration budget.
        tol: Convergence / feasibility tolerance.

    Returns:
        Projected weights as a fresh ``np.ndarray``.
    """
    n = len(symbols)
    if n == 0:
        return np.array(weights, dtype=float).copy()

    w = np.array(weights, dtype=float).copy()

    # Group indices by sector
    sectors: dict[str, list[int]] = {}
    for i, s in enumerate(symbols):
        sec = sector_map.get(s, "Unknown")
        sectors.setdefault(sec, []).append(i)

    # Effective per-position upper bound: the smaller of max_pos and the per-sector cap.
    # If a position is the only one in its sector, the sector cap caps it directly.
    effective_max = np.full(n, max_pos, dtype=float)
    for sec, idx in sectors.items():
        # Single-name sectors: the per-position cap cannot exceed the sector cap.
        if len(idx) == 1:
            effective_max[idx[0]] = min(effective_max[idx[0]], max_sector_weight)

    # If total floor already exceeds 1, we're infeasible; just renormalize and return.
    if n * min_pos > 1.0 + tol:
        w = np.full(n, 1.0 / n)
        return w

    # Main projection loop: at each iteration, clamp to bounds and sector caps, then
    # push any removed mass into positions with remaining headroom.
    for _ in range(max_iterations):
        # Clamp to per-position bounds
        w = np.clip(w, min_pos, effective_max)

        # Clamp over-cap sectors by scaling down the headroom-above-floor uniformly
        for sec, idx in sectors.items():
            sec_total = float(w[idx].sum())
            if sec_total <= max_sector_weight + tol:
                continue
            floor_total = len(idx) * min_pos
            target = max(floor_total, max_sector_weight)
            headroom = w[idx] - min_pos
            headroom_sum = float(headroom.sum())
            if headroom_sum <= tol:
                continue
            reduction = sec_total - target
            scale = max(0.0, 1.0 - reduction / headroom_sum)
            w[idx] = min_pos + headroom * scale

        total = float(w.sum())
        diff = 1.0 - total
        if abs(diff) <= tol:
            break

        if diff > 0:
            # Need to add mass. Distribute to positions/sectors with headroom.
            sector_room = {
                sec: max(0.0, max_sector_weight - float(w[idx].sum()))
                for sec, idx in sectors.items()
            }
            headrooms = np.zeros(n)
            for i in range(n):
                sec = sector_map.get(symbols[i], "Unknown")
                headrooms[i] = min(effective_max[i] - w[i], sector_room.get(sec, 0.0))
                if headrooms[i] < 0:
                    headrooms[i] = 0.0
            total_room = float(headrooms.sum())
            if total_room <= tol:
                # Nothing can absorb more mass — infeasible, exit.
                break
            w = w + headrooms / total_room * min(diff, total_room)
        else:
            # Need to remove mass. Scale down from headroom-above-floor globally.
            headroom = np.maximum(0.0, w - min_pos)
            headroom_sum = float(headroom.sum())
            if headroom_sum <= tol:
                break
            reduction = min(-diff, headroom_sum)
            scale = 1.0 - reduction / headroom_sum
            w = min_pos + headroom * scale

    # Final safety: if we still don't sum to 1, do a last renormalization.
    total = float(w.sum())
    if total > 0 and abs(total - 1.0) > tol:
        w = w / total
    return w


def _build_returns_matrix(
    returns_df: pl.DataFrame,
    symbols: list[str],
) -> np.ndarray:
    """Build a (n_days, n_symbols) returns matrix from long-format DataFrame.

    Returns:
        Returns matrix as numpy array with shape (n_days, n_symbols).
    """
    pivot = returns_df.pivot(on="symbol", index="date", values="daily_return").sort("date")

    # Keep only requested symbols that exist in the data
    available = [s for s in symbols if s in pivot.columns]
    if not available:
        return np.array([]).reshape(0, 0)

    matrix = pivot.select(available).to_numpy()

    # Replace NaN with 0
    matrix = np.nan_to_num(matrix, nan=0.0)

    return matrix


def optimize_portfolio(
    predictions: pl.DataFrame,
    returns_df: pl.DataFrame,
    profile_config: PortfolioProfileConfig,
    constraints: dict,
    benchmark_returns: np.ndarray | None = None,
    sectors_df: pl.DataFrame | None = None,
    commission_pct: float = 0.001,
    rebalance_frequency_days: int = 21,
    turnover_penalty: float = 0.0,
    previous_weights: dict[str, float] | None = None,
) -> pl.DataFrame:
    """Optimize portfolio weights for a single profile.

    Args:
        predictions: DataFrame with columns [symbol, cluster_id, prob_up].
        returns_df: Historical daily returns [date, symbol, daily_return].
        profile_config: Profile configuration (metrics, constraints).
        constraints: Global constraints dict.
        benchmark_returns: Optional benchmark returns for information ratio.
        sectors_df: Optional DataFrame with [symbol, sector] for sector constraints.
        turnover_penalty: Penalty factor for weight changes from previous allocation.
        previous_weights: Previous portfolio weights {symbol: weight} for turnover penalty.

    Returns:
        DataFrame with columns [symbol, weight, cluster_id, prob_up].
    """
    empty_schema = {
        "symbol": pl.Utf8,
        "weight": pl.Float64,
        "cluster_id": pl.Utf8,
        "prob_up": pl.Float64,
    }

    # Filter by min_prob_up threshold
    candidates = predictions.filter(pl.col("prob_up") >= profile_config.min_prob_up)

    if candidates.is_empty():
        return pl.DataFrame(schema=empty_schema)

    # Sector-balanced selection: cap per-sector contributions BEFORE global top-K
    # so one mis-calibrated sector can't dominate the candidate pool and make the
    # SLSQP sector constraint trivially satisfied (see BEC-35).
    if sectors_df is not None and not sectors_df.is_empty():
        # per_sector_cap = max(1, floor(max_positions * max_sector_weight))
        per_sector_cap = max(
            1,
            int(profile_config.max_positions * profile_config.max_sector_weight),
        )
        candidates = (
            candidates.join(sectors_df, on="symbol", how="left")
            .with_columns(pl.col("sector").fill_null("Unknown"))
            .sort("prob_up", descending=True)
            .group_by("sector", maintain_order=True)
            .head(per_sector_cap)
            .sort("prob_up", descending=True)
            .head(profile_config.max_positions)
            .drop("sector")
        )
    else:
        # No sector info — fall back to global top-K by prob_up
        candidates = candidates.sort("prob_up", descending=True).head(profile_config.max_positions)

    symbols = candidates["symbol"].to_list()
    n = len(symbols)

    if n == 0:
        return pl.DataFrame(schema=empty_schema)

    # Build returns matrix for candidates
    returns_matrix = _build_returns_matrix(returns_df, symbols)

    # Build sector map once so fallback paths can enforce the cap too.
    sector_map: dict[str, str] = {}
    if sectors_df is not None and not sectors_df.is_empty():
        sector_map = dict(
            zip(
                sectors_df["symbol"].to_list(),
                sectors_df["sector"].to_list(),
            )
        )

    max_pos = constraints.get("max_single_position", 0.10)
    min_pos = constraints.get("min_single_position", 0.01)

    if returns_matrix.size == 0 or returns_matrix.shape[0] < 10:
        # Not enough data — equal weight fallback
        weights = np.ones(n) / n
    else:
        # Build previous weight vector for turnover penalty
        prev_w = np.zeros(n)
        if turnover_penalty > 0 and previous_weights:
            for i, s in enumerate(symbols):
                prev_w[i] = previous_weights.get(s, 0.0)

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
            obj = -(0.8 * primary_val + 0.2 * comp_val)

            # Turnover penalty: penalize large changes from previous allocation
            if turnover_penalty > 0:
                obj += turnover_penalty * np.sum(np.abs(w - prev_w))

            return obj

        # Constraints
        bounds = [(min_pos, max_pos) for _ in range(n)]
        constraint_list = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},  # weights sum to 1
        ]

        # Sector constraints
        if sector_map:
            sectors_in_portfolio = set(sector_map.get(s, "Unknown") for s in symbols)
            for sector in sectors_in_portfolio:
                sector_indices = [
                    i for i, s in enumerate(symbols) if sector_map.get(s, "Unknown") == sector
                ]
                if sector_indices:
                    constraint_list.append(
                        {
                            "type": "ineq",
                            "fun": lambda w, idx=sector_indices: (
                                profile_config.max_sector_weight - sum(w[i] for i in idx)
                            ),
                        }
                    )

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

    # Hard invariant: enforce the per-profile sector cap even when SLSQP returned
    # a slightly-infeasible solution, the fallback equal-weight path was taken, or
    # the pre-selection left more symbols in one sector than the cap admits.
    # See BEC-40.
    if sector_map:
        weights = _enforce_sector_cap(
            weights=weights,
            symbols=symbols,
            sector_map=sector_map,
            max_sector_weight=profile_config.max_sector_weight,
            min_pos=min_pos,
            max_pos=max_pos,
        )

    # Build result DataFrame
    rows = []
    for i, symbol in enumerate(symbols):
        row = candidates.filter(pl.col("symbol") == symbol).row(0, named=True)
        rows.append(
            {
                "symbol": symbol,
                "weight": float(weights[i]),
                "cluster_id": row["cluster_id"],
                "prob_up": row["prob_up"],
            }
        )

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

    if not Path(pred_path).exists():
        print(f"ERROR: Predictions file not found: {pred_path}")
        print("This usually means no models were trained successfully.")
        print("Please run training first: make train")
        return {}

    predictions = pl.read_parquet(pred_path)

    if predictions.is_empty():
        print("No predictions found. Run aggregation first.")
        return {}

    # Load historical returns from the LAST YEAR of training period (not validation)
    # Using validation returns would be look-ahead bias: optimizing weights on the same
    # data used to evaluate the model (Grinold & Kahn 2000)
    import datetime as dt

    train_returns_start = split_dates.train_end - dt.timedelta(days=365)
    all_symbols = predictions["symbol"].to_list()
    returns_df = load_historical_returns(all_symbols, train_returns_start, split_dates.train_end)

    # Load benchmark returns from same period
    benchmark_returns = load_benchmark_returns(
        benchmark_symbol, train_returns_start, split_dates.train_end
    )

    # Load sector data for constraints
    engine = get_engine()
    sectors_df = pl.read_database("SELECT symbol, sector FROM stock_sectors", engine)

    # Load previous allocations for turnover penalty
    turnover_penalty = float(constraints.get("turnover_penalty", 0.0))
    previous_allocations: dict[str, dict[str, float]] = {}
    if turnover_penalty > 0:
        prev_path = (
            Path(agg_cfg.get("output_parquet", "data/predictions.parquet")).parent
            / "portfolios.parquet"
        )
        if prev_path.exists():
            try:
                prev_df = pl.read_parquet(str(prev_path))
                for pname in prev_df["profile"].unique().to_list():
                    profile_rows = prev_df.filter(pl.col("profile") == pname)
                    previous_allocations[pname] = dict(
                        zip(
                            profile_rows["symbol"].to_list(),
                            profile_rows["weight"].to_list(),
                        )
                    )
                print(
                    "  Loaded previous allocations for turnover penalty "
                    f"(lambda={turnover_penalty})"
                )
            except Exception:
                pass

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
            turnover_penalty=turnover_penalty,
            previous_weights=previous_allocations.get(profile_name),
        )

        if not allocation.is_empty():
            allocation = allocation.with_columns(pl.lit(profile_name).alias("profile"))
            print(
                f"  {profile_name}: {len(allocation)} positions, "
                f"max weight: {allocation['weight'].max():.2%}, "
                f"min weight: {allocation['weight'].min():.2%}"
            )

            # Validation metric
            if returns_df.height > 0:
                syms = allocation["symbol"].to_list()
                wts = allocation["weight"].to_numpy()
                ret_matrix = _build_returns_matrix(returns_df, syms)
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
        # Write empty parquet so downstream stages can detect and handle gracefully
        empty = pl.DataFrame(
            schema={
                "symbol": pl.Utf8,
                "weight": pl.Float64,
                "cluster_id": pl.Utf8,
                "prob_up": pl.Float64,
                "profile": pl.Utf8,
            }
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        empty.write_parquet(output_path)
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
        try:
            for profile_name, allocation in results.items():
                if not allocation.is_empty():
                    mlflow.log_metric(f"{profile_name}_n_positions", len(allocation))
                    mlflow.log_metric(
                        f"{profile_name}_max_weight", float(allocation["weight"].max())
                    )
            if Path(output_path).exists():
                mlflow.log_artifact(output_path)
        except Exception as e:
            mlflow.set_tag("error_type", type(e).__name__)
            mlflow.set_tag("error_message", str(e)[:5000])
            mlflow.set_tag("error_traceback", traceback.format_exc()[:5000])
            raise
    print("Logged portfolio results to MLflow")


if __name__ == "__main__":
    main()
