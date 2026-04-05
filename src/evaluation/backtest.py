"""Portfolio-level backtesting with risk management and regime analysis (Stage 5).

Simulates long-only portfolio performance day by day for each (profile, regime)
combination, computes all risk metrics.

Usage:
    uv run python -m src.evaluation.backtest
"""

from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import mlflow
import numpy as np
import polars as pl
from sqlalchemy import text

from src.config import compute_split_dates, load_config
from src.db import get_engine
from src.evaluation.regime import detect_regimes
from src.keys import MLFLOW_TRACKING_URI
from src.portfolio.metrics import compute_all_metrics


@dataclass
class Position:
    """An open long position in a single stock."""

    symbol: str
    entry_price: float
    entry_date: dt.date
    shares: float
    cost_basis: float


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
    slippage_pct = slippage_bps / 10_000
    stop_loss = risk_cfg.get("position_stop_loss", 0.08)
    take_profit = risk_cfg.get("position_take_profit", 0.50)
    max_dd_limit = risk_cfg.get("max_drawdown_limit", 0.25)
    cooldown_days = risk_cfg.get("cooldown_days", 2)

    if allocations.is_empty() or prices.is_empty():
        return BacktestResult(final_value=initial_capital)

    # Build allocation map
    alloc_map: dict[str, float] = {}
    for row in allocations.iter_rows(named=True):
        alloc_map[row["symbol"]] = row["weight"]

    dates = sorted(prices["date"].unique().to_list())
    symbols_in_portfolio = list(alloc_map.keys())

    cash = initial_capital
    positions: dict[str, Position] = {}
    equity_curve = []
    daily_returns_list = []
    trade_returns: list[float] = []
    peak_equity = initial_capital
    circuit_breaker = False
    cooldown_until: dt.date | None = None

    # Open positions on day 1 based on allocations
    first_day = dates[0] if dates else None

    for day in dates:
        # Open initial positions on first day
        if day == first_day and not circuit_breaker:
            for symbol, weight in alloc_map.items():
                price_row = prices.filter(
                    (pl.col("date") == day) & (pl.col("symbol") == symbol)
                )
                if price_row.is_empty() or weight <= 0:
                    continue

                price = price_row["close"][0]
                if price <= 0:
                    continue

                capital_for_pos = initial_capital * weight
                entry_price = price * (1 + slippage_pct)  # slippage on entry
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
            price_row = prices.filter(
                (pl.col("date") == day) & (pl.col("symbol") == sym)
            )
            if price_row.is_empty():
                continue
            current_price = price_row["close"][0]

            pnl_pct = (current_price - pos.entry_price) / pos.entry_price

            # Stop-loss
            if pnl_pct <= -stop_loss:
                proceeds = _close_position(pos, current_price, commission_pct, slippage_pct)
                trade_returns.append((proceeds - pos.cost_basis) / pos.cost_basis)
                cash += proceeds
                closed_symbols.append(sym)
                continue

            # Take-profit
            if pnl_pct >= take_profit:
                proceeds = _close_position(pos, current_price, commission_pct, slippage_pct)
                trade_returns.append((proceeds - pos.cost_basis) / pos.cost_basis)
                cash += proceeds
                closed_symbols.append(sym)

        for sym in closed_symbols:
            del positions[sym]

        # Compute portfolio equity
        portfolio_value = cash
        for sym, pos in positions.items():
            price_row = prices.filter(
                (pl.col("date") == day) & (pl.col("symbol") == sym)
            )
            if not price_row.is_empty():
                current_price = price_row["close"][0]
                portfolio_value += pos.shares * current_price

        equity_curve.append(portfolio_value)

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
                price_row = prices.filter(
                    (pl.col("date") == day) & (pl.col("symbol") == sym)
                )
                if not price_row.is_empty():
                    proceeds = _close_position(pos, price_row["close"][0], commission_pct, slippage_pct)
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
        price_row = prices.filter(
            (pl.col("date") == last_date) & (pl.col("symbol") == sym)
        )
        if not price_row.is_empty():
            proceeds = _close_position(pos, price_row["close"][0], commission_pct, slippage_pct)
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

    return BacktestResult(
        total_return=total_return,
        annual_return=annual_return,
        sharpe_ratio=all_metrics["sharpe"],
        sortino_ratio=all_metrics["sortino"],
        calmar_ratio=all_metrics["calmar"],
        omega_ratio=all_metrics["omega"],
        info_ratio=all_metrics["information"],
        max_drawdown=all_metrics["max_drawdown"],
        win_rate=win_rate,
        num_trades=len(trade_returns),
        avg_trade_return=avg_trade,
        final_value=final_value,
        circuit_breaker_triggered=circuit_breaker or (cooldown_until is not None),
        equity_curve=equity_curve,
    )


def _close_position(pos: Position, current_price: float, commission_pct: float, slippage_pct: float = 0.0) -> float:
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
    placeholders = ", ".join(f"'{s}'" for s in symbols)
    query = f"""
        SELECT date, symbol, close FROM ohlcv_daily
        WHERE symbol IN ({placeholders})
          AND date >= '{start_date}' AND date <= '{end_date}'
        ORDER BY date, symbol
    """
    return pl.read_database(query, engine)


def load_benchmark_returns(benchmark: str, start_date: dt.date, end_date: dt.date) -> np.ndarray:
    """Load benchmark daily returns for the backtest period."""
    engine = get_engine()
    query = f"""
        SELECT date, close FROM ohlcv_daily
        WHERE symbol = '{benchmark}' AND date >= '{start_date}' AND date <= '{end_date}'
        ORDER BY date
    """
    df = pl.read_database(query, engine)
    if df.is_empty():
        return np.array([0.0])
    return df.sort("date").with_columns(
        pl.col("close").pct_change().alias("ret")
    ).drop_nulls(subset=["ret"])["ret"].to_numpy()


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
    bench_returns = load_benchmark_returns(benchmark, split_dates.test_start, split_dates.today)

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
            bench_df = pl.DataFrame({"date": regime_dates}).sort("date")
            all_bench = pl.read_database(
                f"SELECT date, close FROM ohlcv_daily WHERE symbol = '{benchmark}' "
                f"AND date >= '{split_dates.test_start}' ORDER BY date",
                get_engine(),
            )
            regime_bench = all_bench.filter(pl.col("date").is_in(regime_dates)).sort("date")
            if len(regime_bench) > 1:
                regime_bench_returns = regime_bench.with_columns(
                    pl.col("close").pct_change().alias("ret")
                ).drop_nulls(subset=["ret"])["ret"].to_numpy()
            else:
                regime_bench_returns = None

            result = run_portfolio_backtest(
                profile_alloc,
                regime_prices,
                bt_cfg,
                benchmark_returns=regime_bench_returns,
            )
            result.profile = profile
            result.regime = regime_type

            print(f"  Return: {result.total_return:+.2%}")
            print(f"  Sharpe: {result.sharpe_ratio:.3f}  Sortino: {result.sortino_ratio:.3f}")
            print(f"  Calmar: {result.calmar_ratio:.3f}  Omega: {result.omega_ratio:.3f}")
            print(f"  Info Ratio: {result.info_ratio:.3f}")
            print(f"  Max DD: {result.max_drawdown:.2%}  Win Rate: {result.win_rate:.2%}")
            print(f"  Trades: {result.num_trades}  Final: ${result.final_value:,.2f}")

            results.append(result)

    return results


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
            conn.execute(stmt, {
                "run_date": run_date,
                "profile": r.profile,
                "regime": r.regime,
                "total_return": r.total_return,
                "annual_return": r.annual_return,
                "sharpe_ratio": r.sharpe_ratio,
                "sortino_ratio": r.sortino_ratio,
                "calmar_ratio": r.calmar_ratio,
                "omega_ratio": r.omega_ratio,
                "info_ratio": r.info_ratio,
                "max_drawdown": r.max_drawdown,
                "win_rate": r.win_rate,
                "num_trades": r.num_trades,
            })

    # Generate markdown report
    report_path = output_dir / f"backtest_{run_date}.md"
    lines = [
        f"# Backtest Report — {run_date}\n",
        "| Profile | Regime | Return | Sharpe | Sortino | Calmar | Omega | Info | Max DD | Win Rate | Trades |",
        "|---------|--------|--------|--------|---------|--------|-------|------|--------|----------|--------|",
    ]
    for r in results:
        lines.append(
            f"| {r.profile} | {r.regime} | {r.total_return:+.2%} | "
            f"{r.sharpe_ratio:.3f} | {r.sortino_ratio:.3f} | {r.calmar_ratio:.3f} | "
            f"{r.omega_ratio:.3f} | {r.info_ratio:.3f} | {r.max_drawdown:.2%} | "
            f"{r.win_rate:.2%} | {r.num_trades} |"
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

    # Log to MLflow
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("backtesting")
    with mlflow.start_run(run_name="regime-backtest"):
        for r in results:
            prefix = f"{r.profile}_{r.regime}"
            mlflow.log_metric(f"{prefix}_return", r.total_return)
            mlflow.log_metric(f"{prefix}_sharpe", r.sharpe_ratio)
            mlflow.log_metric(f"{prefix}_sortino", r.sortino_ratio)
            mlflow.log_metric(f"{prefix}_calmar", r.calmar_ratio)
            mlflow.log_metric(f"{prefix}_omega", r.omega_ratio)
            mlflow.log_metric(f"{prefix}_info", r.info_ratio)
            mlflow.log_metric(f"{prefix}_max_dd", r.max_drawdown)

        bt_cfg = config.get("backtest", {})
        output_dir = bt_cfg.get("output_dir", "data/backtest_reports")
        for report_file in Path(output_dir).glob("*.md"):
            mlflow.log_artifact(str(report_file))
    print("Logged backtest results to MLflow")


if __name__ == "__main__":
    main()
