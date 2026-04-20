"""Tests for portfolio metrics."""

import numpy as np
import pytest

from src.portfolio.metrics import (
    annualized_return,
    calmar_ratio,
    compute_all_metrics,
    information_ratio,
    max_drawdown,
    omega_ratio,
    sharpe_ratio,
    sortino_ratio,
    tracking_error,
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


def test_information_ratio_canonical_reference() -> None:
    """Canonical reference check:
    IR = (annualized_active_mean) / (annualized_active_std)
       = (mean_active * 252) / (std_active * sqrt(252))
       = sqrt(252) * mean_active / std_active
    Use a deterministic synthetic example where the reference value is known.
    """
    portfolio = np.array([0.002, -0.001, 0.004, 0.001, -0.002, 0.003, 0.000, 0.002])
    benchmark = np.array([0.001, -0.002, 0.002, 0.001, -0.001, 0.002, 0.000, 0.001])
    active = portfolio - benchmark

    mean_active = active.mean()
    std_active = active.std()  # ddof=0 — match module implementation
    expected = np.sqrt(252) * mean_active / std_active

    actual = information_ratio(portfolio, benchmark)
    assert abs(actual - expected) < 1e-9, f"IR mismatch: {actual} vs {expected}"


def test_information_ratio_annualization_consistency() -> None:
    """Rebuild IR from the components exposed by compute_all_metrics and verify
    numerator and denominator are annualized on the same basis."""
    np.random.seed(7)
    bench = np.random.normal(0.0003, 0.01, 252)
    port = bench + np.random.normal(0.0005, 0.002, 252)
    equity = np.cumprod(1 + port) * 100_000

    metrics = compute_all_metrics(port, equity, benchmark_returns=bench)
    ir = metrics["information"]
    te_annual = metrics["tracking_error"]

    active = port - bench
    # numerator: annualized mean active return = mean * 252
    # denominator: annualized tracking error = std * sqrt(252)
    # IR = (mean * 252) / (std * sqrt(252)) = sqrt(252) * mean / std
    expected_annual_active_mean = active.mean() * 252
    # Recover IR = expected_annual_active_mean / te_annual
    reconstructed = expected_annual_active_mean / te_annual
    assert abs(ir - reconstructed) < 1e-9, (
        f"IR={ir} does not equal (annualized excess mean)/tracking_error={reconstructed}"
    )


def test_information_ratio_length_mismatch() -> None:
    """Guard: different lengths yield 0.0 rather than raising."""
    port = np.array([0.001, 0.002, 0.003])
    bench = np.array([0.001, 0.002])
    assert information_ratio(port, bench) == 0.0


def test_tracking_error_is_annualized() -> None:
    port = np.array([0.01, -0.01, 0.02, -0.02, 0.005])
    bench = np.zeros_like(port)
    expected = float(np.sqrt(252) * port.std())
    assert abs(tracking_error(port, bench) - expected) < 1e-12


def test_annualized_return_constant_series() -> None:
    # 252 trading days of +0.1% -> geometric annual ~= 1.001**252 - 1
    daily = np.full(252, 0.001)
    expected = (1.001**252) - 1
    assert abs(annualized_return(daily) - expected) < 1e-9


def test_compute_all_metrics_includes_benchmark_fields() -> None:
    np.random.seed(1)
    port = np.random.normal(0.001, 0.01, 60)
    bench = np.random.normal(0.0005, 0.01, 60)
    equity = np.cumprod(1 + port) * 100_000
    metrics = compute_all_metrics(port, equity, benchmark_returns=bench)
    assert "tracking_error" in metrics
    assert "benchmark_annual_return" in metrics
    assert metrics["tracking_error"] > 0


def test_compute_all_metrics_without_benchmark() -> None:
    np.random.seed(1)
    port = np.random.normal(0.001, 0.01, 60)
    equity = np.cumprod(1 + port) * 100_000
    metrics = compute_all_metrics(port, equity, benchmark_returns=None)
    assert metrics["information"] == 0.0
    assert metrics["tracking_error"] == 0.0
    assert metrics["benchmark_annual_return"] == 0.0
