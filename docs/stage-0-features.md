# Stage 0b/0c: Feature Engineering and Selection

**Files**: `src/features/technical.py`, `src/features/selection.py`
**Makefile targets**: `make features`, `make select-features`
**Commands**: `uv run python -m src.features.technical`, `uv run python -m src.features.selection`

## Purpose

Transform raw price, macro, and fundamental data from PostgreSQL into a model-ready feature matrix. The output is a Polars DataFrame saved as `data/features.parquet` (all features) and optionally `data/features_selected.parquet` (filtered features).

## Consistent Price Column Usage

When `adj_close` is available and mostly non-null, the pipeline swaps it into the `close` column at the start of `build_features()`. This means all indicator functions (SMA, EMA, RSI, MACD, Bollinger, ATR, etc.) automatically compute on dividend-adjusted prices without requiring per-function changes. After all indicators are computed, the original column names are restored before dropping absolute price columns. This ensures consistency between indicators and the target label, which also uses adj_close.

## Feature Categories

### 1. Moving Averages (scale-invariant ratios)

For each window in `[5, 10, 20, 50, 200]`:
- `sma_{w}_ratio`: `(SMA(close, w) / close) - 1`
- `ema_{w}_ratio`: `(EMA(close, w) / close) - 1`

Absolute SMA/EMA values are computed first, converted to price-relative ratios, then absolute values are dropped. This makes features scale-invariant across stocks with different price levels.

### 2. Momentum Indicators

| Feature | Formula | Interpretation |
|---|---|---|
| `rsi_14` | Relative Strength Index (14-day) | 0-100 oscillator, >70 overbought, <30 oversold |
| `macd_ratio` | MACD(12,26) / close | Trend direction, normalized |
| `macd_signal_ratio` | MACD signal(9) / close | Signal line crossover reference |
| `macd_hist` | MACD - signal | Histogram for divergence detection |
| `stoch_k` | Stochastic %K (14-day) | Position within recent high-low range (0-100) |
| `stoch_d` | Stochastic %D (3-day SMA of %K) | Smoothed stochastic |

### 3. Volatility Indicators

| Feature | Formula | Interpretation |
|---|---|---|
| `bb_upper_ratio` | `(BB_upper / close) - 1` | Distance to upper Bollinger Band |
| `bb_lower_ratio` | `(BB_lower / close) - 1` | Distance to lower Bollinger Band |
| `atr_14_ratio` | `ATR(14) / close` | Average True Range as % of price |
| `realized_vol_5d` | `rolling_std(return_1d, 5)` | Short-term (1-week) realized vol |
| `realized_vol_20d` | `rolling_std(return_1d, 20)` | Monthly realized vol |
| `realized_vol_60d` | `rolling_std(return_1d, 60)` | Quarterly realized vol |
| `mean_reversion_zscore` | `(close - SMA_20) / rolling_std_20` | Standard deviations from 20-day mean |

### 4. Volume Indicators

| Feature | Formula | Interpretation |
|---|---|---|
| `relative_volume` | `volume / SMA(volume, 20)` | Current volume vs 20-day average |
| `obv_roc_20d` | `pct_change(OBV, 20)` | On-Balance Volume rate of change |

### 5. Return Features

| Feature | Source | Interpretation |
|---|---|---|
| `return_1d` | `pct_change(adj_close, 1)` | Daily return |
| `return_5d` | `pct_change(adj_close, 5)` | Weekly return |
| `return_20d` | `pct_change(adj_close, 20)` | Monthly return |

### 6. Treasury / Macro Features

Loaded from `treasury_rates` table (12 tenors). After joining on date:

**Raw tenor values**: `month1`, `month2`, `month3`, `month6`, `year1`, `year2`, `year3`, `year5`, `year7`, `year10`, `year20`, `year30`

**Derived spreads** (8):
- `spread_10y_2y`, `spread_30y_2y`, `spread_30y_10y`, `spread_10y_1y`
- `spread_5y_2y`, `spread_30y_5y`, `spread_6m_1m`
- `yield_curve_slope` = `year30 - month3`

**Daily changes** (12): `{tenor}_change` = daily diff for each tenor

**Lagged values** (for LSTM temporal context):
- `spread_10y_2y_lag5`, `spread_10y_2y_lag20`

### 7. VIX Features

Loaded from `vix_daily` table. After joining on date:

| Feature | Formula | Interpretation |
|---|---|---|
| `vix_close` | Raw VIX close | Absolute volatility level |
| `vix_change` | `diff(vix_close)` | Daily absolute change |
| `vix_return` | `pct_change(vix_close)` | Daily percentage change |
| `vix_range` | `vix_high - vix_low` | Intraday volatility range |
| `vix_sma_5` | `SMA(vix_close, 5)` | Short-term VIX average |
| `vix_sma_20` | `SMA(vix_close, 20)` | Medium-term VIX average |
| `vix_sma20_ratio` | `(vix_close / vix_sma_20) - 1` | VIX relative to its own mean |
| `vix_percentile_252d` | `(vix - rolling_min) / (rolling_max - rolling_min)` over 252 days | Position in trailing 1-year range (0-1) |
| `vix_close_lag5` | `shift(vix_close, 5)` | VIX 5 days ago |
| `vix_close_lag20` | `shift(vix_close, 20)` | VIX 20 days ago |

### 8. Cross-Sectional Features

| Feature | Formula | Interpretation |
|---|---|---|
| `relative_strength_spy_20d` | `return_20d(stock) - return_20d(SPY)` | Outperformance vs broad market |

SPY returns are loaded from `ohlcv_daily` using `adj_close` when available.

### 9. Fundamental Features

Loaded from `key_metrics_quarterly` and `financial_ratios_quarterly` tables. JSONB data is extracted into typed columns at query time.

**Key Metrics (20 fields)**: `km_returnOnEquity`, `km_returnOnAssets`, `km_returnOnInvestedCapital`, `km_returnOnCapitalEmployed`, `km_currentRatio`, `km_earningsYield`, `km_freeCashFlowYield`, `km_evToEBITDA`, `km_netDebtToEBITDA`, `km_incomeQuality`, `km_capexToRevenue`, `km_researchAndDevelopementToRevenue`, `km_evToSales`, `km_cashConversionCycle`, `km_daysOfSalesOutstanding`, `km_daysOfInventoryOutstanding`, `km_evToFreeCashFlow`, `km_evToOperatingCashFlow`, `km_marketCap`, `km_enterpriseValue`

**Financial Ratios (20 fields)**: `fr_grossProfitMargin`, `fr_operatingProfitMargin`, `fr_netProfitMargin`, `fr_currentRatio`, `fr_quickRatio`, `fr_cashRatio`, `fr_debtToEquityRatio`, `fr_debtToAssetsRatio`, `fr_priceToEarningsRatio`, `fr_priceToBookRatio`, `fr_priceToSalesRatio`, `fr_priceToFreeCashFlowRatio`, `fr_dividendYield`, `fr_interestCoverageRatio`, `fr_financialLeverageRatio`, `fr_receivablesTurnover`, `fr_inventoryTurnover`, `fr_assetTurnover`, `fr_operatingCashFlowSalesRatio`, `fr_freeCashFlowOperatingCashFlowRatio`

**Quarter-over-Quarter changes**: For each field above, a `*_qoq` column is computed. These are computed on the quarterly DataFrames **before** the `join_asof` (forward-fill), so they represent true quarter-over-quarter changes rather than daily diffs of constant values.

**Join strategy**: `join_asof` with `strategy="backward"` by symbol on date. This forward-fills the most recent quarterly value to every subsequent trading day until the next quarter is reported.

### 10. Sector Performance Features

Loaded from `sector_performance_daily` and `stock_sectors` tables.

| Feature | Formula | Interpretation |
|---|---|---|
| `sector_avg_change` | Daily avg change for the stock's sector | Sector-level momentum |
| `sector_momentum_5d` | `SMA(sector_avg_change, 5)` | Short-term sector trend |
| `sector_momentum_20d` | `SMA(sector_avg_change, 20)` | Medium-term sector trend |
| `relative_to_sector` | `return_1d - sector_avg_change/100` | Stock vs sector performance |

### 11. Cyclical Time Encoding

Day-of-week and month-of-year effects are encoded as cyclical features using sine/cosine transforms:

| Feature | Formula |
|---|---|
| `dow_sin` | `sin(weekday * 2π / 5)` |
| `dow_cos` | `cos(weekday * 2π / 5)` |
| `moy_sin` | `sin(month * 2π / 12)` |
| `moy_cos` | `cos(month * 2π / 12)` |

### 12. Target Label

Binary classification based on forward returns:

```
forward_return = pct_change(adj_close, horizon).shift(-horizon)

target = 1 (UP)     if forward_return >= buy_threshold  (default +2.5%)
target = 0 (NOT_UP) otherwise
```

Default horizon: 21 trading days (~1 month). The `buy_threshold` is configurable per cluster.

## Columns Dropped Before Output

All absolute price columns are dropped after computing ratio features. This ensures the model never sees raw prices, only scale-invariant indicators:

- `open`, `high`, `low`, `close`, `adj_close`, `volume`, `change_percent`
- `bb_middle`, `bb_upper`, `bb_lower`, `atr_14`, `volume_sma_20`
- `macd`, `macd_signal`, `sector`
- `vix_open`, `vix_high`, `vix_low`
- All absolute `sma_{w}`, `ema_{w}` values

## Null Handling Strategy

The pipeline uses a three-tier null handling approach instead of aggressively dropping all rows with any null:

1. **Forward-fill**: Fundamental features (`km_*`, `fr_*`) are forward-filled per symbol using `pl.col(c).forward_fill().over("symbol")`. Quarterly data naturally has gaps between report dates.

2. **Median-fill**: Remaining null features are filled with the per-symbol median: `pl.col(c).fill_null(pl.col(c).median().over("symbol"))`. This preserves rows that only have nulls in non-critical features.

3. **Drop critical nulls only**: Only rows with nulls in `return_1d`, `return_5d`, `return_20d`, or `target` are dropped. These are rows at the very beginning of a stock's history (insufficient lookback) or the end (no forward return for target).

Before filling, the pipeline logs features with >50% nulls for diagnostic purposes.

## Feature Selection (Stage 0c)

**File**: `src/features/selection.py`

Applies three sequential filters:

1. **Null filter**: Drop features with >90% null values (configurable `max_null_pct`)
2. **Variance filter**: Drop features in the bottom 1% by variance (configurable `min_variance_pct`)
3. **Correlation filter**: For each pair with `|correlation| > 0.95`, drop the second feature (greedy, index-order)

**Output**:
- `data/features_selected.parquet` — filtered DataFrame
- `data/selected_features.json` — manifest listing selected feature names and count

**Integration**: When `feature_selection.enabled` is true in config:
- `src/training/train.py` reads from `features_selected.parquet` via `get_features_parquet_path(config)`
- `src/aggregation/consolidate.py` reads from `features_selected.parquet` via `get_features_parquet_path(config)`
- `src/strategy/runner.py` loads `selected_features.json` via `get_selected_feature_names(config)` and filters features at inference time

## CLI Arguments

### `technical.py`
| Flag | Default | Description |
|---|---|---|
| `--symbols` | all | Filter to specific symbols |
| `--output` | `data/features.parquet` | Output parquet path |

### `selection.py`
| Flag | Default | Description |
|---|---|---|
| `--input` | `data/features.parquet` | Input parquet |
| `--output` | `data/features_selected.parquet` | Output parquet |
| `--manifest` | `data/selected_features.json` | Feature name manifest |
