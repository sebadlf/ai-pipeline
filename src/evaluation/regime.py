"""Market regime detection using SPY data.

Classifies each trading day as bull, bear, or sideways based on
trailing returns and SMA crossover confirmation.

Usage:
    uv run python -m src.evaluation.regime
"""

from __future__ import annotations

import argparse
import datetime as dt

import polars as pl

from src.config import RegimeConfig, compute_split_dates, load_config
from src.db import get_engine


def load_benchmark_prices(
    benchmark: str,
    start_date: dt.date,
    end_date: dt.date,
) -> pl.DataFrame:
    """Load benchmark daily prices from the database.

    Args:
        benchmark: Benchmark symbol (e.g. "SPY").
        start_date: Start date.
        end_date: End date.

    Returns:
        DataFrame with columns [date, close].
    """
    engine = get_engine()
    # Load extra history for SMA computation
    lookback_buffer = dt.timedelta(days=400)  # enough for SMA-200
    query = f"""
        SELECT date, close FROM ohlcv_daily
        WHERE symbol = '{benchmark}'
          AND date >= '{start_date - lookback_buffer}'
          AND date <= '{end_date}'
        ORDER BY date
    """
    return pl.read_database(query, engine)


def detect_regimes(
    config: dict,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
) -> pl.DataFrame:
    """Classify each trading day as bull, bear, or sideways.

    Algorithm:
    - Compute trailing annualized return over lookback_days
    - Compute SMA-short and SMA-long crossover
    - Bull: annualized return > bull_threshold AND SMA-short > SMA-long
    - Bear: annualized return < bear_threshold AND SMA-short < SMA-long
    - Sideways: everything else

    Args:
        config: Full config dict.
        start_date: Start of regime detection period. Defaults to test_start.
        end_date: End of regime detection period. Defaults to today.

    Returns:
        DataFrame with columns [date, regime].
    """
    regime_cfg = RegimeConfig.from_dict(config.get("regime", {}))
    split_dates = compute_split_dates(config)

    if start_date is None:
        start_date = split_dates.test_start
    if end_date is None:
        end_date = split_dates.today

    prices_df = load_benchmark_prices(regime_cfg.benchmark, start_date, end_date)

    if prices_df.is_empty():
        return pl.DataFrame(schema={"date": pl.Date, "regime": pl.Utf8})

    prices_df = prices_df.sort("date")

    # Compute SMAs
    prices_df = prices_df.with_columns(
        pl.col("close").rolling_mean(regime_cfg.sma_short).alias("sma_short"),
        pl.col("close").rolling_mean(regime_cfg.sma_long).alias("sma_long"),
    )

    # Compute trailing annualized return
    lookback = regime_cfg.lookback_days
    prices_df = prices_df.with_columns(
        (pl.col("close") / pl.col("close").shift(lookback) - 1).alias("trailing_return"),
    ).with_columns(
        # Annualize the trailing return
        ((1 + pl.col("trailing_return")).pow(252 / lookback) - 1).alias("annual_return"),
    )

    # Classify regimes
    prices_df = prices_df.with_columns(
        pl.when(
            (pl.col("annual_return") > regime_cfg.bull_threshold)
            & (pl.col("sma_short") > pl.col("sma_long"))
        )
        .then(pl.lit("bull"))
        .when(
            (pl.col("annual_return") < regime_cfg.bear_threshold)
            & (pl.col("sma_short") < pl.col("sma_long"))
        )
        .then(pl.lit("bear"))
        .otherwise(pl.lit("sideways"))
        .alias("regime"),
    )

    # Filter to the requested date range
    result = prices_df.filter((pl.col("date") >= start_date) & (pl.col("date") <= end_date)).select(
        ["date", "regime"]
    )

    # Summary
    for regime in ["bull", "bear", "sideways"]:
        count = result.filter(pl.col("regime") == regime).height
        pct = count / len(result) * 100 if len(result) > 0 else 0
        print(f"  {regime}: {count} days ({pct:.1f}%)")

    return result


def main() -> None:
    """Detect and display market regimes."""
    parser = argparse.ArgumentParser(description="Detect market regimes")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    args = parser.parse_args()

    config = load_config(args.config)
    print("Detecting market regimes...")
    regimes = detect_regimes(config)
    print(f"\nTotal: {len(regimes)} trading days classified")


if __name__ == "__main__":
    main()
