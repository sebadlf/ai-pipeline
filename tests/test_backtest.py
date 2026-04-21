"""Tests for portfolio backtesting."""

import datetime as dt
import math
from unittest.mock import MagicMock

import numpy as np
import polars as pl
import pytest

from src.evaluation.backtest import (
    DEFAULT_REGRESSION_THRESHOLD,
    MIN_ANNUALIZATION_WINDOW,
    MIN_DRAWDOWN_PCT_FOR_METRICS,
    MIN_TRADES_FOR_METRICS,
    BacktestResult,
    RegressionFlag,
    RegressionGuardResult,
    _sharpe_drop_pct,
    check_regression_guard,
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


# ---------------------------------------------------------------------------
# Regression guard unit tests
# ---------------------------------------------------------------------------


def _make_engine_mock(prior_date: dt.date | None, prior_rows: list[tuple]) -> MagicMock:
    """Build a mock SQLAlchemy engine for the regression guard.

    Args:
        prior_date: The MAX(run_date) the first query returns (None = no rows).
        prior_rows: Rows returned for the second query (profile, regime, sharpe).
    """
    engine = MagicMock()
    conn_ctx = MagicMock()
    conn = MagicMock()
    conn_ctx.__enter__ = MagicMock(return_value=conn)
    conn_ctx.__exit__ = MagicMock(return_value=False)
    engine.connect.return_value = conn_ctx

    # First call returns prior_date row; second call returns sharpe rows.
    prior_date_result = MagicMock()
    prior_date_result.fetchone.return_value = (prior_date,) if prior_date else None

    prior_sharpe_result = MagicMock()
    prior_sharpe_result.fetchall.return_value = prior_rows

    conn.execute.side_effect = [prior_date_result, prior_sharpe_result]
    return engine


def _make_results(sharpe_map: dict[tuple[str, str], float]) -> list[BacktestResult]:
    """Build a minimal list of BacktestResult objects for testing."""
    results = []
    for (profile, regime), sharpe in sharpe_map.items():
        r = BacktestResult()
        r.profile = profile
        r.regime = regime
        r.sharpe_ratio = sharpe
        results.append(r)
    return results


class TestSharpeDropPct:
    def test_no_drop(self) -> None:
        assert _sharpe_drop_pct(1.0, 1.0) == 0.0

    def test_30_pct_drop(self) -> None:
        assert abs(_sharpe_drop_pct(1.0, 0.7) - 0.30) < 1e-9

    def test_improvement(self) -> None:
        # Current better than previous → negative drop → no flag
        assert _sharpe_drop_pct(1.0, 1.5) < 0.0

    def test_non_finite_previous(self) -> None:
        assert _sharpe_drop_pct(float("nan"), 1.0) == 0.0

    def test_non_finite_current(self) -> None:
        assert _sharpe_drop_pct(1.0, float("nan")) == 0.0

    def test_zero_previous(self) -> None:
        # Guard against divide-by-zero
        assert _sharpe_drop_pct(0.0, 1.0) == 0.0


class TestCheckRegressionGuard:
    def test_skipped_when_no_prior_run(self) -> None:
        engine = _make_engine_mock(prior_date=None, prior_rows=[])
        results = _make_results({("moderate", "sideways"): 1.2})
        guard = check_regression_guard(results, engine=engine)
        assert guard.skipped is True
        assert guard.has_regression is False

    def test_no_flag_when_sharpe_stable(self) -> None:
        prior = dt.date(2025, 1, 1)
        engine = _make_engine_mock(
            prior_date=prior,
            prior_rows=[("moderate", "sideways", 1.2), ("moderate", "bull", 1.5)],
        )
        # Current is the same — no drop
        results = _make_results({("moderate", "sideways"): 1.2, ("moderate", "bull"): 1.5})
        guard = check_regression_guard(results, engine=engine)
        assert guard.skipped is False
        assert guard.has_regression is False
        assert guard.previous_run_date == prior

    def test_flag_when_sharpe_drops_more_than_threshold(self) -> None:
        prior = dt.date(2025, 1, 1)
        engine = _make_engine_mock(
            prior_date=prior,
            prior_rows=[("moderate", "sideways", 1.0)],
        )
        # 50% drop — exceeds default 30% threshold
        results = _make_results({("moderate", "sideways"): 0.5})
        guard = check_regression_guard(results, engine=engine)
        assert guard.has_regression is True
        assert len(guard.flags) == 1
        flag = guard.flags[0]
        assert flag.profile == "moderate"
        assert flag.regime == "sideways"
        assert abs(flag.drop_pct - 0.50) < 1e-9

    def test_no_flag_when_drop_is_below_threshold(self) -> None:
        prior = dt.date(2025, 1, 1)
        engine = _make_engine_mock(
            prior_date=prior,
            prior_rows=[("moderate", "sideways", 1.0)],
        )
        # 20% drop — below default 30% threshold
        results = _make_results({("moderate", "sideways"): 0.80})
        guard = check_regression_guard(results, engine=engine, threshold=0.30)
        assert guard.has_regression is False

    def test_custom_threshold(self) -> None:
        prior = dt.date(2025, 1, 1)
        engine = _make_engine_mock(
            prior_date=prior,
            prior_rows=[("moderate", "sideways", 1.0)],
        )
        # 20% drop triggers with a custom 10% threshold
        results = _make_results({("moderate", "sideways"): 0.80})
        guard = check_regression_guard(results, engine=engine, threshold=0.10)
        assert guard.has_regression is True

    def test_skipped_when_cell_missing_in_current(self) -> None:
        prior = dt.date(2025, 1, 1)
        engine = _make_engine_mock(
            prior_date=prior,
            prior_rows=[("moderate", "sideways", 1.0)],
        )
        # Current results don't contain (moderate, sideways)
        results = _make_results({("aggressive", "bull"): 2.0})
        guard = check_regression_guard(
            results, engine=engine, guard_cells=[("moderate", "sideways")]
        )
        assert guard.has_regression is False

    def test_skipped_on_db_error(self) -> None:
        engine = MagicMock()
        conn_ctx = MagicMock()
        conn = MagicMock()
        conn_ctx.__enter__ = MagicMock(return_value=conn)
        conn_ctx.__exit__ = MagicMock(return_value=False)
        engine.connect.return_value = conn_ctx
        conn.execute.side_effect = RuntimeError("DB down")
        results = _make_results({("moderate", "sideways"): 1.0})
        guard = check_regression_guard(results, engine=engine)
        assert guard.skipped is True

    def test_multiple_flags_in_one_run(self) -> None:
        prior = dt.date(2025, 1, 1)
        engine = _make_engine_mock(
            prior_date=prior,
            prior_rows=[
                ("moderate", "sideways", 2.0),
                ("moderate", "bull", 3.0),
                ("moderate", "bear", 0.5),
            ],
        )
        # All drop by > 30%
        results = _make_results(
            {
                ("moderate", "sideways"): 1.0,  # -50%
                ("moderate", "bull"): 1.5,  # -50%
                ("moderate", "bear"): 0.2,  # -60%
            }
        )
        guard = check_regression_guard(
            results,
            engine=engine,
            guard_cells=[
                ("moderate", "sideways"),
                ("moderate", "bull"),
                ("moderate", "bear"),
            ],
        )
        assert guard.has_regression is True
        assert len(guard.flags) == 3

    def test_regression_guard_result_dataclass(self) -> None:
        result = RegressionGuardResult()
        assert result.has_regression is False
        assert result.skipped is False
        flag = RegressionFlag(
            profile="moderate",
            regime="sideways",
            previous_sharpe=1.0,
            current_sharpe=0.5,
            drop_pct=0.5,
        )
        result.flags.append(flag)
        assert result.has_regression is True

    def test_default_threshold_is_30_pct(self) -> None:
        assert DEFAULT_REGRESSION_THRESHOLD == 0.30
