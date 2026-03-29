"""Tests for backtesting logic."""

import numpy as np
import pytest

from src.evaluation.backtest import (
    compute_max_drawdown,
    compute_sharpe,
    run_backtest,
)


def test_compute_sharpe_positive() -> None:
    returns = np.array([0.01, 0.02, -0.005, 0.015, 0.01])
    sharpe = compute_sharpe(returns)
    assert sharpe > 0


def test_compute_sharpe_zero_std() -> None:
    returns = np.array([0.0, 0.0, 0.0])
    assert compute_sharpe(returns) == 0.0


def test_compute_max_drawdown() -> None:
    equity = np.array([100, 110, 105, 95, 100, 90])
    dd = compute_max_drawdown(equity)
    assert dd < 0
    assert dd == pytest.approx(-20 / 110, rel=1e-6)


def test_run_backtest_all_long() -> None:
    predictions = np.array([0.01, 0.02, 0.01, 0.01, 0.02])
    actuals = np.array([0.01, -0.01, 0.02, 0.005, 0.01])
    result = run_backtest(predictions, actuals, initial_capital=10000, commission_pct=0.0)
    assert result.num_trades > 0
    assert result.final_value > 0


def test_run_backtest_no_trades() -> None:
    predictions = np.array([-0.01, -0.02, -0.01])
    actuals = np.array([0.01, 0.02, 0.01])
    result = run_backtest(predictions, actuals)
    assert result.num_trades == 0
    assert result.win_rate == 0.0
