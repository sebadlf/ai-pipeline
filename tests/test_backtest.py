"""Tests for portfolio backtesting."""

import datetime as dt

import numpy as np
import polars as pl
import pytest

from src.evaluation.backtest import BacktestResult, Position, run_portfolio_backtest


@pytest.fixture
def sample_prices() -> pl.DataFrame:
    """Generate 20 days of price data for 2 stocks."""
    dates = pl.date_range(
        pl.date(2024, 1, 1), pl.date(2024, 1, 20), eager=True
    ).to_list()

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
    """Portfolio with 60% AAPL (long) and 40% MSFT (long)."""
    return pl.DataFrame([
        {"symbol": "AAPL", "weight": 0.6, "signal": "BUY", "cluster_id": "Tech_0"},
        {"symbol": "MSFT", "weight": 0.4, "signal": "BUY", "cluster_id": "Tech_0"},
    ])


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


def test_backtest_short_position() -> None:
    """Test that short positions profit when price drops."""
    dates = pl.date_range(pl.date(2024, 1, 1), pl.date(2024, 1, 10), eager=True).to_list()
    prices_data = [{"date": d, "symbol": "BAD", "close": float(p)}
                   for d, p in zip(dates, np.linspace(100, 80, len(dates)))]
    prices = pl.DataFrame(prices_data)

    allocations = pl.DataFrame([
        {"symbol": "BAD", "weight": 1.0, "signal": "SELL", "cluster_id": "Test_0"},
    ])

    config = {
        "initial_capital": 100000,
        "commission_pct": 0.001,
        "risk": {
            "position_stop_loss": 0.30,
            "position_take_profit": 0.50,
            "max_drawdown_limit": 0.50,
            "cooldown_days": 2,
        },
    }

    result = run_portfolio_backtest(allocations, prices, config)
    assert result.total_return > 0, f"Short should profit on falling stock, got {result.total_return}"


def test_backtest_empty_allocations(sample_prices: pl.DataFrame, backtest_config: dict) -> None:
    empty_alloc = pl.DataFrame(schema={
        "symbol": pl.Utf8, "weight": pl.Float64,
        "signal": pl.Utf8, "cluster_id": pl.Utf8,
    })
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
