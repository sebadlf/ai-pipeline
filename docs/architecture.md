# Architecture Overview

## Purpose

This project is a local ML pipeline for evaluating stock trading strategies on the full S&P 500 universe (~503 stocks, fetched dynamically). It runs on a Mac Mini M4 Pro (24GB RAM) using a hybrid Docker/native architecture. The pipeline produces daily BUY/SELL/HOLD recommendations with confidence scores for each stock, backed by backtested portfolio strategies with risk management.

## System Context

```
FMP API (financialmodelingprep.com)
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                     Native macOS (MPS GPU)                   │
│                                                             │
│  Ingestion ─▶ Features ─▶ Selection ─▶ Clustering          │
│  (httpx)      (Polars)    (numpy)      (sklearn)            │
│                                                             │
│  Training ─▶ Aggregation ─▶ Portfolio ─▶ Backtest ─▶ Signals│
│  (Lightning)  (PyTorch)     (scipy)     (numpy)    (runner) │
│       │           │            │           │                │
│       ▼           ▼            ▼           ▼                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Docker Compose (ml-network)              │   │
│  │  ┌─────────────────────┐  ┌────────────────────────┐ │   │
│  │  │ PostgreSQL 16       │  │ MLflow Tracking 3.10.1 │ │   │
│  │  │ + TimescaleDB       │  │ :5000                  │ │   │
│  │  │ 11 tables           │  │ Experiments, registry  │ │   │
│  │  └─────────────────────┘  └────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Why Hybrid Docker / Native

Docker on Apple Silicon runs Linux VMs. PyTorch inside Docker cannot access the MPS (Metal Performance Shaders) GPU. Training natively yields GPU acceleration. Infrastructure services (PostgreSQL, MLflow) benefit from containerization: reproducibility, isolation, easy teardown via `docker compose down`.

## 5-Stage Pipeline

The pipeline follows a strict sequential flow. Each stage reads the output of previous stages and writes its own artifacts:

```
Stage 0a: Ingestion     FMP API ──▶ PostgreSQL (7 data sources)
Stage 0b: Features      PostgreSQL ──▶ data/features.parquet
Stage 0c: Selection     features.parquet ──▶ features_selected.parquet
Stage 1:  Clustering    DB + features ──▶ data/clusters.parquet
Stage 2:  Training      features + clusters ──▶ per-cluster .ckpt models
Stage 3:  Aggregation   models + features ──▶ data/predictions.parquet
Stage 4:  Portfolio      predictions + returns ──▶ data/portfolios.parquet
Stage 5:  Backtest      portfolios + regime ──▶ backtest reports + DB
          Promotion     best checkpoints ──▶ MLflow Model Registry
          Signals       champion models + live data ──▶ BUY/SELL/HOLD
```

### Orchestration

All steps are orchestrated via Makefile targets:

```
make pipeline   # runs: ingest → features → select-features → cluster → train
                #        → aggregate → portfolio → backtest
```

Individual steps can be run independently. The pipeline is designed for daily execution with all date boundaries computed relative to `date.today()`.

## Data Flow Diagram

```
                    FMP API
                       │
            ┌──────────┼──────────┐
            ▼          ▼          ▼
         OHLCV     Treasury    VIX
        adjClose   12 tenors
        Sectors    Key Metrics
                   Fin. Ratios
                   Sector Perf
            │          │          │
            └──────────┼──────────┘
                       ▼
                  PostgreSQL
                  (11 tables)
                       │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
      technical.py  clustering.py  backtest.py
      (features)    (clusters)     (prices)
           │           │
           ▼           │
    features.parquet   │
           │           │
           ▼           │
    selection.py       │
           │           │
           ▼           │
 features_selected     │
    .parquet           │
           │           │
           ▼           ▼
        train.py ◄── clusters.parquet
           │
           ▼
     .ckpt models (per cluster)
           │
           ▼
    consolidate.py ──▶ predictions.parquet
                              │
                              ▼
                       optimizer.py ──▶ portfolios.parquet
                                              │
                                              ▼
                                       backtest.py ──▶ reports + DB
```

## Tech Stack

| Layer | Tool | Version | Purpose |
|---|---|---|---|
| Data source | FMP API | stable | OHLCV, adj close, treasury, VIX, fundamentals, sectors |
| Database | PostgreSQL + TimescaleDB | 16 | Time-series storage, 11 tables |
| Feature engineering | Polars | latest | Rolling windows, joins, transforms |
| Feature selection | numpy + Polars | latest | Null/variance/correlation filters |
| Clustering | scikit-learn | latest | KMeans, PCA, silhouette scoring |
| ML framework | PyTorch + Lightning | latest | LSTM ternary classifier |
| Portfolio optimization | scipy | latest | SLSQP multi-objective optimization |
| Experiment tracking | MLflow | 3.10.1 | Tracking, registry, artifact store |
| Dependency management | UV | latest | Fast Python package manager |
| Orchestration | Makefile | - | Task runner |
| Containerization | Docker Compose | - | Postgres + MLflow infrastructure |

## Database Schema

| Table | Purpose | Key Columns |
|---|---|---|
| `ohlcv_daily` | Daily price data | symbol, date, open, high, low, close, adj_close, volume |
| `treasury_rates` | US Treasury yields | date, month1..year30 (12 tenor columns) |
| `vix_daily` | VIX index | date, open, high, low, close |
| `key_metrics_quarterly` | Fundamental metrics | symbol, date, data (JSONB) |
| `financial_ratios_quarterly` | Financial ratios | symbol, date, data (JSONB) |
| `sector_performance_daily` | Sector returns | date, sector, average_change |
| `stock_sectors` | GICS mapping | symbol, sector |
| `cluster_assignments` | Cluster output | symbol, cluster_id, sector |
| `predictions` | Model predictions | run_date, symbol, prediction, confidence, prob_* |
| `portfolio_allocations` | Portfolio weights | run_date, profile, symbol, weight, signal |
| `backtest_results` | Backtest metrics | run_date, profile, regime, sharpe, sortino, ... |

## Configuration

All parameters are centralized in `configs/default.yaml` and loaded by `src/config.py`. Key sections:

- **ingestion**: data source, lookback period, benchmark symbols
- **features**: indicator windows, toggle flags for fundamentals/VIX/sector
- **feature_selection**: null/variance/correlation thresholds
- **target**: classification horizon, BUY/SELL thresholds
- **model**: LSTM architecture (hidden_size, num_layers, dropout, seq_len)
- **training**: optimizer params, temporal split durations, purge gap
- **clustering**: KMeans config, PCA variance ratio, feature list, per-cluster threshold overrides
- **portfolio**: 3 risk profiles with metric preferences and constraints
- **regime**: bull/bear thresholds, SMA windows
- **backtest**: initial capital, commission, risk management params

## Temporal Split Design

All date boundaries are computed relative to today for daily retraining support. A 21-day purge gap between splits prevents label leakage (matching the 21-day forward-return target horizon):

```
start ──────── train_end │ PURGE 21d │ val_start ─── val_end │ PURGE 21d │ test_start ─── today
  (17yr)                                  (1yr)                               (2yr)
```

Computed by `compute_split_dates()` in `src/config.py`. The SplitDates dataclass is passed to dataset, clustering, backtest, and aggregation modules.

## Key Design Decisions

1. **Per-cluster models**: Stocks are clustered by GICS sector + behavioral features. Each cluster gets its own LSTM model, allowing the model to specialize for stocks with similar characteristics.

2. **Symbol-boundary-aware windowing**: The sliding window dataset tracks where each symbol's data ends in the concatenated array. Windows that would cross symbol boundaries are excluded, preventing the LSTM from seeing transitions between different stocks.

3. **Consistent adj_close usage**: All price-derived indicators (SMAs, EMAs, RSI, MACD, Bollinger, ATR) are computed on dividend-adjusted close prices when available, ensuring consistency with the target labels.

4. **Smart adjClose refresh**: Instead of re-downloading 20 years of adjusted close data for all ~500 symbols daily, the pipeline probes 3 historical dates per symbol. Only symbols where values have changed (due to dividends/splits) trigger a full re-download.

5. **Feature selection integration**: When enabled, `features_selected.parquet` is consumed by training, aggregation, and inference. A JSON manifest of selected feature names ensures the runner filters to the same feature set.

6. **Three-tier null handling**: Fundamentals are forward-filled per symbol (quarterly gaps expected), remaining nulls are median-filled per symbol, and only rows with null returns/target are dropped.

## File Map

```
ai-pipeline/
├── CLAUDE.md                      # AI assistant context
├── README.md                      # User-facing documentation
├── Makefile                       # Pipeline orchestration (14 targets)
├── docker-compose.yml             # Postgres + MLflow containers
├── pyproject.toml                 # UV dependency manifest
├── configs/
│   └── default.yaml               # All hyperparameters and config
├── src/
│   ├── config.py                  # Config loading, SplitDates, helpers
│   ├── db.py                      # SQLAlchemy schema (11 tables)
│   ├── keys.py                    # Environment variable loading
│   ├── ingestion/fmp_loader.py    # Stage 0a: FMP API → PostgreSQL
│   ├── features/
│   │   ├── technical.py           # Stage 0b: Feature engineering
│   │   ├── selection.py           # Stage 0c: Feature selection
│   │   └── clustering.py          # Stage 1: Stock clustering
│   ├── models/
│   │   ├── base_model.py          # LSTMForecaster (Lightning module)
│   │   └── dataset.py             # TradingDataModule + TimeSeriesDataset
│   ├── training/train.py          # Stage 2: Per-cluster training
│   ├── aggregation/consolidate.py # Stage 3: Prediction consolidation
│   ├── portfolio/
│   │   ├── metrics.py             # Risk/return metric functions
│   │   └── optimizer.py           # Stage 4: Portfolio optimization
│   ├── evaluation/
│   │   ├── regime.py              # Market regime detection
│   │   ├── backtest.py            # Stage 5: Regime-aware backtesting
│   │   └── promote.py             # Model registry promotion
│   └── strategy/runner.py         # Signal generation from champions
├── docs/                          # This documentation
├── data/                          # Pipeline artifacts (gitignored)
├── tests/                         # pytest test suite
└── notebooks/                     # Exploration notebooks
```
