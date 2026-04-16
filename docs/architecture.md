# Architecture Overview

## Purpose

This project is a local ML pipeline for evaluating stock trading strategies on the full S&P 500 universe (~503 stocks, fetched dynamically). It runs on a Mac Mini M4 Pro (24GB RAM) using a hybrid Docker/native architecture. The pipeline produces prob_up predictions (probability of rising >= threshold) for each stock, used to construct risk-profiled long-only portfolios backed by regime-aware backtesting.

## System Context

```
FMP API (financialmodelingprep.com)
    |
    v
+-------------------------------------------------------------+
|                     Native macOS (MPS GPU)                   |
|                                                             |
|  Ingestion -> Features -> Selection -> Normalize -> Cluster |
|  (httpx)      (Polars)    (numpy)      (Z-score)   (sklearn)|
|                                                             |
|  Optuna -> Training -> Promote -> Aggregate -> Portfolio    |
|  (search)  (Lightning) (MLflow)  (ensemble)   (scipy)      |
|                                                             |
|  Backtest -> Signals                                        |
|  (numpy)    (runner)                                        |
|       |           |            |           |                |
|       v           v            v           v                |
|  +------------------------------------------------------+  |
|  |              Docker Compose (ml-network)               |  |
|  |  +---------------------+  +------------------------+  |  |
|  |  | PostgreSQL 16       |  | MLflow Tracking 3.10.1 |  |  |
|  |  | + TimescaleDB       |  | :5000                  |  |  |
|  |  | 11 tables           |  | Experiments, registry  |  |  |
|  |  | + Optuna studies    |  |                        |  |  |
|  |  +---------------------+  +------------------------+  |  |
|  +------------------------------------------------------+  |
+-------------------------------------------------------------+
```

## Why Hybrid Docker / Native

Docker on Apple Silicon runs Linux VMs. PyTorch inside Docker cannot access the MPS (Metal Performance Shaders) GPU. Training natively yields GPU acceleration. Infrastructure services (PostgreSQL, MLflow) benefit from containerization: reproducibility, isolation, easy teardown via `docker compose down`.

## 7-Stage Pipeline

The pipeline follows a strict sequential flow. Each stage reads the output of previous stages and writes its own artifacts:

```
Stage 0a: Ingestion       FMP API --> PostgreSQL (7 data sources)
Stage 0b: Features        PostgreSQL --> data/features.parquet
Stage 0c: Selection       features.parquet --> features_selected.parquet
Stage 0d: Normalization   features_selected.parquet --> features_normalized.parquet
Stage 1:  Clustering      DB + features --> data/clusters.parquet
Stage 2:  Training        Optuna optimization + ensemble training per cluster
Stage 3:  Promotion       Cascading elimination --> MLflow Model Registry champions
Stage 4:  Aggregation     Champion models + features --> data/predictions.parquet
Stage 5:  Portfolio       Predictions + returns --> data/portfolios.parquet
Stage 6:  Backtest        Portfolios + regime --> backtest reports + DB
Stage 7:  Signals         Champion models + live data --> prob_up predictions
```

### Orchestration

All steps are orchestrated via Makefile targets:

```
make pipeline   # runs: features -> select-features -> normalize -> cluster
                #        -> train-clusters -> promote -> aggregate
                #        -> portfolio -> backtest
```

Individual steps can be run independently. The pipeline is designed for daily execution with all date boundaries computed relative to `date.today()`.

## Data Flow Diagram

```
                    FMP API
                       |
            +----------+----------+
            v          v          v
         OHLCV     Treasury    VIX
        adjClose   12 tenors
        Sectors    Key Metrics
                   Fin. Ratios
                   Sector Perf
            |          |          |
            +----------+----------+
                       v
                  PostgreSQL
                  (11 tables)
                       |
           +-----------+-----------+
           v           v           v
      technical.py  clustering.py  backtest.py
      (features)    (clusters)     (prices)
           |           |
           v           |
    features.parquet   |
           |           |
           v           |
    selection.py       |
           |           |
           v           |
 features_selected     |
    .parquet           |
           |           |
           v           |
    normalize.py       |
           |           |
           v           |
 features_normalized   |
    .parquet           |
           |           v
           +---> optimize.py <--- clusters.parquet
                     |
                     v
              train.py (per-cluster Optuna + ensemble top-3)
                     |
                     v
               .ckpt models (3 per cluster)
                     |
                     v
              promote.py --> MLflow Model Registry (champion alias)
                     |
                     v
           consolidate.py --> predictions.parquet
                                    |
                                    v
                             optimizer.py --> portfolios.parquet
                                                    |
                                                    v
                                             backtest.py --> reports + DB
```

## Tech Stack

| Layer | Tool | Version | Purpose |
|---|---|---|---|
| Data source | FMP API | stable | OHLCV, adj close, treasury, VIX, fundamentals, sectors |
| Database | PostgreSQL + TimescaleDB | 16 | Time-series storage, 11 tables, Optuna studies |
| Feature engineering | Polars | latest | Rolling windows, joins, transforms |
| Feature selection | numpy + Polars | latest | Null/variance/correlation/MI filters |
| Normalization | numpy | latest | Percentile clipping + Z-score |
| Clustering | scikit-learn | latest | KMeans, PCA, silhouette scoring |
| ML framework | PyTorch + Lightning | latest | LSTM binary classifier (UP/NOT_UP) with FocalLoss |
| Hyperparameter optimization | Optuna | latest | Precision-at-threshold objective, PostgreSQL persistence |
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
| `predictions` | Model predictions | run_date, symbol, cluster_id, prob_up |
| `portfolio_allocations` | Portfolio weights | run_date, profile, symbol, weight, prob_up |
| `backtest_results` | Backtest metrics | run_date, profile, regime, sharpe, sortino, ... |

## Configuration

All parameters are centralized in `configs/default.yaml` and loaded by `src/config.py`. Key sections:

- **ingestion**: data source, lookback period, benchmark symbols
- **features**: indicator windows, toggle flags for fundamentals/VIX/sector
- **feature_selection**: null/variance/correlation/MI thresholds
- **normalization**: percentile clipping bounds, output paths
- **target**: classification horizon (21 days), buy_threshold (+2.5%)
- **model**: LSTM architecture defaults (fallback only; Optuna overrides in practice)
- **training**: optimizer params, temporal split durations, purge gap, Optuna search space and fixed params
- **clustering**: KMeans config, PCA variance ratio, 20 clustering features, per-cluster threshold overrides
- **portfolio**: 3 risk profiles with metric preferences and constraints
- **regime**: bull/bear thresholds, SMA windows
- **backtest**: initial capital, commission, slippage, risk management params
- **promotion**: cascading elimination thresholds, walk-forward stability config

## Temporal Split Design

All date boundaries are computed relative to today for daily retraining support. A 21-day purge gap between splits prevents label leakage (matching the 21-day forward-return target horizon):

```
start ---------- train_end | PURGE 21d | val_start --- val_end | PURGE 21d | test_start --- today
  (~6yr)                                    (1yr)                               (1yr)
```

Computed by `compute_split_dates()` in `src/config.py`. The SplitDates dataclass is passed to dataset, clustering, backtest, and aggregation modules.

## Key Design Decisions

1. **Per-cluster models**: Stocks are clustered by behavioral, fundamental, and macro-sensitivity features using global KMeans (prod) or sector-based (dev). Each cluster gets its own LSTM model with Optuna-optimized hyperparameters, allowing specialization for stocks with similar characteristics.

2. **Symbol-boundary-aware windowing**: The sliding window dataset tracks where each symbol's data ends in the concatenated array. Windows that would cross symbol boundaries are excluded, preventing the LSTM from seeing transitions between different stocks.

3. **Consistent adj_close usage**: All price-derived indicators (SMAs, EMAs, RSI, MACD, Bollinger, ATR) are computed on dividend-adjusted close prices when available, ensuring consistency with the target labels.

4. **Smart adjClose refresh**: Instead of re-downloading 20 years of adjusted close data for all ~500 symbols daily, the pipeline probes 3 historical dates per symbol. Only symbols where values have changed (due to dividends/splits) trigger a full re-download.

5. **Feature selection + normalization pipeline**: Features are filtered (null/variance/correlation/MI), then normalized (percentile clipping + Z-score with training-set statistics). Stats are persisted for consistent training/inference normalization.

6. **Three-tier null handling**: Fundamentals are forward-filled per symbol (quarterly gaps expected), remaining nulls are median-filled per symbol, and only rows with null returns/target are dropped.

7. **Overfitting mitigation**: Multiple layers of defense -- Optuna gap penalty (penalizes train_acc - val_acc > 30%), reduced model capacity (max 128 hidden, max 3 layers), aggressive regularization ranges (dropout up to 0.65), data augmentation (noise injection + feature masking), dual early stopping, and ensemble top-3 for robustness.

8. **Generalization-adjusted champion selection**: Champion models are selected not just by validation precision but by a score that penalizes val-to-test precision gaps, preferring models that generalize well to unseen data.

## File Map

```
ai-pipeline/
+-- CLAUDE.md                      # AI assistant context
+-- README.md                      # User-facing documentation
+-- Makefile                       # Pipeline orchestration
+-- docker-compose.yml             # Postgres + MLflow containers
+-- pyproject.toml                 # UV dependency manifest
+-- configs/
|   +-- default.yaml               # All hyperparameters and config
+-- src/
|   +-- config.py                  # Config loading, SplitDates, helpers
|   +-- db.py                      # SQLAlchemy schema (11 tables)
|   +-- keys.py                    # Environment variable loading
|   +-- ingestion/fmp_loader.py    # Stage 0a: FMP API -> PostgreSQL
|   +-- features/
|   |   +-- technical.py           # Stage 0b: Feature engineering
|   |   +-- selection.py           # Stage 0c: Feature selection
|   |   +-- normalize.py           # Stage 0d: Normalization (clip + Z-score)
|   |   +-- clustering.py          # Stage 1: Stock clustering
|   +-- models/
|   |   +-- base_model.py          # LSTMForecaster (Lightning module) with FocalLoss
|   |   +-- dataset.py             # TradingDataModule + TimeSeriesDataset + augmentation
|   +-- training/
|   |   +-- optimize.py            # Optuna hyperparameter optimization (per-cluster)
|   |   +-- train.py               # Stage 2: Per-cluster ensemble training
|   +-- evaluation/
|   |   +-- precision_eval.py      # Precision-at-threshold walk-forward evaluation
|   |   +-- promote.py             # Stage 3: Cascading model promotion
|   |   +-- champion.py            # Champion checkpoint loader from MLflow registry
|   |   +-- regime.py              # Market regime detection (bull/bear/sideways)
|   |   +-- backtest.py            # Stage 6: Regime-aware portfolio backtesting
|   |   +-- clean_runs.py          # MLflow run cleanup utility
|   +-- aggregation/consolidate.py # Stage 4: Weighted ensemble prediction consolidation
|   +-- portfolio/
|   |   +-- metrics.py             # Risk/return metric functions
|   |   +-- optimizer.py           # Stage 5: Portfolio optimization
|   +-- strategy/runner.py         # Stage 7: Signal generation from champions
+-- docs/                          # This documentation
+-- data/                          # Pipeline artifacts (gitignored)
+-- tests/                         # pytest test suite
+-- notebooks/                     # Exploration notebooks
```
