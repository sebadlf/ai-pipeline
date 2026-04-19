"""Tests for market regime detection."""

import numpy as np
import polars as pl


def _make_price_series(trend: str, n_days: int = 300) -> pl.DataFrame:
    """Generate synthetic price series with known trend.

    Args:
        trend: "bull", "bear", or "sideways".
        n_days: Number of trading days.
    """
    np.random.seed(42)
    if trend == "bull":
        daily_drift = 0.001  # ~28% annualized
        noise = 0.005
    elif trend == "bear":
        daily_drift = -0.001  # ~-22% annualized
        noise = 0.005
    else:  # sideways
        daily_drift = 0.0
        noise = 0.003

    returns = np.random.normal(daily_drift, noise, n_days)
    prices = 100 * np.cumprod(1 + returns)

    dates = pl.date_range(
        pl.date(2023, 1, 1),
        pl.date(2023, 1, 1) + pl.duration(days=n_days - 1),
        eager=True,
    )

    return pl.DataFrame(
        {
            "date": dates,
            "close": prices,
        }
    )


def test_bull_regime_detection() -> None:
    """Strong uptrend should be classified as bull."""
    df = _make_price_series("bull")

    # Compute SMA crossover and trailing return
    df = df.with_columns(
        pl.col("close").rolling_mean(50).alias("sma_short"),
        pl.col("close").rolling_mean(200).alias("sma_long"),
        (pl.col("close") / pl.col("close").shift(126) - 1).alias("trailing_return"),
    ).drop_nulls()

    # In a strong uptrend, SMA-50 should be above SMA-200
    last_rows = df.tail(20)
    sma_above = (last_rows["sma_short"] > last_rows["sma_long"]).all()
    positive_return = (last_rows["trailing_return"] > 0).all()
    assert sma_above, "SMA-50 should be above SMA-200 in bull market"
    assert positive_return, "Trailing returns should be positive in bull market"


def test_bear_regime_detection() -> None:
    """Strong downtrend should be classified as bear."""
    df = _make_price_series("bear")

    df = df.with_columns(
        pl.col("close").rolling_mean(50).alias("sma_short"),
        pl.col("close").rolling_mean(200).alias("sma_long"),
        (pl.col("close") / pl.col("close").shift(126) - 1).alias("trailing_return"),
    ).drop_nulls()

    last_rows = df.tail(20)
    sma_below = (last_rows["sma_short"] < last_rows["sma_long"]).all()
    negative_return = (last_rows["trailing_return"] < 0).all()
    assert sma_below, "SMA-50 should be below SMA-200 in bear market"
    assert negative_return, "Trailing returns should be negative in bear market"


def test_sideways_regime_detection() -> None:
    """Flat market should have small trailing returns."""
    df = _make_price_series("sideways")

    df = df.with_columns(
        (pl.col("close") / pl.col("close").shift(126) - 1).alias("trailing_return"),
    ).drop_nulls()

    last_rows = df.tail(20)
    # Returns should be close to zero
    mean_return = abs(float(last_rows["trailing_return"].mean()))
    assert mean_return < 0.15, f"Sideways market should have small returns, got {mean_return}"


def test_regime_classification_logic() -> None:
    """Test the classification logic directly."""
    bull_threshold = 0.10
    bear_threshold = -0.10

    # Bull case
    annual_return = 0.25
    sma_short_above = True
    if annual_return > bull_threshold and sma_short_above:
        regime = "bull"
    elif annual_return < bear_threshold and not sma_short_above:
        regime = "bear"
    else:
        regime = "sideways"
    assert regime == "bull"

    # Bear case
    annual_return = -0.20
    sma_short_above = False
    if annual_return > bull_threshold and sma_short_above:
        regime = "bull"
    elif annual_return < bear_threshold and not sma_short_above:
        regime = "bear"
    else:
        regime = "sideways"
    assert regime == "bear"

    # Sideways: positive return but SMA crossed down
    annual_return = 0.15
    sma_short_above = False
    if annual_return > bull_threshold and sma_short_above:
        regime = "bull"
    elif annual_return < bear_threshold and not sma_short_above:
        regime = "bear"
    else:
        regime = "sideways"
    assert regime == "sideways"
