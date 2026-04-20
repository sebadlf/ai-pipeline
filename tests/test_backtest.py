"""Tests for portfolio backtesting."""

import math

import numpy as np
import polars as pl
import pytest

from src.evaluation.backtest import (
    MIN_ANNUALIZATION_WINDOW,
    MIN_DRAWDOWN_PCT_FOR_METRICS,
    MIN_TRADES_FOR_METRICS,
    BacktestResult,
    run_portfolio_backtest,
)


@pytest.fixture
def sample_prices() -> pl.DataFrame:
    """Generate 20 days of price data for 2 stocks."""
    dates = pl.date_range(pl.date(2024, 1, 1), pl.date(2024, 1, 20), eager=True).to_list()

    rows = []
    # AAPL: goes up 10% over 20 days
    aapl_prices = np.linspace(150, 165, len(dates))
    for d, p in zip(dates, aapl_prices):
        rows.append({"date": d, "symbol": "AAPL", "close": float(p)})

    # MSFT: goes down 5% over 20 days
    msft_prices = np.linspace(400, 380, len(dates))
    for d, p in zip(dates, msft_prices):
        rows.append({"date": d, "symbol": "MSFT", "close": float(p)})

    return pl.DataFrame(rows)


@pytest.fixture
def sample_allocations() -> pl.DataFrame:
    """Portfolio with 60% AAPL and 40% MSFT (long-only)."""
    return pl.DataFrame(
        [
            {"symbol": "AAPL", "weight": 0.6, "cluster_id": "Tech_0", "prob_up": 0.85},
            {"symbol": "MSFT", "weight": 0.4, "cluster_id": "Tech_0", "prob_up": 0.72},
        ]
    )


@pytest.fixture
def backtest_config() -> dict:
    return {
        "initial_capital": 100000,
        "commission_pct": 0.001,
        "risk": {
            "position_stop_loss": 0.08,
            "position_take_profit": 0.50,
            "max_drawdown_limit": 0.25,
            "cooldown_days": 2,
        },
    }


def test_backtest_produces_result(
    sample_allocations: pl.DataFrame,
    sample_prices: pl.DataFrame,
    backtest_config: dict,
) -> None:
    result = run_portfolio_backtest(sample_allocations, sample_prices, backtest_config)
    assert isinstance(result, BacktestResult)
    assert result.final_value > 0
    assert len(result.equity_curve) > 0


def test_backtest_long_portfolio_positive_return(
    sample_allocations: pl.DataFrame,
    sample_prices: pl.DataFrame,
    backtest_config: dict,
) -> None:
    """AAPL goes up 10%, MSFT goes down 5%. 60/40 split should be net positive."""
    result = run_portfolio_backtest(sample_allocations, sample_prices, backtest_config)
    # Weighted return ~ 0.6 * 10% + 0.4 * (-5%) = 4%
    assert result.total_return > 0, f"Expected positive return, got {result.total_return}"


def test_backtest_empty_allocations(sample_prices: pl.DataFrame, backtest_config: dict) -> None:
    empty_alloc = pl.DataFrame(
        schema={
            "symbol": pl.Utf8,
            "weight": pl.Float64,
            "cluster_id": pl.Utf8,
            "prob_up": pl.Float64,
        }
    )
    result = run_portfolio_backtest(empty_alloc, sample_prices, backtest_config)
    assert result.final_value == 100000
    assert result.num_trades == 0


def test_backtest_metrics_populated(
    sample_allocations: pl.DataFrame,
    sample_prices: pl.DataFrame,
    backtest_config: dict,
) -> None:
    """All metric fields should be populated."""
    result = run_portfolio_backtest(sample_allocations, sample_prices, backtest_config)
    assert isinstance(result.sharpe_ratio, float)
    assert isinstance(result.sortino_ratio, float)
    assert isinstance(result.calmar_ratio, float)
    assert isinstance(result.omega_ratio, float)
    assert isinstance(result.max_drawdown, float)


def test_backtest_insufficient_sample_emits_nan(
    sample_allocations: pl.DataFrame,
    sample_prices: pl.DataFrame,
    backtest_config: dict,
) -> None:
    """Few trades OR tiny max drawdown must surface Sharpe/Sortino/Calmar/Omega as NaN
    and raise the insufficient_sample flag. The 20-day fixture with monotonic prices
    produces 0 trades (below MIN_TRADES_FOR_METRICS) AND negligible drawdown — both
    guard conditions trip simultaneously.
    """
    result = run_portfolio_backtest(sample_allocations, sample_prices, backtest_config)
    assert result.num_trades < MIN_TRADES_FOR_METRICS
    assert result.max_drawdown < MIN_DRAWDOWN_PCT_FOR_METRICS
    assert result.insufficient_sample is True
    assert math.isnan(result.sharpe_ratio)
    assert math.isnan(result.sortino_ratio)
    assert math.isnan(result.calmar_ratio)
    assert math.isnan(result.omega_ratio)


def test_backtest_benchmark_fields_populated(
    sample_allocations: pl.DataFrame,
    sample_prices: pl.DataFrame,
    backtest_config: dict,
) -> None:
    """benchmark_annual_return and tracking_error fields should be floats.
    When no benchmark is supplied AND the window is short (<MIN_ANNUALIZATION_WINDOW),
    both fields are NaN (short window guard fires before the no-benchmark path).
    """
    result = run_portfolio_backtest(sample_allocations, sample_prices, backtest_config)
    assert isinstance(result.benchmark_annual_return, float)
    assert isinstance(result.tracking_error, float)
    # The 20-day fixture is below MIN_ANNUALIZATION_WINDOW so both are NaN
    assert math.isnan(result.benchmark_annual_return)
    assert math.isnan(result.tracking_error)


def test_backtest_with_benchmark_suppressed_on_short_window() -> None:
    """Benchmark metrics are NaN on short windows regardless of benchmark presence.
    With a window < MIN_ANNUALIZATION_WINDOW, benchmark_annual_return and
    tracking_error must always be NaN — the short window guard fires before
    any annualization calculation.
    """
    import datetime as dt

    # Use a window just under the threshold
    n_days = MIN_ANNUALIZATION_WINDOW - 10
    assert n_days > 5, "fixture must be long enough to run"
    start = dt.date(2024, 1, 3)
    dates = [start + dt.timedelta(days=i) for i in range(n_days)]

    prices_list = []
    spy_prices = np.linspace(450.0, 460.0, n_days)
    for d, p in zip(dates, spy_prices):
        prices_list.append({"date": d, "symbol": "SPY", "close": float(p)})
    prices = pl.DataFrame(prices_list)

    allocations = pl.DataFrame(
        [{"symbol": "SPY", "weight": 1.0, "cluster_id": "ETF_0", "prob_up": 0.80}]
    )
    config = {
        "initial_capital": 100000,
        "commission_pct": 0.001,
        "risk": {
            "position_stop_loss": 0.08,
            "position_take_profit": 0.50,
            "max_drawdown_limit": 0.25,
            "cooldown_days": 2,
        },
    }
    bench = np.diff(spy_prices) / spy_prices[:-1]
    result = run_portfolio_backtest(allocations, prices, config, benchmark_returns=bench)

    # Regardless of whether insufficient_sample also fires, the short window means NaN
    assert math.isnan(result.benchmark_annual_return), (
        f"Expected NaN for benchmark_annual_return on short window, "
        f"got {result.benchmark_annual_return}"
    )
    assert math.isnan(result.tracking_error), (
        f"Expected NaN for tracking_error on short window, got {result.tracking_error}"
    )
    assert math.isnan(result.info_ratio), (
        f"Expected NaN for info_ratio on short window, got {result.info_ratio}"
    )


def test_short_window_benchmark_annualization_suppressed() -> None:
    """A 20-trading-day bear regime with a small positive SPY return must NOT produce
    a pathological Bench Ann Ret > 500%.

    Without the MIN_ANNUALIZATION_WINDOW guard, (1+r)^(252/20)-1 over a small r can
    explode to thousands-of-percent. With the guard, all three benchmark metrics
    (bench_ann_ret, tracking_err, info_ratio) should be NaN.
    """
    assert 20 < MIN_ANNUALIZATION_WINDOW, "fixture is only meaningful below the threshold"

    dates = pl.date_range(pl.date(2024, 1, 1), pl.date(2024, 1, 20), eager=True).to_list()

    # Single stock with a small positive drift (mimics SPY in a short bear window)
    prices_list = []
    spy_prices = np.linspace(450.0, 453.0, len(dates))  # ~+0.7% period return
    for d, p in zip(dates, spy_prices):
        prices_list.append({"date": d, "symbol": "SPY", "close": float(p)})
    prices = pl.DataFrame(prices_list)

    allocations = pl.DataFrame(
        [{"symbol": "SPY", "weight": 1.0, "cluster_id": "ETF_0", "prob_up": 0.80}]
    )

    config = {
        "initial_capital": 100000,
        "commission_pct": 0.001,
        "risk": {
            "position_stop_loss": 0.08,
            "position_take_profit": 0.50,
            "max_drawdown_limit": 0.25,
            "cooldown_days": 2,
        },
    }

    # Build a benchmark series with a small positive total return matching the window
    # (19 daily returns for 20 equity data points)
    bench = np.diff(spy_prices) / spy_prices[:-1]

    result = run_portfolio_backtest(allocations, prices, config, benchmark_returns=bench)

    # Core assertion: no pathological benchmark annualization
    assert math.isnan(result.benchmark_annual_return), (
        f"Expected NaN for benchmark_annual_return on short window, "
        f"got {result.benchmark_annual_return:.2%}"
    )
    assert math.isnan(result.tracking_error), (
        f"Expected NaN for tracking_error on short window, got {result.tracking_error}"
    )
    assert math.isnan(result.info_ratio), (
        f"Expected NaN for info_ratio on short window, got {result.info_ratio}"
    )

    # Sanity: the raw period return should still be sensible (< 5%)
    assert abs(result.total_return) < 0.05, (
        f"Unexpected large total_return: {result.total_return:.2%}"
    )
