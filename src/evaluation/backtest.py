"""Portfolio-level backtesting with risk management and regime analysis (Stage 5).

Simulates long-only portfolio performance day by day for each (profile, regime)
combination, computes all risk metrics.

Usage:
    uv run python -m src.evaluation.backtest
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
from dataclasses import dataclass, field
from pathlib import Path

import mlflow
import numpy as np
import polars as pl
from sqlalchemy import text

from src.config import compute_split_dates, load_config
from src.db import get_engine, in_params
from src.evaluation.regime import detect_regimes
from src.keys import MLFLOW_TRACKING_URI
from src.portfolio.metrics import compute_all_metrics

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """An open long position in a single stock."""

    symbol: str
    entry_price: float
    entry_date: dt.date
    shares: float
    cost_basis: float


# Minimum sample thresholds below which risk-adjusted metrics are unreliable.
# Keep in sync with docs and report legend.
MIN_TRADES_FOR_METRICS = 30
MIN_DRAWDOWN_PCT_FOR_METRICS = 0.005  # 0.5% expressed as fraction
# Minimum number of trading days required to safely annualize benchmark returns.
# Below this threshold (e.g., a 15-25-day bear window), naive (1+r)^(252/n)-1
# explodes a small positive period return into thousands-of-percent annual figures.
MIN_ANNUALIZATION_WINDOW = 63  # ~3 months


@dataclass
class BacktestResult:
    """Container for backtest metrics."""

    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    omega_ratio: float = 0.0
    info_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    num_trades: int = 0
    avg_trade_return: float = 0.0
    final_value: float = 0.0
    circuit_breaker_triggered: bool = False
    equity_curve: list[float] = field(default_factory=list)
    profile: str = ""
    regime: str = ""
    benchmark_annual_return: float = 0.0
    tracking_error: float = 0.0
    insufficient_sample: bool = False


def run_portfolio_backtest(
    allocations: pl.DataFrame,
    prices: pl.DataFrame,
    config: dict,
    benchmark_returns: np.ndarray | None = None,
) -> BacktestResult:
    """Run a long-only portfolio backtest with risk management.

    Args:
        allocations: DataFrame with columns [symbol, weight].
        prices: DataFrame with columns [date, symbol, close].
        config: Backtest config section.
        benchmark_returns: Optional benchmark daily returns.
    """
    risk_cfg = config.get("risk", {})
    initial_capital = config.get("initial_capital", 100000)
    commission_pct = config.get("commission_pct", 0.001)
    slippage_bps = config.get("slippage_bps", 5)
    base_slippage_pct = slippage_bps / 10_000
    volume_impact_factor = config.get("volume_impact_factor", 0.0)
    stop_loss = risk_cfg.get("position_stop_loss", 0.08)
    take_profit = risk_cfg.get("position_take_profit", 0.50)
    max_dd_limit = risk_cfg.get("max_drawdown_limit", 0.25)
    cooldown_days = risk_cfg.get("cooldown_days", 2)
    rebalance_days = config.get("rebalance_frequency_days", 21)
    max_position_drift = config.get("max_position_drift", 0.0)

    if allocations.is_empty() or prices.is_empty():
        return BacktestResult(final_value=initial_capital)

    # Build allocation map
    alloc_map: dict[str, float] = {}
    for row in allocations.iter_rows(named=True):
        alloc_map[row["symbol"]] = row["weight"]

    dates = sorted(prices["date"].unique().to_list())
    symbols_in_portfolio = list(alloc_map.keys())

    # Pre-compute average daily volume (ADV) per symbol for volume-dependent slippage
    adv_map: dict[str, float] = {}
    if volume_impact_factor > 0 and "volume" in prices.columns:
        for sym in symbols_in_portfolio:
            sym_vol = prices.filter(pl.col("symbol") == sym)["volume"]
            adv_map[sym] = float(sym_vol.mean()) if len(sym_vol) > 0 else 1e9

    def _get_slippage(symbol: str, position_value: float) -> float:
        """Compute slippage: base + volume-dependent impact (Almgren & Chriss 2001)."""
        if volume_impact_factor <= 0 or symbol not in adv_map:
            return base_slippage_pct
        adv = adv_map[symbol]
        if adv <= 0:
            return base_slippage_pct
        # impact = factor * sqrt(position_value / ADV_dollar)
        # Use close price approximation for ADV dollar value
        impact = volume_impact_factor * (position_value / (adv * 50)) ** 0.5  # rough ADV$
        return base_slippage_pct + impact

    cash = initial_capital
    positions: dict[str, Position] = {}
    equity_curve = []
    daily_returns_list = []
    trade_returns: list[float] = []
    peak_equity = initial_capital
    circuit_breaker = False
    cooldown_until: dt.date | None = None
    days_since_rebalance = 0

    # Open positions on day 1 based on allocations
    first_day = dates[0] if dates else None

    for day in dates:
        # Check for drift-based rebalancing (event-driven)
        drift_triggered = False
        if max_position_drift > 0 and day != first_day and not circuit_breaker and positions:
            total_value = cash + sum(
                pos.shares
                * prices.filter((pl.col("date") == day) & (pl.col("symbol") == sym))["close"][0]
                for sym, pos in positions.items()
                if not prices.filter((pl.col("date") == day) & (pl.col("symbol") == sym)).is_empty()
            )
            if total_value > 0:
                for sym, pos in positions.items():
                    price_row = prices.filter((pl.col("date") == day) & (pl.col("symbol") == sym))
                    if price_row.is_empty():
                        continue
                    actual_weight = (pos.shares * price_row["close"][0]) / total_value
                    target_weight = alloc_map.get(sym, 0.0)
                    if abs(actual_weight - target_weight) > max_position_drift:
                        drift_triggered = True
                        break

        # Periodic or drift-triggered rebalancing to target weights
        should_rebalance = (
            not circuit_breaker
            and positions
            and day != first_day
            and ((rebalance_days > 0 and days_since_rebalance >= rebalance_days) or drift_triggered)
        )
        if should_rebalance:
            # Close all positions
            for sym, pos in list(positions.items()):
                price_row = prices.filter((pl.col("date") == day) & (pl.col("symbol") == sym))
                if not price_row.is_empty():
                    slp = _get_slippage(sym, pos.shares * price_row["close"][0])
                    proceeds = _close_position(pos, price_row["close"][0], commission_pct, slp)
                    trade_returns.append((proceeds - pos.cost_basis) / pos.cost_basis)
                    cash += proceeds
            positions.clear()

            # Re-open with target weights using current equity
            current_equity = cash
            for symbol, weight in alloc_map.items():
                price_row = prices.filter((pl.col("date") == day) & (pl.col("symbol") == symbol))
                if price_row.is_empty() or weight <= 0:
                    continue
                price = price_row["close"][0]
                if price <= 0:
                    continue
                capital_for_pos = current_equity * weight
                slp = _get_slippage(symbol, capital_for_pos)
                entry_price = price * (1 + slp)
                shares = (capital_for_pos * (1 - commission_pct)) / entry_price
                positions[symbol] = Position(
                    symbol=symbol,
                    entry_price=entry_price,
                    entry_date=day,
                    shares=shares,
                    cost_basis=capital_for_pos,
                )
                cash -= capital_for_pos
            days_since_rebalance = 0

        # Open initial positions on first day
        if day == first_day and not circuit_breaker:
            for symbol, weight in alloc_map.items():
                price_row = prices.filter((pl.col("date") == day) & (pl.col("symbol") == symbol))
                if price_row.is_empty() or weight <= 0:
                    continue

                price = price_row["close"][0]
                if price <= 0:
                    continue

                capital_for_pos = initial_capital * weight
                slp = _get_slippage(symbol, capital_for_pos)
                entry_price = price * (1 + slp)  # volume-dependent slippage on entry
                shares = (capital_for_pos * (1 - commission_pct)) / entry_price
                positions[symbol] = Position(
                    symbol=symbol,
                    entry_price=entry_price,
                    entry_date=day,
                    shares=shares,
                    cost_basis=capital_for_pos,
                )
                cash -= capital_for_pos

        # Risk checks on existing positions
        closed_symbols = []
        for sym, pos in positions.items():
            price_row = prices.filter((pl.col("date") == day) & (pl.col("symbol") == sym))
            if price_row.is_empty():
                continue
            current_price = price_row["close"][0]

            pnl_pct = (current_price - pos.entry_price) / pos.entry_price

            # Stop-loss
            if pnl_pct <= -stop_loss:
                slp = _get_slippage(sym, pos.shares * current_price)
                proceeds = _close_position(pos, current_price, commission_pct, slp)
                trade_returns.append((proceeds - pos.cost_basis) / pos.cost_basis)
                cash += proceeds
                closed_symbols.append(sym)
                continue

            # Take-profit
            if pnl_pct >= take_profit:
                slp = _get_slippage(sym, pos.shares * current_price)
                proceeds = _close_position(pos, current_price, commission_pct, slp)
                trade_returns.append((proceeds - pos.cost_basis) / pos.cost_basis)
                cash += proceeds
                closed_symbols.append(sym)

        for sym in closed_symbols:
            del positions[sym]

        # Compute portfolio equity
        portfolio_value = cash
        for sym, pos in positions.items():
            price_row = prices.filter((pl.col("date") == day) & (pl.col("symbol") == sym))
            if not price_row.is_empty():
                current_price = price_row["close"][0]
                portfolio_value += pos.shares * current_price

        equity_curve.append(portfolio_value)
        days_since_rebalance += 1

        if len(equity_curve) >= 2:
            daily_ret = (equity_curve[-1] - equity_curve[-2]) / equity_curve[-2]
            daily_returns_list.append(daily_ret)

        # Drawdown circuit breaker
        peak_equity = max(peak_equity, portfolio_value)
        current_dd = (portfolio_value - peak_equity) / peak_equity

        if current_dd <= -max_dd_limit and not circuit_breaker:
            circuit_breaker = True
            cooldown_until = day + dt.timedelta(days=cooldown_days)
            for sym, pos in list(positions.items()):
                price_row = prices.filter((pl.col("date") == day) & (pl.col("symbol") == sym))
                if not price_row.is_empty():
                    slp = _get_slippage(sym, pos.shares * price_row["close"][0])
                    proceeds = _close_position(pos, price_row["close"][0], commission_pct, slp)
                    trade_returns.append((proceeds - pos.cost_basis) / pos.cost_basis)
                    cash += proceeds
            positions.clear()
            continue

        if cooldown_until and day < cooldown_until:
            continue
        if cooldown_until and day >= cooldown_until:
            circuit_breaker = False
            cooldown_until = None
            peak_equity = portfolio_value

    # Close remaining positions at last price
    last_date = dates[-1] if dates else None
    for sym, pos in list(positions.items()):
        price_row = prices.filter((pl.col("date") == last_date) & (pl.col("symbol") == sym))
        if not price_row.is_empty():
            slp = _get_slippage(sym, pos.shares * price_row["close"][0])
            proceeds = _close_position(pos, price_row["close"][0], commission_pct, slp)
            trade_returns.append((proceeds - pos.cost_basis) / pos.cost_basis)
            cash += proceeds
    positions.clear()

    # Compute metrics
    final_value = cash
    equity_arr = np.array(equity_curve) if equity_curve else np.array([initial_capital])
    daily_returns_arr = np.array(daily_returns_list) if daily_returns_list else np.array([0.0])

    n_days = len(equity_curve)
    years = n_days / 252 if n_days > 0 else 1
    total_return = final_value / initial_capital - 1
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

    all_metrics = compute_all_metrics(daily_returns_arr, equity_arr, benchmark_returns)

    winning = sum(1 for r in trade_returns if r > 0)
    win_rate = winning / len(trade_returns) if trade_returns else 0.0
    avg_trade = float(np.mean(trade_returns)) if trade_returns else 0.0

    num_trades = len(trade_returns)
    max_dd = all_metrics["max_drawdown"]

    # Guard against divide-by-zero / small-sample metrics. When the sample is too
    # small (few trades) or the drawdown denominator is too tight, Sharpe/Sortino/
    # Calmar explode into meaningless ranges. Surface them as NaN so downstream
    # reports can flag the row as insufficient data instead of treating the
    # artifact as a real signal.
    insufficient = num_trades < MIN_TRADES_FOR_METRICS or max_dd < MIN_DRAWDOWN_PCT_FOR_METRICS
    if insufficient:
        sharpe_val = float("nan")
        sortino_val = float("nan")
        calmar_val = float("nan")
        omega_val = float("nan")
    else:
        sharpe_val = all_metrics["sharpe"]
        sortino_val = all_metrics["sortino"]
        calmar_val = all_metrics["calmar"]
        omega_val = all_metrics["omega"]

    # Suppress benchmark annualization metrics when the window is too short.
    # A naive (1+r_period)^(252/n)-1 over 15-25 trading days explodes a small
    # positive period return into thousands-of-percent annual figures, making
    # bear-regime rows misleading. Apply this guard whenever the sample is
    # insufficient OR the number of trading days is below MIN_ANNUALIZATION_WINDOW.
    short_window = n_days < MIN_ANNUALIZATION_WINDOW
    if insufficient or short_window:
        bench_ann_ret = float("nan")
        tracking_err = float("nan")
        info_ratio_val = float("nan")
    else:
        bench_ann_ret = all_metrics.get("benchmark_annual_return", 0.0)
        tracking_err = all_metrics.get("tracking_error", 0.0)
        info_ratio_val = all_metrics["information"]

    return BacktestResult(
        total_return=total_return,
        annual_return=annual_return,
        sharpe_ratio=sharpe_val,
        sortino_ratio=sortino_val,
        calmar_ratio=calmar_val,
        omega_ratio=omega_val,
        info_ratio=info_ratio_val,
        max_drawdown=max_dd,
        win_rate=win_rate,
        num_trades=num_trades,
        avg_trade_return=avg_trade,
        final_value=final_value,
        circuit_breaker_triggered=circuit_breaker or (cooldown_until is not None),
        equity_curve=equity_curve,
        benchmark_annual_return=bench_ann_ret,
        tracking_error=tracking_err,
        insufficient_sample=insufficient,
    )


def _close_position(
    pos: Position, current_price: float, commission_pct: float, slippage_pct: float = 0.0
) -> float:
    """Calculate proceeds from closing a position.

    Args:
        pos: The position to close.
        current_price: Current market price.
        commission_pct: Commission rate.
        slippage_pct: Slippage as a fraction (e.g., 0.0005 for 5 bps).

    Returns:
        Net proceeds.
    """
    exit_price = current_price * (1 - slippage_pct)  # slippage on exit
    return pos.shares * exit_price * (1 - commission_pct)


def load_test_prices(symbols: list[str], start_date: dt.date, end_date: dt.date) -> pl.DataFrame:
    """Load prices for backtesting period from database.

    Args:
        symbols: List of symbols.
        start_date: Start of backtest period.
        end_date: End of backtest period.

    Returns:
        DataFrame with columns [date, symbol, close].
    """
    engine = get_engine()
    ph, params = in_params("s", symbols)
    params["start_date"] = start_date
    params["end_date"] = end_date
    query = text(f"""
        SELECT date, symbol, close FROM ohlcv_daily
        WHERE symbol IN ({ph})
          AND date >= :start_date AND date <= :end_date
        ORDER BY date, symbol
    """).bindparams(**params)
    with engine.connect() as conn:
        return pl.read_database(query, conn)


def load_benchmark_returns(benchmark: str, start_date: dt.date, end_date: dt.date) -> np.ndarray:
    """Load benchmark daily returns for the backtest period."""
    engine = get_engine()
    query = text("""
        SELECT date, close FROM ohlcv_daily
        WHERE symbol = :benchmark AND date >= :start_date AND date <= :end_date
        ORDER BY date
    """).bindparams(benchmark=benchmark, start_date=start_date, end_date=end_date)
    with engine.connect() as conn:
        df = pl.read_database(query, conn)
    if df.is_empty():
        return np.array([0.0])
    return (
        df.sort("date")
        .with_columns(pl.col("close").pct_change().alias("ret"))
        .drop_nulls(subset=["ret"])["ret"]
        .to_numpy()
    )


def run_all_backtests(config: dict) -> list[BacktestResult]:
    """Run backtests for all (profile, regime) combinations.

    Args:
        config: Full config dict.

    Returns:
        List of BacktestResult objects.
    """
    split_dates = compute_split_dates(config)
    bt_cfg = config.get("backtest", {})
    portfolio_cfg = config.get("portfolio", {})
    benchmark = portfolio_cfg.get("benchmark", "SPY")

    # Load portfolio allocations
    output_path = portfolio_cfg.get("output_parquet", "data/portfolios.parquet")
    if not Path(output_path).exists():
        print(f"Portfolio file not found: {output_path}. Run portfolio optimization first.")
        return []

    portfolios = pl.read_parquet(output_path)

    if portfolios.is_empty():
        print("No portfolio allocations found. Run portfolio optimization first.")
        return []

    # Detect regimes
    print("Detecting market regimes for test period...")
    regimes = detect_regimes(config)

    if regimes.is_empty():
        print("No regime data available.")
        return []

    # Load prices for all symbols in portfolios
    all_symbols = portfolios["symbol"].unique().to_list()
    prices = load_test_prices(all_symbols, split_dates.test_start, split_dates.today)

    # Load benchmark returns
    load_benchmark_returns(benchmark, split_dates.test_start, split_dates.today)

    profiles = portfolios["profile"].unique().to_list()
    regime_types = ["bull", "bear", "sideways"]

    results = []

    for profile in profiles:
        profile_alloc = portfolios.filter(pl.col("profile") == profile)

        for regime_type in regime_types:
            print(f"\n--- Backtest: {profile} / {regime_type} ---")

            # Filter prices to days matching this regime
            regime_dates = regimes.filter(pl.col("regime") == regime_type)["date"].to_list()

            if not regime_dates:
                print(f"  No {regime_type} days in test period, skipping")
                result = BacktestResult(
                    profile=profile,
                    regime=regime_type,
                    final_value=bt_cfg.get("initial_capital", 100000),
                )
                results.append(result)
                continue

            regime_prices = prices.filter(pl.col("date").is_in(regime_dates))

            # Filter benchmark returns to regime days
            bench_query = text(
                "SELECT date, close FROM ohlcv_daily WHERE symbol = :benchmark "
                "AND date >= :test_start ORDER BY date"
            ).bindparams(benchmark=benchmark, test_start=split_dates.test_start)
            with get_engine().connect() as bench_conn:
                all_bench = pl.read_database(bench_query, bench_conn)
            regime_bench = all_bench.filter(pl.col("date").is_in(regime_dates)).sort("date")
            if len(regime_bench) > 1:
                regime_bench_returns = (
                    regime_bench.with_columns(pl.col("close").pct_change().alias("ret"))
                    .drop_nulls(subset=["ret"])["ret"]
                    .to_numpy()
                )
            else:
                regime_bench_returns = None

            # Merge portfolio constraints into backtest config
            port_constraints = portfolio_cfg.get("constraints", {})
            bt_with_rebalance = {
                **bt_cfg,
                "rebalance_frequency_days": port_constraints.get("rebalance_frequency_days", 21),
                "max_position_drift": port_constraints.get("max_position_drift", 0.0),
            }
            result = run_portfolio_backtest(
                profile_alloc,
                regime_prices,
                bt_with_rebalance,
                benchmark_returns=regime_bench_returns,
            )
            result.profile = profile
            result.regime = regime_type

            def _p(v: float) -> str:
                return "n/a" if not np.isfinite(v) else f"{v:.3f}"

            print(f"  Return: {result.total_return:+.2%}")
            print(f"  Sharpe: {_p(result.sharpe_ratio)}  Sortino: {_p(result.sortino_ratio)}")
            print(f"  Calmar: {_p(result.calmar_ratio)}  Omega: {_p(result.omega_ratio)}")
            print(f"  Info Ratio: {_p(result.info_ratio)}")
            bench_ann_str = (
                "n/a (short window)"
                if not np.isfinite(result.benchmark_annual_return)
                else f"{result.benchmark_annual_return:+.2%}"
            )
            tracking_err_str = (
                "n/a (short window)"
                if not np.isfinite(result.tracking_error)
                else f"{result.tracking_error:.2%}"
            )
            print(f"  Bench Ann Ret: {bench_ann_str}  Tracking Err: {tracking_err_str}")
            print(f"  Max DD: {result.max_drawdown:.2%}  Win Rate: {result.win_rate:.2%}")
            print(f"  Trades: {result.num_trades}  Final: ${result.final_value:,.2f}")
            if result.insufficient_sample:
                print("  [flag] insufficient_sample -- risk ratios suppressed")

            results.append(result)

    return results


@dataclass
class RegressionFlag:
    """A single regression flag for a (profile, regime) cell."""

    profile: str
    regime: str
    previous_sharpe: float
    current_sharpe: float
    drop_pct: float  # positive = degradation, e.g. 0.35 = 35% drop


@dataclass
class RegressionGuardResult:
    """Outcome of the regression guard check.

    Attributes:
        flags: List of (profile, regime) cells that exceeded the drop threshold.
        skipped: True when there is no previous run to compare against.
        previous_run_date: Date of the baseline run used for comparison.
    """

    flags: list[RegressionFlag] = field(default_factory=list)
    skipped: bool = False
    previous_run_date: dt.date | None = None

    @property
    def has_regression(self) -> bool:
        """True when at least one monitored cell exceeded the drop threshold."""
        return bool(self.flags)


# Cells watched by the regression guard: (profile, regime) tuples.
# These correspond to the use-case in BEC-65 (moderate/sideways are most informative
# but we also guard all regime×profile combos to avoid blind spots).
_GUARD_CELLS: list[tuple[str, str]] = [
    ("moderate", "sideways"),
    ("moderate", "bull"),
    ("moderate", "bear"),
]

# Default drop threshold: flag when Sharpe falls more than this fraction vs. previous cycle.
DEFAULT_REGRESSION_THRESHOLD = 0.30


def _sharpe_drop_pct(previous: float, current: float) -> float:
    """Return the fractional Sharpe drop relative to ``previous``.

    Returns 0.0 when either value is non-finite (skip rather than false-positive).
    Negative previous Sharpe ratios are handled: if both are negative and current
    is *less* negative, that's an improvement (returns negative drop, i.e. no flag).
    """
    if not np.isfinite(previous) or not np.isfinite(current):
        return 0.0
    if previous == 0.0:
        return 0.0
    # Use absolute previous as denominator so direction is consistent.
    return (previous - current) / abs(previous)


def check_regression_guard(
    current_results: list[BacktestResult],
    engine=None,  # type: ignore[assignment]
    *,
    threshold: float = DEFAULT_REGRESSION_THRESHOLD,
    guard_cells: list[tuple[str, str]] | None = None,
    current_run_date: dt.date | None = None,
) -> RegressionGuardResult:
    """Compare current backtest Sharpe ratios against the previous cycle.

    Queries the ``backtest_results`` table for the most recent prior run_date
    (before *current_run_date*) and compares Sharpe ratios for each watched
    (profile, regime) cell.  Flags any cell where the Sharpe ratio dropped by
    more than *threshold* (default 30 %).

    Args:
        current_results: Results from the current backtest run.
        engine: SQLAlchemy engine (uses singleton when None).
        threshold: Fractional drop that triggers a flag (0.30 = 30 %).
        guard_cells: List of (profile, regime) tuples to watch.
                     Defaults to ``_GUARD_CELLS``.
        current_run_date: The run_date for the current results (defaults to today).

    Returns:
        RegressionGuardResult with any flags populated.
    """
    if guard_cells is None:
        guard_cells = _GUARD_CELLS
    current_run_date = current_run_date or dt.date.today()

    # Build a lookup from current results: (profile, regime) -> sharpe
    current_map: dict[tuple[str, str], float] = {
        (r.profile, r.regime): r.sharpe_ratio for r in current_results
    }

    db_engine = engine or get_engine()

    # Find the most recent prior run_date (strict: < current_run_date)
    prior_date_row = None
    try:
        with db_engine.connect() as conn:
            prior_date_row = conn.execute(
                text("""
                    SELECT MAX(run_date) AS prior_date
                    FROM backtest_results
                    WHERE run_date < :current_date
                """).bindparams(current_date=current_run_date)
            ).fetchone()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Regression guard: could not query prior run_date: %s", exc)
        result = RegressionGuardResult(skipped=True)
        return result

    if prior_date_row is None or prior_date_row[0] is None:
        logger.info(
            "Regression guard: no prior backtest run found before %s — skipping comparison.",
            current_run_date,
        )
        return RegressionGuardResult(skipped=True)

    prior_date: dt.date = prior_date_row[0]

    # Load previous sharpe ratios for the watched cells
    flags: list[RegressionFlag] = []
    try:
        with db_engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT profile, regime, sharpe_ratio
                    FROM backtest_results
                    WHERE run_date = :prior_date
                """).bindparams(prior_date=prior_date)
            ).fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Regression guard: could not load prior results: %s", exc)
        return RegressionGuardResult(skipped=True, previous_run_date=prior_date)

    prior_map: dict[tuple[str, str], float | None] = {(row[0], row[1]): row[2] for row in rows}

    for profile, regime in guard_cells:
        prior_sharpe_raw = prior_map.get((profile, regime))
        current_sharpe = current_map.get((profile, regime))

        if prior_sharpe_raw is None or current_sharpe is None:
            continue  # cell missing in one of the runs — skip

        prior_sharpe = float(prior_sharpe_raw)
        drop = _sharpe_drop_pct(prior_sharpe, current_sharpe)

        if drop > threshold:
            flags.append(
                RegressionFlag(
                    profile=profile,
                    regime=regime,
                    previous_sharpe=prior_sharpe,
                    current_sharpe=current_sharpe,
                    drop_pct=drop,
                )
            )
            logger.warning(
                "REGRESSION GUARD: %s/%s Sharpe dropped %.1f%% "
                "(prev=%.3f → curr=%.3f) — exceeds %.0f%% threshold.",
                profile,
                regime,
                drop * 100,
                prior_sharpe,
                current_sharpe,
                threshold * 100,
            )

    return RegressionGuardResult(
        flags=flags,
        skipped=False,
        previous_run_date=prior_date,
    )


def save_backtest_results(
    results: list[BacktestResult],
    config: dict,
    run_date: dt.date | None = None,
) -> None:
    """Save backtest results to database and generate reports.

    Args:
        results: List of BacktestResult objects.
        config: Full config dict.
        run_date: Date for the run.
    """
    run_date = run_date or dt.date.today()
    bt_cfg = config.get("backtest", {})
    output_dir = Path(bt_cfg.get("output_dir", "data/backtest_reports"))
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save to database
    def _nan_to_none(value: float) -> float | None:
        """Convert non-finite floats to None so Postgres stores SQL NULL
        instead of 'NaN' / 'Infinity' which complicates downstream queries."""
        return None if not np.isfinite(value) else float(value)

    engine = get_engine()
    with engine.begin() as conn:
        for r in results:
            stmt = text("""
                INSERT INTO backtest_results
                    (run_date, profile, regime, total_return, annual_return,
                     sharpe_ratio, sortino_ratio, calmar_ratio, omega_ratio,
                     info_ratio, max_drawdown, win_rate, num_trades)
                VALUES
                    (:run_date, :profile, :regime, :total_return, :annual_return,
                     :sharpe_ratio, :sortino_ratio, :calmar_ratio, :omega_ratio,
                     :info_ratio, :max_drawdown, :win_rate, :num_trades)
                ON CONFLICT (run_date, profile, regime) DO UPDATE SET
                    total_return = EXCLUDED.total_return,
                    annual_return = EXCLUDED.annual_return,
                    sharpe_ratio = EXCLUDED.sharpe_ratio,
                    sortino_ratio = EXCLUDED.sortino_ratio,
                    calmar_ratio = EXCLUDED.calmar_ratio,
                    omega_ratio = EXCLUDED.omega_ratio,
                    info_ratio = EXCLUDED.info_ratio,
                    max_drawdown = EXCLUDED.max_drawdown,
                    win_rate = EXCLUDED.win_rate,
                    num_trades = EXCLUDED.num_trades
            """)
            conn.execute(
                stmt,
                {
                    "run_date": run_date,
                    "profile": r.profile,
                    "regime": r.regime,
                    "total_return": _nan_to_none(r.total_return),
                    "annual_return": _nan_to_none(r.annual_return),
                    "sharpe_ratio": _nan_to_none(r.sharpe_ratio),
                    "sortino_ratio": _nan_to_none(r.sortino_ratio),
                    "calmar_ratio": _nan_to_none(r.calmar_ratio),
                    "omega_ratio": _nan_to_none(r.omega_ratio),
                    "info_ratio": _nan_to_none(r.info_ratio),
                    "max_drawdown": _nan_to_none(r.max_drawdown),
                    "win_rate": _nan_to_none(r.win_rate),
                    "num_trades": r.num_trades,
                },
            )

    # Generate markdown report
    def _fmt_ratio(value: float) -> str:
        return "n/a (insufficient data)" if not np.isfinite(value) else f"{value:.3f}"

    report_path = output_dir / f"backtest_{run_date}.md"
    lines = [
        f"# Backtest Report — {run_date}\n",
        "Rows flagged `insufficient_sample` (n_trades < "
        f"{MIN_TRADES_FOR_METRICS} or max_dd < "
        f"{MIN_DRAWDOWN_PCT_FOR_METRICS:.1%}) report `n/a (insufficient data)` for "
        "Sharpe/Sortino/Calmar/Omega. "
        f"Rows with fewer than {MIN_ANNUALIZATION_WINDOW} trading days report "
        "`n/a (short window)` for Bench Ann Ret / Tracking Err / Info to avoid "
        "annualization artifacts.\n",
        "| Profile | Regime | Return | Sharpe | Sortino | Calmar | Omega | Info | Bench Ann Ret | Tracking Err | Max DD | Win Rate | Trades | Flag |",  # noqa: E501
        "|---------|--------|--------|--------|---------|--------|-------|------|---------------|--------------|--------|----------|--------|------|",  # noqa: E501
    ]

    def _fmt_pct(value: float, sign: bool = False) -> str:
        """Format a float as a percentage, or 'n/a (short window)' if not finite."""
        if not np.isfinite(value):
            return "n/a (short window)"
        return f"{value:+.2%}" if sign else f"{value:.2%}"

    for r in results:
        flag = "insufficient_sample" if r.insufficient_sample else ""
        lines.append(
            f"| {r.profile} | {r.regime} | {r.total_return:+.2%} | "
            f"{_fmt_ratio(r.sharpe_ratio)} | {_fmt_ratio(r.sortino_ratio)} | "
            f"{_fmt_ratio(r.calmar_ratio)} | {_fmt_ratio(r.omega_ratio)} | "
            f"{_fmt_ratio(r.info_ratio)} | {_fmt_pct(r.benchmark_annual_return, sign=True)} | "
            f"{_fmt_pct(r.tracking_error)} | {r.max_drawdown:.2%} | "
            f"{r.win_rate:.2%} | {r.num_trades} | {flag} |"
        )
    lines.append("")

    report_path.write_text("\n".join(lines))
    print(f"\nReport saved to {report_path}")


def main() -> None:
    """Run backtesting pipeline for all portfolios and regimes."""
    parser = argparse.ArgumentParser(description="Backtest portfolios by regime")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    args = parser.parse_args()

    config = load_config(args.config)

    print("Running portfolio backtests by market regime...")
    results = run_all_backtests(config)

    if not results:
        return

    save_backtest_results(results, config)

    # --- Regression guard ---
    guard_result = check_regression_guard(results)
    if guard_result.skipped:
        print("\nRegression guard: no prior cycle found — comparison skipped.")
    elif guard_result.has_regression:
        print(
            f"\n[REGRESSION GUARD] {len(guard_result.flags)} cell(s) degraded "
            f"by >{DEFAULT_REGRESSION_THRESHOLD:.0%} vs. {guard_result.previous_run_date}:"
        )
        for flag in guard_result.flags:
            print(
                f"  {flag.profile}/{flag.regime}: Sharpe {flag.previous_sharpe:.3f} → "
                f"{flag.current_sharpe:.3f} ({flag.drop_pct:+.1%} drop)"
            )
    else:
        print(
            f"\nRegression guard: OK — no Sharpe drop >{DEFAULT_REGRESSION_THRESHOLD:.0%} "
            f"vs. {guard_result.previous_run_date}."
        )

    # Log to MLflow
    def _log_finite(name: str, value: float) -> None:
        if np.isfinite(value):
            mlflow.log_metric(name, value)

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("backtesting")
    with mlflow.start_run(run_name="regime-backtest"):
        for r in results:
            prefix = f"{r.profile}_{r.regime}"
            _log_finite(f"{prefix}_return", r.total_return)
            _log_finite(f"{prefix}_sharpe", r.sharpe_ratio)
            _log_finite(f"{prefix}_sortino", r.sortino_ratio)
            _log_finite(f"{prefix}_calmar", r.calmar_ratio)
            _log_finite(f"{prefix}_omega", r.omega_ratio)
            _log_finite(f"{prefix}_info", r.info_ratio)
            _log_finite(f"{prefix}_max_dd", r.max_drawdown)
            mlflow.set_tag(f"{prefix}_insufficient_sample", str(r.insufficient_sample))

        # Log regression guard outcome
        mlflow.set_tag("regression_guard_skipped", str(guard_result.skipped))
        mlflow.set_tag("regression_guard_has_regression", str(guard_result.has_regression))
        if guard_result.previous_run_date:
            mlflow.set_tag("regression_guard_baseline", str(guard_result.previous_run_date))
        for flag in guard_result.flags:
            key = f"regression_{flag.profile}_{flag.regime}_drop_pct"
            mlflow.log_metric(key, flag.drop_pct)

        bt_cfg = config.get("backtest", {})
        output_dir = bt_cfg.get("output_dir", "data/backtest_reports")
        for report_file in Path(output_dir).glob("*.md"):
            mlflow.log_artifact(str(report_file))
    print("Logged backtest results to MLflow")


if __name__ == "__main__":
    main()
