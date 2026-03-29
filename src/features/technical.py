"""Technical indicator feature engineering with Polars.

Usage:
    uv run python -m src.features.technical
    uv run python -m src.features.technical --symbols AAPL MSFT
"""

from __future__ import annotations

import argparse

import polars as pl

from src.config import load_config
from src.db import get_engine


def load_ohlcv(symbols: list[str] | None = None) -> pl.DataFrame:
    """Load OHLCV data from PostgreSQL into a Polars DataFrame.

    Args:
        symbols: Optional list of symbols to filter. None = all.
    """
    query = "SELECT * FROM ohlcv_daily"
    if symbols:
        placeholders = ", ".join(f"'{s}'" for s in symbols)
        query += f" WHERE symbol IN ({placeholders})"
    query += " ORDER BY symbol, date"

    return pl.read_database(query, get_engine())


def add_sma(df: pl.DataFrame, window: int) -> pl.DataFrame:
    """Add Simple Moving Average column."""
    return df.with_columns(
        pl.col("close").rolling_mean(window).over("symbol").alias(f"sma_{window}")
    )


def add_ema(df: pl.DataFrame, window: int) -> pl.DataFrame:
    """Add Exponential Moving Average column."""
    return df.with_columns(
        pl.col("close").ewm_mean(span=window).over("symbol").alias(f"ema_{window}")
    )


def add_rsi(df: pl.DataFrame, window: int = 14) -> pl.DataFrame:
    """Add Relative Strength Index column."""
    delta = pl.col("close").diff()
    gain = delta.clip(lower_bound=0).rolling_mean(window).over("symbol")
    loss = (-delta.clip(upper_bound=0)).rolling_mean(window).over("symbol")

    return df.with_columns(
        (100 - 100 / (1 + gain / loss)).alias(f"rsi_{window}")
    )


def add_macd(
    df: pl.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> pl.DataFrame:
    """Add MACD, signal line, and histogram columns."""
    macd_line = (
        pl.col("close").ewm_mean(span=fast).over("symbol")
        - pl.col("close").ewm_mean(span=slow).over("symbol")
    )
    return df.with_columns(
        macd_line.alias("macd"),
    ).with_columns(
        pl.col("macd").ewm_mean(span=signal).over("symbol").alias("macd_signal"),
    ).with_columns(
        (pl.col("macd") - pl.col("macd_signal")).alias("macd_hist"),
    )


def add_bollinger_bands(df: pl.DataFrame, window: int = 20) -> pl.DataFrame:
    """Add Bollinger Bands (upper, middle, lower)."""
    return df.with_columns(
        pl.col("close").rolling_mean(window).over("symbol").alias("bb_middle"),
        pl.col("close").rolling_std(window).over("symbol").alias("_bb_std"),
    ).with_columns(
        (pl.col("bb_middle") + 2 * pl.col("_bb_std")).alias("bb_upper"),
        (pl.col("bb_middle") - 2 * pl.col("_bb_std")).alias("bb_lower"),
    ).drop("_bb_std")


def add_atr(df: pl.DataFrame, window: int = 14) -> pl.DataFrame:
    """Add Average True Range column."""
    high = pl.col("high")
    low = pl.col("low")
    prev_close = pl.col("close").shift(1).over("symbol")

    tr = pl.max_horizontal(
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    )
    return df.with_columns(
        tr.rolling_mean(window).over("symbol").alias(f"atr_{window}")
    )


def add_volume_sma(df: pl.DataFrame, window: int = 20) -> pl.DataFrame:
    """Add volume SMA and relative volume columns."""
    return df.with_columns(
        pl.col("volume").rolling_mean(window).over("symbol").alias(f"volume_sma_{window}"),
    ).with_columns(
        (pl.col("volume") / pl.col(f"volume_sma_{window}")).alias("relative_volume"),
    )


def load_treasury_rates() -> pl.DataFrame:
    """Load treasury rates from PostgreSQL into a Polars DataFrame."""
    query = "SELECT date, year2, year10, year30 FROM treasury_rates ORDER BY date"
    return pl.read_database(query, get_engine())


def add_treasury_features(df: pl.DataFrame, treasury: pl.DataFrame) -> pl.DataFrame:
    """Join treasury rates and add derived spread/change features."""
    df = df.join(treasury, on="date", how="left")

    return df.with_columns(
        (pl.col("year10") - pl.col("year2")).alias("spread_10y_2y"),
        (pl.col("year30") - pl.col("year2")).alias("spread_30y_2y"),
        (pl.col("year30") - pl.col("year10")).alias("spread_30y_10y"),
        pl.col("year2").diff().over("symbol").alias("year2_change"),
        pl.col("year10").diff().over("symbol").alias("year10_change"),
        pl.col("year30").diff().over("symbol").alias("year30_change"),
    )


def load_vix() -> pl.DataFrame:
    """Load VIX daily data from PostgreSQL into a Polars DataFrame."""
    query = "SELECT date, open AS vix_open, high AS vix_high, low AS vix_low, close AS vix_close FROM vix_daily ORDER BY date"
    return pl.read_database(query, get_engine())


def add_vix_features(df: pl.DataFrame, vix: pl.DataFrame) -> pl.DataFrame:
    """Join VIX data and add derived volatility features."""
    df = df.join(vix, on="date", how="left")

    return df.with_columns(
        pl.col("vix_close").diff().over("symbol").alias("vix_change"),
        pl.col("vix_close").pct_change().over("symbol").alias("vix_return"),
        (pl.col("vix_high") - pl.col("vix_low")).alias("vix_range"),
        pl.col("vix_close").rolling_mean(5).over("symbol").alias("vix_sma_5"),
        pl.col("vix_close").rolling_mean(20).over("symbol").alias("vix_sma_20"),
        (pl.col("vix_close") / pl.col("vix_close").rolling_mean(20).over("symbol") - 1).alias("vix_sma20_ratio"),
    )


def add_returns(df: pl.DataFrame) -> pl.DataFrame:
    """Add daily and multi-period return columns."""
    return df.with_columns(
        pl.col("close").pct_change().over("symbol").alias("return_1d"),
        pl.col("close").pct_change(5).over("symbol").alias("return_5d"),
        pl.col("close").pct_change(20).over("symbol").alias("return_20d"),
    )


def add_ternary_target(
    df: pl.DataFrame,
    horizon: int = 63,
    buy_threshold: float = 0.05,
    sell_threshold: float = 0.03,
) -> pl.DataFrame:
    """Add ternary classification target: HOLD=0, BUY=1, SELL=2.

    Args:
        df: DataFrame with close prices.
        horizon: Number of trading days ahead (63 ~ 3 months).
        buy_threshold: Minimum positive return for BUY (e.g. 0.05 = +5%).
        sell_threshold: Minimum negative return for SELL (e.g. 0.03 = -3%, applied as negative).
    """
    forward_return = pl.col("close").pct_change(horizon).shift(-horizon).over("symbol")
    return df.with_columns(
        pl.when(forward_return >= buy_threshold)
        .then(pl.lit(1))
        .when(forward_return <= -sell_threshold)
        .then(pl.lit(2))
        .otherwise(pl.lit(0))
        .cast(pl.Int64)
        .alias("target"),
    )


def build_features(df: pl.DataFrame, config: dict) -> pl.DataFrame:
    """Apply all configured feature engineering steps.

    Args:
        df: Raw OHLCV DataFrame.
        config: Full config dict.
    """
    features_cfg = config.get("features", {})
    windows = features_cfg.get("windows", [5, 10, 20, 50, 200])

    # Moving averages for each window
    for w in windows:
        df = add_sma(df, w)
        df = add_ema(df, w)

    # Technical indicators
    df = add_rsi(df)
    df = add_macd(df)
    df = add_bollinger_bands(df)
    df = add_atr(df)
    df = add_volume_sma(df)
    df = add_returns(df)

    # Treasury rates (year2, year10, year30 + spreads + daily changes)
    if features_cfg.get("treasury_rates", True):
        treasury = load_treasury_rates()
        if len(treasury) > 0:
            df = add_treasury_features(df, treasury)
        else:
            print("  Warning: no treasury rate data found, skipping")

    # VIX (close, change, range, SMAs, ratio)
    if features_cfg.get("vix", True):
        vix = load_vix()
        if len(vix) > 0:
            df = add_vix_features(df, vix)
        else:
            print("  Warning: no VIX data found, skipping")

    # Convert absolute indicators to price-relative ratios (scale-invariant)
    close = pl.col("close")
    ratio_exprs = []
    for w in windows:
        ratio_exprs.append((pl.col(f"sma_{w}") / close - 1).alias(f"sma_{w}_ratio"))
        ratio_exprs.append((pl.col(f"ema_{w}") / close - 1).alias(f"ema_{w}_ratio"))
    ratio_exprs.extend([
        (pl.col("bb_upper") / close - 1).alias("bb_upper_ratio"),
        (pl.col("bb_lower") / close - 1).alias("bb_lower_ratio"),
        (pl.col("atr_14") / close).alias("atr_14_ratio"),
        (pl.col("macd") / close).alias("macd_ratio"),
        (pl.col("macd_signal") / close).alias("macd_signal_ratio"),
    ])
    df = df.with_columns(ratio_exprs)

    # Target: ternary classification BUY/SELL/HOLD (needs close column)
    target_cfg = config.get("target", {})
    df = add_ternary_target(
        df,
        horizon=target_cfg.get("horizon", 63),
        buy_threshold=target_cfg.get("buy_threshold", 0.05),
        sell_threshold=target_cfg.get("sell_threshold", 0.03),
    )

    # Drop absolute price columns (keep only scale-invariant features)
    abs_cols = (
        ["open", "high", "low", "close", "volume", "change_percent", "bb_middle",
         "bb_upper", "bb_lower", "atr_14", "volume_sma_20", "macd", "macd_signal"]
        + [f"sma_{w}" for w in windows]
        + [f"ema_{w}" for w in windows]
    )
    df = df.drop([c for c in abs_cols if c in df.columns])

    return df


def main() -> None:
    """Generate features and save to parquet."""
    config = load_config()
    features_cfg = config["features"]

    parser = argparse.ArgumentParser(description="Generate technical features")
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--output", default="data/features.parquet")
    args = parser.parse_args()

    print("Loading OHLCV data...")
    df = load_ohlcv(args.symbols)
    print(f"  Loaded {len(df)} rows")

    print("Building features...")
    df = build_features(df, config)

    # Drop adj_close if entirely null
    if "adj_close" in df.columns and df["adj_close"].null_count() == len(df):
        df = df.drop("adj_close")

    # Drop rows with nulls in any feature or target column
    initial_len = len(df)
    feature_cols = [c for c in df.columns if c not in {"id", "symbol", "date"}]
    df = df.drop_nulls(subset=feature_cols)
    print(f"  Dropped {initial_len - len(df)} rows with null target")

    # Save to parquet
    from pathlib import Path
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(args.output)
    print(f"  Saved {len(df)} rows to {args.output}")
    print(f"  Columns: {df.columns}")


if __name__ == "__main__":
    main()
