# Stage 0a: Data Ingestion

**File**: `src/ingestion/fmp_loader.py`
**Makefile target**: `make ingest`
**Command**: `uv run python -m src.ingestion.fmp_loader`

## Purpose

Fetch financial data from the Financial Modeling Prep (FMP) API and upsert it into PostgreSQL. This is the first step of the pipeline and the only step that communicates with an external service.

## Data Sources (7)

| Source | FMP Endpoint | DB Table | Granularity | Description |
|---|---|---|---|---|
| OHLCV | `/stable/historical-price-eod/full` | `ohlcv_daily` | Daily per symbol | Open, High, Low, Close, Volume, change_percent |
| Adjusted Close | `/stable/historical-price-eod/dividend-adjusted` | `ohlcv_daily.adj_close` | Daily per symbol | Dividend-adjusted close price (separate column update) |
| Treasury Rates | `/stable/treasury-rates` | `treasury_rates` | Daily | 12 US Treasury tenors (1M through 30Y) |
| VIX | `/stable/historical-price-eod/full?symbol=^VIX` | `vix_daily` | Daily | CBOE Volatility Index |
| Key Metrics | `/stable/key-metrics/{symbol}?period=quarter` | `key_metrics_quarterly` | Quarterly | ~47 fundamental fields stored as JSONB |
| Financial Ratios | `/stable/ratios/{symbol}?period=quarter` | `financial_ratios_quarterly` | Quarterly | ~66 ratio fields stored as JSONB |
| Sector Performance | `/stable/historical-sector-performance` | `sector_performance_daily` | Daily per sector | Average daily change per GICS sector |
| GICS Sectors | `/stable/profile/{symbol}` | `stock_sectors` | Static | Maps each symbol to its GICS sector name |

### Symbol Universe

By default, symbols come from the FMP S&P 500 constituents endpoint (`/stable/sp500-constituents-list`). The config can override with a static list. Benchmark symbols (default: SPY) are always included regardless of the symbol source.

### Date Range

The start date is computed as `today - ingestion.start_years_back` years (default: 20 years). End date defaults to today.

## Smart adjClose Refresh

The `adj_close` field is retroactively recalculated by FMP whenever a company pays dividends or executes stock splits. Naive re-downloading of all ~500 symbols' full 20-year history on every run is wasteful.

### Probe-and-Refresh Mechanism

For each symbol, the pipeline probes 3 historical dates and compares the FMP value against the stored value:

```
Probe dates:
  1. ~30 days ago   (detects recent dividends)
  2. ~180 days ago  (detects quarterly dividends)
  3. ~730 days ago  (detects splits or old dividends)

If ANY probe differs by > $0.001 from stored value → full re-download
If ALL probes match → skip (no corporate action changed history)
If symbol has no adj_close in DB yet → full download
```

**Implementation**: `check_adjclose_changed(engine, symbol, api_key)` fetches single-day adjClose from FMP for each probe date and compares against `SELECT adj_close FROM ohlcv_daily WHERE symbol = ? AND date = ?`.

**Impact**: On a typical day, 1-5 S&P 500 stocks pay dividends. Instead of ~500 full-history downloads, the pipeline makes ~1500 lightweight single-day probes plus ~5 full re-downloads.

**Override**: `--force-adjclose` bypasses probing and forces full re-download for all symbols.

## Upsert Strategy

All data uses `INSERT ... ON CONFLICT DO UPDATE` for idempotent writes:

- **OHLCV**: Conflict on `(symbol, date)` → update all price/volume fields
- **Treasury rates**: Conflict on `(date)` → update all 12 tenor columns
- **VIX**: Conflict on `(date)` → update OHLC
- **Key metrics / ratios**: Conflict on `(symbol, date)` → update JSONB data column
- **Sector performance**: Conflict on `(date, sector)` → update average_change
- **Sectors**: Conflict on `(symbol)` → update sector

This means the ingestion step is safe to re-run at any time without creating duplicates.

## Error Handling

- HTTP 402 (Payment Required) errors from FMP are caught per-symbol. The symbol is skipped and ingestion continues for remaining symbols.
- Other HTTP errors are logged and the symbol is skipped.
- The `--skip-*` flags allow bypassing individual data sources during development.

## CLI Arguments

| Flag | Default | Description |
|---|---|---|
| `--symbols` | S&P 500 + benchmarks | Override symbol list |
| `--start` | `today - 20yr` | Start date (YYYY-MM-DD) |
| `--end` | today | End date |
| `--skip-treasury` | false | Skip treasury rates |
| `--skip-vix` | false | Skip VIX data |
| `--skip-sectors` | false | Skip GICS sector mapping |
| `--skip-adjclose` | false | Skip adjusted close updates |
| `--force-adjclose` | false | Force full adjClose re-download |
| `--skip-fundamentals` | false | Skip key metrics + ratios |
| `--skip-sector-perf` | false | Skip sector performance |

## Database Schema Details

### `ohlcv_daily`
```sql
CREATE TABLE ohlcv_daily (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    date DATE NOT NULL,
    open FLOAT NOT NULL,
    high FLOAT NOT NULL,
    low FLOAT NOT NULL,
    close FLOAT NOT NULL,
    adj_close FLOAT,           -- nullable, filled by separate step
    volume BIGINT NOT NULL,
    change_percent FLOAT,
    UNIQUE (symbol, date)
);
```

### `treasury_rates`
```sql
CREATE TABLE treasury_rates (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    month1 FLOAT, month2 FLOAT, month3 FLOAT, month6 FLOAT,
    year1 FLOAT, year2 FLOAT, year3 FLOAT, year5 FLOAT,
    year7 FLOAT, year10 FLOAT, year20 FLOAT, year30 FLOAT
);
```

### `key_metrics_quarterly` / `financial_ratios_quarterly`
```sql
CREATE TABLE key_metrics_quarterly (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    date DATE NOT NULL,
    fiscal_year INT,
    period VARCHAR,             -- e.g. "Q1", "Q2"
    data JSONB NOT NULL,        -- raw API response stored as-is
    UNIQUE (symbol, date)
);
```

The JSONB approach allows storing all ~47 (key metrics) or ~66 (ratios) fields without schema migration when FMP adds or removes fields. Specific fields are extracted at query time in the feature engineering step.

## Execution Order in `main()`

1. Parse CLI args and load config
2. Resolve symbol list (S&P 500 or static)
3. Fetch and upsert GICS sectors (unless `--skip-sectors`)
4. For each symbol: fetch and upsert OHLCV
5. Fetch and upsert treasury rates (global, not per-symbol)
6. Fetch and upsert VIX data (global)
7. For each symbol: smart adjClose probe → conditional full download
8. For each symbol: fetch and upsert key metrics quarterly
9. For each symbol: fetch and upsert financial ratios quarterly
10. For each sector: fetch and upsert sector performance
