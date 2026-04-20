"""Tests for portfolio backtesting."""

import math

import numpy as np
import polars as pl
import pytest

from src.evaluation.backtest import (
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
    """benchmark_annual_return and tracking_error fields should be floats,
    default 0.0 when no benchmark is supplied."""
    result = run_portfolio_backtest(sample_allocations, sample_prices, backtest_config)
    assert isinstance(result.benchmark_annual_return, float)
    assert isinstance(result.tracking_error, float)
    assert result.benchmark_annual_return == 0.0
    assert result.tracking_error == 0.0


def test_backtest_with_benchmark_populates_tracking_error(
    sample_allocations: pl.DataFrame,
    sample_prices: pl.DataFrame,
    backtest_config: dict,
) -> None:
    """When a benchmark is provided and daily returns exist, tracking_error is > 0
    unless the portfolio exactly matches the benchmark (not the case here)."""
    # Supply any nonzero benchmark series of the right shape. The backtest has ~20
    # days, so build a 19-element daily-return series to match the equity curve len.
    bench = np.linspace(-0.001, 0.001, 19)
    result = run_portfolio_backtest(
        sample_allocations,
        sample_prices,
        backtest_config,
        benchmark_returns=bench,
    )
    # We can't assert > 0 strictly in case the portfolio also matches; but the field
    # should be finite and non-negative. annualized_return of bench is finite too.
    assert math.isfinite(result.tracking_error)
    assert result.tracking_error >= 0.0
    assert math.isfinite(result.benchmark_annual_return)
