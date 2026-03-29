"""Tests for feature engineering."""

import numpy as np
import polars as pl
import pytest

from src.features.technical import (
    add_atr,
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
    dates = pl.date_range(pl.date(2023, 1, 1), pl.date(2023, 1, 1) + pl.duration(days=n - 1), eager=True)
    close = np.cumsum(np.random.randn(n) * 0.5) + 100

    return pl.DataFrame({
        "symbol": ["TEST"] * n,
        "date": dates,
        "open": close + np.random.randn(n) * 0.1,
        "high": close + np.abs(np.random.randn(n)),
        "low": close - np.abs(np.random.randn(n)),
        "close": close,
        "volume": np.random.randint(1_000_000, 10_000_000, n),
    })


def test_add_sma(sample_ohlcv: pl.DataFrame) -> None:
    result = add_sma(sample_ohlcv, 5)
    assert "sma_5" in result.columns
    assert result["sma_5"][:4].null_count() == 4  # first 4 should be null


def test_add_ema(sample_ohlcv: pl.DataFrame) -> None:
    result = add_ema(sample_ohlcv, 10)
    assert "ema_10" in result.columns
    assert len(result) == len(sample_ohlcv)


def test_add_rsi(sample_ohlcv: pl.DataFrame) -> None:
    result = add_rsi(sample_ohlcv, 14)
    assert "rsi_14" in result.columns
    # RSI should be between 0 and 100 for non-null values
    valid = result.filter(pl.col("rsi_14").is_not_null())
    assert valid["rsi_14"].min() >= 0
    assert valid["rsi_14"].max() <= 100


def test_add_macd(sample_ohlcv: pl.DataFrame) -> None:
    result = add_macd(sample_ohlcv)
    assert "macd" in result.columns
    assert "macd_signal" in result.columns
    assert "macd_hist" in result.columns


def test_add_bollinger_bands(sample_ohlcv: pl.DataFrame) -> None:
    result = add_bollinger_bands(sample_ohlcv)
    assert "bb_upper" in result.columns
    assert "bb_middle" in result.columns
    assert "bb_lower" in result.columns
    valid = result.drop_nulls(subset=["bb_upper", "bb_lower"])
    assert (valid["bb_upper"] >= valid["bb_lower"]).all()


def test_add_atr(sample_ohlcv: pl.DataFrame) -> None:
    result = add_atr(sample_ohlcv, 14)
    assert "atr_14" in result.columns
    valid = result.filter(pl.col("atr_14").is_not_null())
    assert (valid["atr_14"] >= 0).all()


def test_add_volume_sma(sample_ohlcv: pl.DataFrame) -> None:
    result = add_volume_sma(sample_ohlcv, 20)
    assert "volume_sma_20" in result.columns
    assert "relative_volume" in result.columns


def test_add_returns(sample_ohlcv: pl.DataFrame) -> None:
    result = add_returns(sample_ohlcv)
    assert "return_1d" in result.columns
    assert "return_5d" in result.columns
    assert "return_20d" in result.columns
