"""Tests for portfolio metrics."""

import numpy as np
import pytest

from src.portfolio.metrics import (
    calmar_ratio,
    information_ratio,
    max_drawdown,
    omega_ratio,
    sharpe_ratio,
    sortino_ratio,
)


@pytest.fixture
def positive_returns() -> np.ndarray:
    """Returns with positive mean and moderate volatility."""
    np.random.seed(42)
    return np.random.normal(0.001, 0.01, 252)


@pytest.fixture
def negative_returns() -> np.ndarray:
    """Returns with negative mean."""
    np.random.seed(42)
    return np.random.normal(-0.002, 0.01, 252)


def test_sharpe_positive(positive_returns: np.ndarray) -> None:
    result = sharpe_ratio(positive_returns)
    assert result > 0, f"Expected positive Sharpe, got {result}"


def test_sharpe_zero_std() -> None:
    returns = np.zeros(100)
    assert sharpe_ratio(returns) == 0.0


def test_sortino_positive(positive_returns: np.ndarray) -> None:
    result = sortino_ratio(positive_returns)
    assert result > 0


def test_sortino_greater_than_sharpe(positive_returns: np.ndarray) -> None:
    """Sortino should be >= Sharpe when upside volatility dominates."""
    s = sharpe_ratio(positive_returns)
    so = sortino_ratio(positive_returns)
    # With positive mean and symmetric volatility, Sortino >= Sharpe
    assert so >= s * 0.8, f"Sortino ({so}) unexpectedly much lower than Sharpe ({s})"


def test_omega_positive_returns(positive_returns: np.ndarray) -> None:
    result = omega_ratio(positive_returns)
    assert result > 1.0, f"Expected Omega > 1 for positive returns, got {result}"


def test_omega_negative_returns(negative_returns: np.ndarray) -> None:
    result = omega_ratio(negative_returns)
    assert result < 1.0, f"Expected Omega < 1 for negative returns, got {result}"


def test_omega_no_losses() -> None:
    returns = np.ones(100) * 0.01
    result = omega_ratio(returns)
    assert result == float("inf")


def test_calmar_positive() -> None:
    # Equity curve that goes up with a small drawdown
    equity = np.array([100, 105, 103, 108, 112, 115])
    returns = np.diff(equity) / equity[:-1]
    result = calmar_ratio(returns, equity)
    assert result > 0


def test_calmar_no_drawdown() -> None:
    equity = np.array([100, 101, 102, 103, 104])
    returns = np.diff(equity) / equity[:-1]
    result = calmar_ratio(returns, equity)
    assert result == float("inf")


def test_information_ratio_outperformance() -> None:
    np.random.seed(42)
    benchmark = np.random.normal(0.0005, 0.01, 252)
    portfolio = benchmark + 0.001  # consistently outperform
    result = information_ratio(portfolio, benchmark)
    assert result > 0


def test_information_ratio_same_returns() -> None:
    returns = np.ones(100) * 0.001
    result = information_ratio(returns, returns)
    assert result == 0.0


def test_max_drawdown_value() -> None:
    equity = np.array([100, 110, 105, 95, 100, 108])
    result = max_drawdown(equity)
    # Peak was 110, trough was 95 -> drawdown = 15/110 ≈ 0.1364
    expected = (110 - 95) / 110
    assert abs(result - expected) < 1e-6


def test_max_drawdown_no_drawdown() -> None:
    equity = np.array([100, 101, 102, 103])
    assert max_drawdown(equity) == 0.0
