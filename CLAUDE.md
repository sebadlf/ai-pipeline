# CLAUDE.md — Trading ML Pipeline

## Project overview

Local ML pipeline for evaluating stock trading strategies on the full S&P 500 universe (~503 stocks, fetched dynamically from the FMP API). Runs on a Mac Mini M4 Pro (24GB RAM) using a hybrid architecture: infrastructure in Docker, compute native on macOS to leverage MPS GPU acceleration. The pipeline uses a 5-stage architecture: stock clustering, per-cluster model training, prediction aggregation, portfolio optimization, and regime-aware backtesting.

## Architecture — 5-Stage Pipeline

### Stage 1: Stock Clustering
- Divides stocks first by GICS sector, then clusters within each sector using KMeans on behavioral features (return profile, volatility, volume, RSI, beta)
- Output: cluster assignments (`data/clusters.parquet`, `cluster_assignments` table)

### Stage 2: Per-Cluster Model Training
- Trains one LSTM model per cluster for binary classification: UP/NOT_UP
  - **UP (1)**: stock rises ≥ buy_threshold (default +2.5%) in 21 trading days
  - **NOT_UP (0)**: everything else
- Model output is `prob_up` — the probability of UP. This is the sole signal used downstream
- buy_threshold is configurable per cluster
- Each cluster gets its own MLflow experiment (`cluster/{cluster_id}`)

### Stage 3: Result Aggregation
- Consolidates `prob_up` predictions from all per-cluster models into unified results
- Output: predictions table with `prob_up` per symbol (`data/predictions.parquet`)

### Stage 4: Portfolio Design (3 profiles, long-only)

Stocks with `prob_up >= min_prob_up` (per profile) are candidates for portfolio inclusion.

**Aggressive Portfolio** (maximize return):
- Primary: Sortino | Complementary: Omega | Validation: Information ratio
- min_prob_up: 0.70 | max_positions: 25

**Moderate Portfolio** (risk/return balance):
- Primary: Sharpe | Complementary: Calmar | Validation: Sortino
- min_prob_up: 0.75 | max_positions: 20

**Conservative Portfolio** (capital preservation):
- Primary: Calmar | Complementary: Sortino | Validation: Sharpe
- min_prob_up: 0.80 | max_positions: 15

Output: portfolio allocations with optimized weights (`data/portfolios.parquet`)

### Stage 5: Regime-Aware Backtesting
- Detects market regimes (bull/bear/sideways) using SPY SMA crossover + trailing returns
- Backtests each portfolio across each regime
- Computes all metrics: Sharpe, Sortino, Calmar, Omega, Information ratio, max drawdown
- Generates markdown reports in `data/backtest_reports/`

## Architecture decisions

### Hybrid Docker / Native split

**Docker Compose** (infrastructure, stateful services):
- PostgreSQL with TimescaleDB extension — stores OHLCV, treasury rates, VIX data, sectors, clusters, predictions, portfolios, backtest results. Serves as MLflow backend store
- MLflow Tracking Server (v3.10.1) — experiment tracking, run comparison, model registry. Exposes UI on `localhost:5000`
- Volumes: `./pgdata` for Postgres persistence, `./mlruns` for MLflow artifacts
- All services share a Docker network called `ml-network`

**Native macOS** (compute, leverages MPS):
- Data ingestion scripts: FMP API → PostgreSQL (OHLCV, adj close, treasury 12 tenors, VIX, key metrics, financial ratios, sector performance, GICS sectors)
- Feature engineering with Polars (technical indicators + macro + fundamentals + sector features)
- Feature selection (null filter, variance filter, correlation filter)
- Stock clustering with scikit-learn (KMeans per sector)
- Model training with PyTorch Lightning (`accelerator="mps"`)
- Portfolio optimization with scipy (SLSQP)
- Regime-aware backtesting with comprehensive risk metrics
- Strategy execution: load champion models and generate trading signals

### Why this split
Docker on Apple Silicon runs Linux VMs — PyTorch inside Docker has NO access to MPS. Training natively gives us GPU acceleration. Infrastructure (Postgres, MLflow) runs perfectly in Docker and benefits from containerization (reproducibility, isolation, easy teardown).

### Temporal split design

All date boundaries are computed relative to `date.today()` to support daily retraining. Purge gaps of 21 trading days (~1 month, matching the target horizon) between splits prevent label leakage.

```
train (17yr) | PURGE 21d | val (1yr) | PURGE 21d | test (2yr) | today
```

Configured via relative durations in `configs/default.yaml`, computed by `compute_split_dates()` in `src/config.py`.

## Tech stack

| Layer | Tool | Purpose |
|---|---|---|
| Data source | financialmodelingprep.com API | OHLCV, adj close, treasury (12 tenors), VIX, key metrics, ratios, sector perf, GICS sectors |
| Database | PostgreSQL + TimescaleDB | Time-series storage, hypertables |
| Feature engineering | Polars | Rolling windows, technical indicators, macro features |
| Clustering | scikit-learn | KMeans per sector, silhouette score validation |
| ML framework | PyTorch | LSTM-based binary classifier (UP/NOT_UP) |
| Training wrapper | PyTorch Lightning | Training loop, MPS support, MLflow auto-logging |
| Portfolio optimization | scipy | SLSQP optimizer for multi-objective portfolio design |
| Experiment tracking | MLflow | Tracking, comparison, artifact storage, model registry |
| Dependency management | UV | Fast Python package manager |
| Orchestration | Makefile | Task runner for pipeline steps |
| Containerization | Docker Compose | Postgres + MLflow infrastructure |

## Project structure

```
ai-pipeline/
├── CLAUDE.md
├── README.md
├── Makefile
├── docker-compose.yml
├── pyproject.toml
├── .env                           # API key, DB credentials (never commit)
├── .env.example
├── configs/
│   └── default.yaml               # All hyperparameters and experiment config
├── src/
│   ├── config.py                  # Config loading, SplitDates, ClusterConfig, etc.
│   ├── db.py                      # SQLAlchemy schema (9 tables)
│   ├── keys.py                    # Environment variable loading
│   ├── ingestion/
│   │   └── fmp_loader.py          # FMP API → PostgreSQL (OHLCV, adj close, treasury 12 tenors, VIX, key metrics, ratios, sector perf, sectors)
│   ├── features/
│   │   ├── technical.py           # Polars feature engineering (indicators + macro + fundamentals + sector)
│   │   ├── selection.py           # Feature selection (null/variance/correlation filters)
│   │   └── clustering.py          # Stage 1: KMeans clustering by sector
│   ├── models/
│   │   ├── base_model.py          # LSTMForecaster (binary UP/NOT_UP Lightning module)
│   │   └── dataset.py             # TradingDataModule with per-cluster filtering
│   ├── training/
│   │   └── train.py               # Stage 2: Per-cluster training with MLflow
│   ├── aggregation/
│   │   └── consolidate.py         # Stage 3: Merge per-cluster predictions
│   ├── portfolio/
│   │   ├── metrics.py             # Sharpe, Sortino, Omega, Calmar, Information ratio
│   │   └── optimizer.py           # Stage 4: Multi-profile portfolio optimization
│   ├── evaluation/
│   │   ├── regime.py              # Market regime detection (bull/bear/sideways)
│   │   ├── backtest.py            # Stage 5: Regime-aware portfolio backtesting
│   │   ├── promote.py             # Promote per-cluster models by trading metrics (val_trade_sortino)
│   │   └── champion.py            # Shared champion checkpoint loader from MLflow registry
│   └── strategy/
│       └── runner.py              # Load champion models, generate trading signals
├── data/                          # Feature parquet files, clusters, predictions, portfolios
├── tests/
│   ├── test_features.py
│   ├── test_clustering.py
│   ├── test_aggregation.py
│   ├── test_portfolio_metrics.py
│   ├── test_portfolio_optimizer.py
│   ├── test_promotion.py
│   ├── test_regime.py
│   └── test_backtest.py
└── notebooks/
```

## Database tables

| Table | Purpose |
|---|---|
| `ohlcv_daily` | Daily OHLCV + adj_close price data |
| `treasury_rates` | US Treasury rates (12 tenors: 1M to 30Y) |
| `vix_daily` | VIX volatility index data |
| `key_metrics_quarterly` | Quarterly key metrics per symbol (JSONB) |
| `financial_ratios_quarterly` | Quarterly financial ratios per symbol (JSONB) |
| `sector_performance_daily` | Historical sector performance (avg daily change) |
| `stock_sectors` | GICS sector mapping per symbol |
| `cluster_assignments` | Stage 1 output: stock-to-cluster mapping |
| `predictions` | Stage 3 output: aggregated prob_up predictions per symbol |
| `portfolio_allocations` | Stage 4 output: optimized weights per profile |
| `backtest_results` | Stage 5 output: metrics per (profile, regime) |

## Key connections

- Ingestion writes to Postgres via SQLAlchemy (OHLCV + adj close, treasury 12 tenors, VIX, key metrics, financial ratios, sector performance, GICS sectors)
- Features reads from Postgres, transforms with Polars, outputs `data/features.parquet`. Uses adj_close for all price-derived indicators when available
- Feature selection filters by null rate, variance, and correlation, outputs `data/features_selected.parquet` and `data/selected_features.json` manifest
- Training and aggregation read from `features_selected.parquet` when feature selection is enabled; runner filters to selected features at inference time
- Clustering reads sectors from DB + features, assigns clusters with KMeans, outputs `data/clusters.parquet`
- Training iterates over clusters, creates per-cluster MLflow experiments, trains LSTM models
- Aggregation loads per-cluster models, runs inference, outputs `data/predictions.parquet`
- Portfolio optimizer uses predictions + historical returns to construct 3 risk-profiled portfolios
- Backtesting simulates portfolios across bull/bear/sideways regimes, computes all metrics
- Data is normalized using training-set statistics only (Z-score), applied to val/test/inference
- TimeSeriesDataset uses symbol-boundary-aware indexing — windows never cross from one stock's data into another's

## Makefile targets

```makefile
make setup       # Create venv and install dependencies with UV
make up          # docker compose up -d (Postgres + MLflow)
make down        # docker compose down
make ingest      # FMP API → PostgreSQL (OHLCV, adj close, treasury, VIX, fundamentals, sector perf, sectors)
make features    # Generate feature parquet from DB
make select-features  # Feature selection (null/variance/correlation filters)
make cluster     # Stage 1: Cluster stocks by sector
make train       # Stage 2: Train LSTM per cluster
make train-cluster CLUSTER=Tech_0  # Train single cluster
make aggregate   # Stage 3: Consolidate predictions
make portfolio   # Stage 4: Optimize 3 portfolio profiles
make backtest    # Stage 5: Regime-aware backtesting
make promote     # Register best per-cluster models as champions
make signals     # Generate trading signals
make pipeline    # Run: ingest → features → select-features → cluster → train → promote → aggregate → portfolio → backtest
make test        # Run all tests
```

## Environment variables

```
FMP_API_KEY=           # financialmodelingprep.com API key
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trading
POSTGRES_USER=trading
POSTGRES_PASSWORD=     # Set in .env, never commit
MLFLOW_TRACKING_URI=http://localhost:5000
PIPELINE_ENV=dev       # dev (5yr data) or prod (20yr data), default: dev
```

## Model details

- **Architecture**: LSTM with LayerNorm, GELU activation, 2 layers, 128 hidden units
- **Task**: Binary classification — UP (≥+2.5%) vs NOT_UP in 21 trading days
- **Threshold**: buy_threshold configurable per cluster in `configs/default.yaml` under `clustering.cluster_thresholds`
- **Regularization**: Dropout (0.3), weight decay, gradient clipping (1.0), label smoothing (0.05)
- **Optimizer**: AdamW with ReduceLROnPlateau scheduler
- **Early stopping**: Monitors `val_acc`, patience 20 epochs
- **Loss**: CrossEntropyLoss with label smoothing

## Features

All price-derived indicators (SMAs, EMAs, RSI, MACD, Bollinger, ATR, etc.) use `adj_close` when available, ensuring consistency between indicators and target labels.

- **Technical indicators**: SMA, EMA, RSI, MACD, Bollinger Bands, ATR, Stochastic Oscillator (%K, %D), volume SMA (at windows 5, 10, 20, 50, 200)
- **Returns**: 1-day, 5-day, 20-day returns (from dividend-adjusted close)
- **Volatility**: Multi-window realized volatility (5d, 20d, 60d rolling std of returns), ATR ratio, mean-reversion z-score
- **Volume**: Relative volume, OBV rate-of-change (20d)
- **Macro**: US Treasury rates (12 tenors: 1M to 30Y), 8 yield spreads + curve slope, daily changes per tenor, lagged spreads (5d, 20d)
- **VIX**: Close, SMA(5/20), SMA20 ratio, intraday range, VIX percentile rank (252d rolling min/max), lagged VIX (5d, 20d)
- **Cross-sectional**: Relative strength vs SPY (20d return minus SPY 20d return)
- **Fundamentals**: ~20 key metrics + ~20 financial ratios, quarterly data forward-filled to daily, with true quarter-over-quarter changes (computed on quarterly data before asof join)
- **Sector performance**: Daily sector avg change, 5d/20d sector momentum, relative-to-sector performance
- **Time encoding**: Cyclical sin/cos encoding of day-of-week and month-of-year
- **Clustering features**: Behavioral, fundamental, macro-sensitivity, and sector-relative features with PCA and auto-K selection
- **Feature selection**: Post-engineering filter removing >90% null features, near-zero variance, and highly correlated pairs (>0.95). Output (`features_selected.parquet`) is consumed by training, aggregation, and inference when enabled
- **Null handling**: Fundamentals are forward-filled per symbol, remaining nulls are median-filled per symbol, only rows with null returns/target are dropped

## Portfolio metrics

| Metric | Formula | Use |
|---|---|---|
| Sharpe | excess_return / total_volatility | Moderate primary |
| Sortino | excess_return / downside_volatility | Aggressive primary |
| Calmar | annual_return / max_drawdown | Conservative primary |
| Omega | sum(gains) / sum(losses) | Aggressive complementary |
| Information | excess_vs_benchmark / tracking_error | Aggressive validation |

## Risk management (backtest)

- Per-position stop-loss at -8%, take-profit at +50%
- Portfolio drawdown circuit breaker at -25% with 2-day cooldown
- Sector weight limits per profile (20-30%)
- Max single position weight: 10%
- Commission: 0.1%
- Monthly rebalance (21 trading days)

## Constraints and preferences

- **RAM**: 24GB — prefer Polars over pandas
- **GPU**: Apple MPS via PyTorch Lightning — always set `accelerator="mps"` in Trainer
- **No cloud services**: Everything runs locally
- **CLI-first**: No dashboards beyond MLflow UI
- **Python version**: 3.12+
- **Code style**: Type hints everywhere, docstrings on public functions

## Common commands

```bash
# Start infrastructure
docker compose up -d

# Run full pipeline
make pipeline

# Train a specific cluster
make train-cluster CLUSTER=Technology_0

# Generate trading signals
make signals

# Check MLflow UI
open http://localhost:5000

# Run with UV directly
uv run python -m src.ingestion.fmp_loader
uv run python -m src.features.clustering
uv run python -m src.training.train --cluster Technology_0
uv run python -m src.aggregation.consolidate
uv run python -m src.portfolio.optimizer
uv run python -m src.evaluation.backtest
uv run python -m src.strategy.runner --symbols AAPL NVDA TSLA

# Check Postgres
docker exec -it trading-postgres psql -U trading -d trading

# Run tests
make test
```
