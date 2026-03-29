"""Portfolio performance metrics.

Pure functions operating on numpy arrays of daily returns.
All ratios are annualized assuming 252 trading days per year.
"""

from __future__ import annotations

import numpy as np


def sharpe_ratio(returns: np.ndarray, risk_free: float = 0.0) -> float:
    """Annualized Sharpe ratio.

    Args:
        returns: Array of daily returns.
        risk_free: Daily risk-free rate (default 0).
    """
    excess = returns - risk_free
    if len(excess) < 2 or excess.std() == 0:
        return 0.0
    return float(np.sqrt(252) * excess.mean() / excess.std())


def sortino_ratio(returns: np.ndarray, target: float = 0.0) -> float:
    """Annualized Sortino ratio (penalizes only downside volatility).

    Args:
        returns: Array of daily returns.
        target: Minimum acceptable return per day (default 0).
    """
    excess = returns - target
    downside = np.minimum(returns - target, 0.0)
    downside_std = np.sqrt(np.mean(downside ** 2))
    if downside_std == 0 or len(returns) < 2:
        return 0.0
    return float(np.sqrt(252) * excess.mean() / downside_std)


def omega_ratio(returns: np.ndarray, threshold: float = 0.0) -> float:
    """Omega ratio — ratio of gains to losses relative to a threshold.

    Captures the full return distribution without assuming normality.

    Args:
        returns: Array of daily returns.
        threshold: Return threshold (default 0).
    """
    gains = np.sum(np.maximum(returns - threshold, 0.0))
    losses = np.sum(np.maximum(threshold - returns, 0.0))
    if losses == 0:
        return float("inf") if gains > 0 else 1.0
    return float(gains / losses)


def calmar_ratio(returns: np.ndarray, equity_curve: np.ndarray) -> float:
    """Calmar ratio — annualized return / max drawdown.

    Args:
        returns: Array of daily returns.
        equity_curve: Array of portfolio values over time.
    """
    if len(equity_curve) < 2:
        return 0.0

    # Annualized return
    total_return = equity_curve[-1] / equity_curve[0] - 1
    n_years = len(returns) / 252
    if n_years <= 0:
        return 0.0
    annual_return = (1 + total_return) ** (1 / n_years) - 1

    # Max drawdown
    peak = np.maximum.accumulate(equity_curve)
    drawdowns = (equity_curve - peak) / peak
    max_dd = abs(float(drawdowns.min()))

    if max_dd == 0:
        return float("inf") if annual_return > 0 else 0.0
    return float(annual_return / max_dd)


def information_ratio(
    returns: np.ndarray, benchmark_returns: np.ndarray
) -> float:
    """Annualized Information ratio — excess return / tracking error.

    Args:
        returns: Array of portfolio daily returns.
        benchmark_returns: Array of benchmark daily returns (same length).
    """
    if len(returns) != len(benchmark_returns) or len(returns) < 2:
        return 0.0
    active_returns = returns - benchmark_returns
    tracking_error = active_returns.std()
    if tracking_error == 0:
        return 0.0
    return float(np.sqrt(252) * active_returns.mean() / tracking_error)


def max_drawdown(equity_curve: np.ndarray) -> float:
    """Maximum drawdown as a positive fraction.

    Args:
        equity_curve: Array of portfolio values.
    """
    if len(equity_curve) < 2:
        return 0.0
    peak = np.maximum.accumulate(equity_curve)
    drawdowns = (equity_curve - peak) / peak
    return float(abs(drawdowns.min()))


def compute_all_metrics(
    returns: np.ndarray,
    equity_curve: np.ndarray,
    benchmark_returns: np.ndarray | None = None,
) -> dict[str, float]:
    """Compute all portfolio metrics at once.

    Args:
        returns: Array of daily returns.
        equity_curve: Array of portfolio values.
        benchmark_returns: Optional benchmark daily returns for Information ratio.

    Returns:
        Dict with keys: sharpe, sortino, omega, calmar, information, max_drawdown.
    """
    metrics = {
        "sharpe": sharpe_ratio(returns),
        "sortino": sortino_ratio(returns),
        "omega": omega_ratio(returns),
        "calmar": calmar_ratio(returns, equity_curve),
        "max_drawdown": max_drawdown(equity_curve),
    }
    if benchmark_returns is not None and len(benchmark_returns) == len(returns):
        metrics["information"] = information_ratio(returns, benchmark_returns)
    else:
        metrics["information"] = 0.0
    return metrics
