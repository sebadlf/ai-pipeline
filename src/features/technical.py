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


_TREASURY_TENORS = [
    "month1", "month2", "month3", "month6",
    "year1", "year2", "year3", "year5", "year7", "year10", "year20", "year30",
]


def load_treasury_rates() -> pl.DataFrame:
    """Load all 12 treasury rate tenors from PostgreSQL."""
    cols = ", ".join(_TREASURY_TENORS)
    query = f"SELECT date, {cols} FROM treasury_rates ORDER BY date"
    schema = {t: pl.Float64 for t in _TREASURY_TENORS}
    schema["date"] = pl.Date
    return pl.read_database(query, get_engine(), schema_overrides=schema)


def add_treasury_features(df: pl.DataFrame, treasury: pl.DataFrame) -> pl.DataFrame:
    """Join treasury rates and add spreads, yield curve slope, and daily changes."""
    df = df.join(treasury, on="date", how="left")

    spread_exprs = [
        (pl.col("year10") - pl.col("year2")).alias("spread_10y_2y"),
        (pl.col("year30") - pl.col("year2")).alias("spread_30y_2y"),
        (pl.col("year30") - pl.col("year10")).alias("spread_30y_10y"),
        (pl.col("year10") - pl.col("year1")).alias("spread_10y_1y"),
        (pl.col("year5") - pl.col("year2")).alias("spread_5y_2y"),
        (pl.col("year30") - pl.col("year5")).alias("spread_30y_5y"),
        (pl.col("month6") - pl.col("month1")).alias("spread_6m_1m"),
        (pl.col("year30") - pl.col("month3")).alias("yield_curve_slope"),
    ]
    df = df.with_columns(spread_exprs)

    change_exprs = [
        pl.col(t).diff().over("symbol").alias(f"{t}_change")
        for t in _TREASURY_TENORS
    ]
    return df.with_columns(change_exprs)


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


_KEY_METRIC_FIELDS = [
    "returnOnEquity", "returnOnAssets", "returnOnInvestedCapital",
    "returnOnCapitalEmployed", "currentRatio", "earningsYield",
    "freeCashFlowYield", "evToEBITDA", "netDebtToEBITDA", "incomeQuality",
    "capexToRevenue", "researchAndDevelopementToRevenue", "evToSales",
    "cashConversionCycle", "daysOfSalesOutstanding", "daysOfInventoryOutstanding",
    "evToFreeCashFlow", "evToOperatingCashFlow", "marketCap", "enterpriseValue",
]

_RATIO_FIELDS = [
    "grossProfitMargin", "operatingProfitMargin", "netProfitMargin",
    "currentRatio", "quickRatio", "cashRatio",
    "debtToEquityRatio", "debtToAssetsRatio",
    "priceToEarningsRatio", "priceToBookRatio", "priceToSalesRatio",
    "priceToFreeCashFlowRatio", "dividendYield", "interestCoverageRatio",
    "financialLeverageRatio", "receivablesTurnover", "inventoryTurnover",
    "assetTurnover", "operatingCashFlowSalesRatio",
    "freeCashFlowOperatingCashFlowRatio",
]


def load_key_metrics() -> pl.DataFrame:
    """Load key metrics from PostgreSQL, extracting selected fields from JSONB."""
    extracts = ", ".join(
        f"(data->>'{f}')::double precision AS km_{f.lower()}" for f in _KEY_METRIC_FIELDS
    )
    query = f"SELECT symbol, date, {extracts} FROM key_metrics_quarterly ORDER BY symbol, date"
    return pl.read_database(query, get_engine())


def load_financial_ratios() -> pl.DataFrame:
    """Load financial ratios from PostgreSQL, extracting selected fields from JSONB."""
    extracts = ", ".join(
        f"(data->>'{f}')::double precision AS fr_{f.lower()}" for f in _RATIO_FIELDS
    )
    query = f"SELECT symbol, date, {extracts} FROM financial_ratios_quarterly ORDER BY symbol, date"
    return pl.read_database(query, get_engine())


def add_fundamental_features(
    df: pl.DataFrame,
    km_df: pl.DataFrame,
    fr_df: pl.DataFrame,
) -> pl.DataFrame:
    """Forward-fill quarterly fundamentals to daily rows via asof join.

    QoQ changes are computed on the quarterly DataFrames (where each row
    is a distinct quarter) BEFORE the asof join, so they represent true
    quarter-over-quarter changes rather than daily diffs of constant values.
    """
    df = df.sort(["symbol", "date"])
    km_df = km_df.sort(["symbol", "date"])
    fr_df = fr_df.sort(["symbol", "date"])

    km_qoq_exprs = [
        pl.col(f"km_{f.lower()}").pct_change().over("symbol").alias(f"km_{f.lower()}_qoq")
        for f in _KEY_METRIC_FIELDS
    ]
    km_df = km_df.with_columns(km_qoq_exprs)

    fr_qoq_exprs = [
        pl.col(f"fr_{f.lower()}").pct_change().over("symbol").alias(f"fr_{f.lower()}_qoq")
        for f in _RATIO_FIELDS
    ]
    fr_df = fr_df.with_columns(fr_qoq_exprs)

    df = df.join_asof(km_df, on="date", by="symbol", strategy="backward")
    df = df.join_asof(fr_df, on="date", by="symbol", strategy="backward")

    return df


def load_sector_performance() -> pl.DataFrame:
    """Load historical sector performance from PostgreSQL."""
    query = "SELECT date, sector, average_change FROM sector_performance_daily ORDER BY sector, date"
    return pl.read_database(query, get_engine())


def load_stock_sectors() -> pl.DataFrame:
    """Load stock-to-sector mapping from PostgreSQL."""
    query = "SELECT symbol, sector FROM stock_sectors"
    return pl.read_database(query, get_engine())


def add_sector_features(
    df: pl.DataFrame,
    sector_perf: pl.DataFrame,
    stock_sectors: pl.DataFrame,
) -> pl.DataFrame:
    """Add sector momentum and relative performance features."""
    df = df.join(stock_sectors, on="symbol", how="left")

    sector_perf = sector_perf.sort(["sector", "date"])
    sector_perf = sector_perf.with_columns(
        pl.col("average_change").rolling_mean(5).over("sector").alias("sector_momentum_5d"),
        pl.col("average_change").rolling_mean(20).over("sector").alias("sector_momentum_20d"),
    )
    sector_perf = sector_perf.rename({"average_change": "sector_avg_change"})

    df = df.join(sector_perf, on=["date", "sector"], how="left")

    if "return_1d" in df.columns:
        df = df.with_columns(
            (pl.col("return_1d") - pl.col("sector_avg_change") / 100).alias("relative_to_sector"),
        )

    return df


def add_realized_volatility(df: pl.DataFrame) -> pl.DataFrame:
    """Add multi-window realized volatility from rolling std of daily returns."""
    return df.with_columns(
        pl.col("return_1d").rolling_std(5).over("symbol").alias("realized_vol_5d"),
        pl.col("return_1d").rolling_std(20).over("symbol").alias("realized_vol_20d"),
        pl.col("return_1d").rolling_std(60).over("symbol").alias("realized_vol_60d"),
    )


def add_vix_percentile(df: pl.DataFrame) -> pl.DataFrame:
    """Add VIX percentile rank over trailing 252 trading days (0-1 scale).

    Uses rolling min/max to approximate percentile efficiently:
    percentile = (vix - rolling_min) / (rolling_max - rolling_min).
    """
    return df.with_columns(
        pl.col("vix_close").rolling_min(252, min_samples=20).over("symbol").alias("_vix_min_252"),
        pl.col("vix_close").rolling_max(252, min_samples=20).over("symbol").alias("_vix_max_252"),
    ).with_columns(
        (
            (pl.col("vix_close") - pl.col("_vix_min_252"))
            / (pl.col("_vix_max_252") - pl.col("_vix_min_252"))
        ).alias("vix_percentile_252d"),
    ).drop("_vix_min_252", "_vix_max_252")


def add_relative_strength_spy(df: pl.DataFrame) -> pl.DataFrame:
    """Add relative strength vs SPY benchmark (stock return minus SPY return).

    Loads SPY returns from DB and joins to compute cross-sectional
    relative performance at 20d horizon.
    """
    spy_query = "SELECT date, close, adj_close FROM ohlcv_daily WHERE symbol = 'SPY' ORDER BY date"
    spy_df = pl.read_database(spy_query, get_engine())
    if spy_df.is_empty():
        return df

    spy_price = "adj_close" if "adj_close" in spy_df.columns and spy_df["adj_close"].null_count() < len(spy_df) else "close"
    spy_df = spy_df.sort("date").with_columns(
        pl.col(spy_price).pct_change(20).alias("spy_return_20d"),
    ).select(["date", "spy_return_20d"])

    df = df.join(spy_df, on="date", how="left")
    df = df.with_columns(
        (pl.col("return_20d") - pl.col("spy_return_20d")).alias("relative_strength_spy_20d"),
    ).drop("spy_return_20d")
    return df


def add_stochastic(df: pl.DataFrame, k_window: int = 14, d_window: int = 3) -> pl.DataFrame:
    """Add Stochastic Oscillator (%K and %D)."""
    return df.with_columns(
        pl.col("high").rolling_max(k_window).over("symbol").alias("_stoch_high"),
        pl.col("low").rolling_min(k_window).over("symbol").alias("_stoch_low"),
    ).with_columns(
        (
            (pl.col("close") - pl.col("_stoch_low"))
            / (pl.col("_stoch_high") - pl.col("_stoch_low"))
            * 100
        ).alias("stoch_k"),
    ).with_columns(
        pl.col("stoch_k").rolling_mean(d_window).over("symbol").alias("stoch_d"),
    ).drop("_stoch_high", "_stoch_low")


def add_obv(df: pl.DataFrame) -> pl.DataFrame:
    """Add On-Balance Volume rate of change (normalized, scale-invariant)."""
    sign = pl.when(pl.col("close").diff().over("symbol") > 0).then(pl.col("volume")) \
        .when(pl.col("close").diff().over("symbol") < 0).then(-pl.col("volume")) \
        .otherwise(pl.lit(0))

    return df.with_columns(
        sign.cum_sum().over("symbol").alias("_obv"),
    ).with_columns(
        pl.col("_obv").pct_change(20).over("symbol").alias("obv_roc_20d"),
    ).with_columns(
        pl.when(pl.col("obv_roc_20d").is_infinite())
        .then(None)
        .otherwise(pl.col("obv_roc_20d"))
        .alias("obv_roc_20d"),
    ).drop("_obv")


def add_mean_reversion_zscore(df: pl.DataFrame, window: int = 20) -> pl.DataFrame:
    """Add mean-reversion z-score: how many std devs price is from its SMA."""
    return df.with_columns(
        pl.col("close").rolling_mean(window).over("symbol").alias("_mr_mean"),
        pl.col("close").rolling_std(window).over("symbol").alias("_mr_std"),
    ).with_columns(
        ((pl.col("close") - pl.col("_mr_mean")) / pl.col("_mr_std")).alias("mean_reversion_zscore"),
    ).drop("_mr_mean", "_mr_std")


def add_cyclical_time(df: pl.DataFrame) -> pl.DataFrame:
    """Add sin/cos encoding of day-of-week and month-of-year."""
    import math

    return df.with_columns(
        pl.col("date").dt.weekday().alias("_dow"),
        pl.col("date").dt.month().alias("_moy"),
    ).with_columns(
        (pl.col("_dow").cast(pl.Float64) * 2 * math.pi / 5).sin().alias("dow_sin"),
        (pl.col("_dow").cast(pl.Float64) * 2 * math.pi / 5).cos().alias("dow_cos"),
        (pl.col("_moy").cast(pl.Float64) * 2 * math.pi / 12).sin().alias("moy_sin"),
        (pl.col("_moy").cast(pl.Float64) * 2 * math.pi / 12).cos().alias("moy_cos"),
    ).drop("_dow", "_moy")


def add_lagged_macros(df: pl.DataFrame) -> pl.DataFrame:
    """Add lagged VIX and treasury spread features for temporal context."""
    lag_exprs = []
    for lag in [5, 20]:
        if "vix_close" in df.columns:
            lag_exprs.append(
                pl.col("vix_close").shift(lag).over("symbol").alias(f"vix_close_lag{lag}")
            )
        if "spread_10y_2y" in df.columns:
            lag_exprs.append(
                pl.col("spread_10y_2y").shift(lag).over("symbol").alias(f"spread_10y_2y_lag{lag}")
            )
    if lag_exprs:
        df = df.with_columns(lag_exprs)
    return df


def add_returns(df: pl.DataFrame) -> pl.DataFrame:
    """Add daily and multi-period return columns using adj_close when available."""
    price_col = "adj_close" if "adj_close" in df.columns and df["adj_close"].null_count() < len(df) else "close"
    return df.with_columns(
        pl.col(price_col).pct_change().over("symbol").alias("return_1d"),
        pl.col(price_col).pct_change(5).over("symbol").alias("return_5d"),
        pl.col(price_col).pct_change(20).over("symbol").alias("return_20d"),
    )


def add_binary_target(
    df: pl.DataFrame,
    horizon: int = 21,
    buy_threshold: float = 0.025,
) -> pl.DataFrame:
    """Add binary classification target: UP (1) if forward return >= threshold, else NOT_UP (0).

    Args:
        df: DataFrame with close/adj_close prices.
        horizon: Number of trading days ahead.
        buy_threshold: Minimum positive return for UP class.
    """
    price_col = "adj_close" if "adj_close" in df.columns and df["adj_close"].null_count() < len(df) else "close"
    forward_return = pl.col(price_col).pct_change(horizon).shift(-horizon).over("symbol")
    return df.with_columns(
        pl.when(forward_return >= buy_threshold)
        .then(pl.lit(1))
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

    # Use adj_close as the primary price column when available.
    # Swap it into "close" so all indicator functions use adjusted prices.
    _has_adj_close = "adj_close" in df.columns and df["adj_close"].null_count() < len(df)
    if _has_adj_close:
        df = df.rename({"close": "_unadj_close", "adj_close": "close"})

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
    df = add_stochastic(df)
    df = add_obv(df)
    df = add_mean_reversion_zscore(df)
    df = add_realized_volatility(df)
    df = add_cyclical_time(df)

    # Treasury rates (all 12 tenors + spreads + daily changes)
    if features_cfg.get("treasury_rates", True):
        treasury = load_treasury_rates()
        if len(treasury) > 0:
            df = add_treasury_features(df, treasury)
        else:
            print("  Warning: no treasury rate data found, skipping")

    # VIX (close, change, range, SMAs, ratio, percentile)
    if features_cfg.get("vix", True):
        vix = load_vix()
        if len(vix) > 0:
            df = add_vix_features(df, vix)
            df = add_vix_percentile(df)
        else:
            print("  Warning: no VIX data found, skipping")

    # Lagged macro features (requires VIX/treasury to be joined first)
    df = add_lagged_macros(df)

    # Relative strength vs SPY
    try:
        df = add_relative_strength_spy(df)
    except Exception as e:
        print(f"  Warning: relative strength vs SPY skipped ({e})")

    # Fundamentals (key metrics + financial ratios, forward-filled quarterly)
    if features_cfg.get("fundamentals", False):
        try:
            km_df = load_key_metrics()
            fr_df = load_financial_ratios()
            if len(km_df) > 0 and len(fr_df) > 0:
                df = add_fundamental_features(df, km_df, fr_df)
                print(f"  Added {len(_KEY_METRIC_FIELDS)} key metrics + {len(_RATIO_FIELDS)} ratios")
            else:
                print("  Warning: no fundamental data found, skipping")
        except Exception as e:
            print(f"  Warning: fundamentals skipped ({e})")

    # Sector performance
    if features_cfg.get("sector_performance", False):
        try:
            sp_df = load_sector_performance()
            ss_df = load_stock_sectors()
            if len(sp_df) > 0 and len(ss_df) > 0:
                df = add_sector_features(df, sp_df, ss_df)
                print("  Added sector performance features")
            else:
                print("  Warning: no sector performance data found, skipping")
        except Exception as e:
            print(f"  Warning: sector performance skipped ({e})")

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

    # Target: binary classification UP/NOT_UP (needs close or adj_close)
    target_cfg = config.get("target", {})
    df = add_binary_target(
        df,
        horizon=target_cfg.get("horizon", 21),
        buy_threshold=target_cfg.get("buy_threshold", 0.025),
    )

    # Restore original column name if we swapped adj_close -> close
    if _has_adj_close:
        df = df.rename({"close": "adj_close", "_unadj_close": "close"})

    # Drop absolute price columns (keep only scale-invariant features)
    abs_cols = (
        ["open", "high", "low", "close", "adj_close", "volume", "change_percent",
         "bb_middle", "bb_upper", "bb_lower", "atr_14", "volume_sma_20",
         "macd", "macd_signal", "sector",
         "vix_open", "vix_high", "vix_low"]
        + [f"sma_{w}" for w in windows]
        + [f"ema_{w}" for w in windows]
    )
    df = df.drop([c for c in abs_cols if c in df.columns])

    return df


def fill_nulls(df: pl.DataFrame) -> pl.DataFrame:
    """Fill nulls in feature columns: forward-fill fundamentals, median-fill the rest.

    Args:
        df: DataFrame with feature columns (output of build_features).

    Returns:
        DataFrame with nulls filled. Rows with null critical columns are dropped.
    """
    meta_cols = {"id", "symbol", "date"}
    feature_cols = [c for c in df.columns if c not in meta_cols]

    # Step 0: Convert float NaN to Polars null so fill operations work uniformly
    float_cols = [c for c in feature_cols if df[c].dtype in (pl.Float32, pl.Float64)]
    if float_cols:
        df = df.with_columns([pl.col(c).fill_nan(None) for c in float_cols])

    # Step 1: Forward-fill fundamental features per symbol (quarterly gaps are expected)
    fundamental_cols = [c for c in feature_cols if c.startswith(("km_", "fr_"))]
    if fundamental_cols:
        df = df.with_columns(
            [pl.col(c).forward_fill().over("symbol") for c in fundamental_cols]
        )

    # Step 2: Fill remaining nulls with per-symbol median for numeric features
    remaining_null_cols = [c for c in feature_cols if df[c].null_count() > 0 and c != "target"]
    if remaining_null_cols:
        median_fills = []
        for c in remaining_null_cols:
            col_median = pl.col(c).median().over("symbol")
            median_fills.append(pl.col(c).fill_null(col_median).alias(c))
        df = df.with_columns(median_fills)

    # Step 3: Drop rows that still have nulls in critical columns only
    critical_cols = [c for c in ["return_1d", "return_5d", "return_20d", "target"]
                     if c in df.columns]
    if critical_cols:
        df = df.drop_nulls(subset=critical_cols)

    return df


def main() -> None:
    """Generate features and save to parquet."""
    from src.config import resolve_dev_sectors

    config = load_config()

    parser = argparse.ArgumentParser(description="Generate technical features")
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--output", default="data/features.parquet")
    args = parser.parse_args()

    # In dev mode, filter to configured sectors
    symbols = args.symbols
    if symbols is None:
        dev_sectors = resolve_dev_sectors(config)
        if dev_sectors:
            sector_set = set(dev_sectors)
            query = "SELECT symbol, sector FROM stock_sectors ORDER BY symbol"
            sectors_df = pl.read_database(query, get_engine())
            symbols = sectors_df.filter(pl.col("sector").is_in(sector_set))["symbol"].to_list()
            print(f"Dev mode: filtered to {len(symbols)} symbols in sectors: {', '.join(dev_sectors)}")

    print("Loading OHLCV data...")
    df = load_ohlcv(symbols)
    print(f"  Loaded {len(df)} rows")

    print("Building features...")
    df = build_features(df, config)

    initial_len = len(df)
    df = fill_nulls(df)

    meta_cols = {"id", "symbol", "date"}
    feature_cols = [c for c in df.columns if c not in meta_cols]

    dropped = initial_len - len(df)
    print(f"  Dropped {dropped:,} rows with critical nulls ({dropped/max(initial_len,1):.1%})")

    # Save to parquet
    from pathlib import Path
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(args.output)
    print(f"  Saved {len(df):,} rows to {args.output}")
    print(f"  Features: {len(feature_cols)} columns")


if __name__ == "__main__":
    main()
