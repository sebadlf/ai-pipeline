"""Tests for feature engineering."""

import numpy as np
import polars as pl
import pytest

from src.features.normalize import (
    _apply_quantile_normal,
    _fit_quantile_knots,
)
from src.features.technical import (
    add_atr,
    add_binary_target,
    add_bollinger_bands,
    add_ema,
    add_macd,
    add_returns,
    add_rsi,
    add_sma,
    add_volume_sma,
)


@pytest.fixture
def sample_ohlcv() -> pl.DataFrame:
    """Create sample OHLCV data for testing."""
    np.random.seed(42)
    n = 100
    dates = pl.date_range(
        pl.date(2023, 1, 1), pl.date(2023, 1, 1) + pl.duration(days=n - 1), eager=True
    )
    close = np.cumsum(np.random.randn(n) * 0.5) + 100

    return pl.DataFrame(
        {
            "symbol": ["TEST"] * n,
            "date": dates,
            "open": close + np.random.randn(n) * 0.5,
            "high": close + abs(np.random.randn(n)),
            "low": close - abs(np.random.randn(n)),
            "close": close,
            "volume": np.random.randint(1000, 10000, n),
        }
    )


def test_add_sma(sample_ohlcv: pl.DataFrame) -> None:
    """SMA should be computed correctly."""
    result = add_sma(sample_ohlcv, 5)
    assert "sma_5" in result.columns
    # First 4 values should be null (not enough data)
    assert result["sma_5"][:4].null_count() == 4


def test_add_ema(sample_ohlcv: pl.DataFrame) -> None:
    """EMA should be computed."""
    result = add_ema(sample_ohlcv, 10)
    assert "ema_10" in result.columns


def test_add_rsi(sample_ohlcv: pl.DataFrame) -> None:
    """RSI should be between 0 and 100."""
    result = add_rsi(sample_ohlcv, 14)
    assert "rsi_14" in result.columns
    valid = result.filter(pl.col("rsi_14").is_not_null())
    assert valid["rsi_14"].min() >= 0
    assert valid["rsi_14"].max() <= 100


def test_add_macd(sample_ohlcv: pl.DataFrame) -> None:
    """MACD should produce macd and signal line."""
    result = add_macd(sample_ohlcv)
    assert "macd" in result.columns
    assert "macd_signal" in result.columns


def test_add_bollinger_bands(sample_ohlcv: pl.DataFrame) -> None:
    """Bollinger bands should produce 3 columns."""
    result = add_bollinger_bands(sample_ohlcv, 20)
    assert "bb_upper" in result.columns
    assert "bb_middle" in result.columns
    assert "bb_lower" in result.columns


def test_add_atr(sample_ohlcv: pl.DataFrame) -> None:
    """ATR should be positive."""
    result = add_atr(sample_ohlcv, 14)
    assert "atr_14" in result.columns
    valid = result.filter(pl.col("atr_14").is_not_null())
    assert valid["atr_14"].min() >= 0


def test_add_volume_sma(sample_ohlcv: pl.DataFrame) -> None:
    """Volume SMA should be computed."""
    result = add_volume_sma(sample_ohlcv, 20)
    assert "volume_sma_20" in result.columns


def test_add_returns(sample_ohlcv: pl.DataFrame) -> None:
    """Returns should be computed for multiple periods."""
    result = add_returns(sample_ohlcv)
    assert "return_1d" in result.columns
    assert "return_5d" in result.columns
    assert "return_20d" in result.columns


def test_add_binary_target(sample_ohlcv: pl.DataFrame) -> None:
    """Binary target should produce values 0 (NOT_UP) and 1 (UP)."""
    result = add_binary_target(sample_ohlcv, horizon=5, buy_threshold=0.02)
    assert "target" in result.columns
    valid = result.filter(pl.col("target").is_not_null())
    unique_vals = set(valid["target"].unique().to_list())
    assert unique_vals.issubset({0, 1}), f"Unexpected target values: {unique_vals}"


def test_binary_target_thresholds() -> None:
    """Verify that binary threshold correctly separates UP/NOT_UP."""
    n = 20
    close = [100.0] * n
    # Row 0: close=100, row 5: close=110 -> +10% -> UP (1)
    close[5] = 110.0
    # Row 1: close=100, row 6: close=90 -> -10% -> NOT_UP (0)
    close[6] = 90.0
    # Row 2: close=100, row 7: close=101 -> +1% -> NOT_UP (0)
    close[7] = 101.0

    df = pl.DataFrame(
        {
            "symbol": ["TEST"] * n,
            "date": pl.date_range(
                pl.date(2023, 1, 1), pl.date(2023, 1, 1) + pl.duration(days=n - 1), eager=True
            ),
            "close": close,
        }
    )

    result = add_binary_target(df, horizon=5, buy_threshold=0.05)
    targets = result["target"].to_list()
    # Row 0: +10% > +5% -> UP (1)
    assert targets[0] == 1
    # Row 1: -10% < +5% -> NOT_UP (0)
    assert targets[1] == 0
    # Row 2: +1% < +5% -> NOT_UP (0)
    assert targets[2] == 0


def test_quantile_normal_normalizes_heavy_tailed_distribution() -> None:
    """Rank-based quantile-normal transform yields ~unit variance even on
    distributions where linear z-score (with percentile clipping) does not.

    Acceptance criterion for BEC-41: normalization produces std ≈ 1 on a
    synthetic distribution whose bulk is concentrated so tightly that
    clipping at [p01, p99] would collapse it to near-zero variance.
    """
    rng = np.random.default_rng(11)
    # Heavy-tailed fundamental-like distribution: 99% of mass in a narrow
    # band with small std, 1% split across large positive/negative tails.
    # Clipping at p01/p99 trims the tails, leaving the narrow bulk — whose
    # inter-sample variance is tiny relative to the raw tail scale, so the
    # effective post-clip z-score std collapses well below 1.
    n = 5000
    bulk = rng.normal(loc=0.25, scale=0.01, size=int(0.99 * n))
    tail_pos = rng.uniform(low=50.0, high=100.0, size=int(0.005 * n))
    tail_neg = rng.uniform(low=-100.0, high=-50.0, size=int(0.005 * n))
    heavy = np.concatenate([bulk, tail_pos, tail_neg])
    rng.shuffle(heavy)

    # Fit knots on the same data (as the normalize step would on training
    # rows) and apply to the full series.
    knots = _fit_quantile_knots(heavy, n_knots=256)
    transformed = _apply_quantile_normal(heavy, knots)

    std = float(np.std(transformed))
    assert 0.7 <= std <= 1.3, (
        f"quantile-normal transform yielded std={std:.3f} on a heavy-tailed "
        "distribution; expected ~1.0 (BEC-41)."
    )
