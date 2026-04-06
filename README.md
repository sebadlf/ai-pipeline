# Trading ML Pipeline

Local ML pipeline for evaluating stock trading strategies on S&P 500 stocks available as CEDEARs in the Argentine market. Runs on a Mac Mini M4 Pro (24GB RAM) using a hybrid architecture: infrastructure in Docker, compute native on macOS to leverage Apple MPS GPU acceleration.

> **For Developers**: See [AGENTS.md](AGENTS.md) for detailed technical context, architecture decisions, and AI assistant instructions.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Native macOS (MPS GPU)                  │
│                                                             │
│  FMP API ──▶ Ingestion ──▶ Features ──▶ Training ──▶ Eval  │
│               (httpx)      (Polars)    (Lightning)  (numpy) │
│                 │                          │           │    │
│                 ▼                          ▼           ▼    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Docker Compose (ml-network)              │   │
│  │  ┌─────────────────────┐  ┌────────────────────────┐ │   │
│  │  │ PostgreSQL 16       │  │ MLflow Tracking Server │ │   │
│  │  │ + TimescaleDB       │  │ :5000                  │ │   │
│  │  │ OHLCV, treasury,    │  │ Experiments, registry  │ │   │
    │  │  │ VIX, fundamentals,  │  │ Model promotion        │ │   │
    │  │  │ sector performance  │  │                        │ │   │
│  │  └─────────────────────┘  └────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Why hybrid?** Docker on Apple Silicon runs Linux VMs — PyTorch inside Docker has no access to MPS. Training natively gives GPU acceleration. Infrastructure (Postgres, MLflow) benefits from containerization.

## Tech Stack

| Layer | Tool |
|---|---|
| Data source | financialmodelingprep.com API |
| Database | PostgreSQL + TimescaleDB |
| Feature engineering | Polars |
| ML framework | PyTorch + PyTorch Lightning |
| Experiment tracking | MLflow |
| Dependency management | UV |
| Orchestration | Makefile |

## Project Structure

```
├── AGENTS.md                      # AI assistant context — technical reference
├── CLAUDE.md                      # Legacy Cursor/Claude specific context
├── Makefile                       # Task runner
├── docker-compose.yml             # Postgres + MLflow
├── pyproject.toml                 # Dependencies (UV)
├── configs/
│   └── default.yaml               # All hyperparameters and experiment config
├── src/
│   ├── config.py                  # Config loading, SplitDates, compute_split_dates()
│   ├── db.py                      # Database schema and connection
│   ├── keys.py                    # Environment variable loading
│   ├── ingestion/
│   │   └── fmp_loader.py          # FMP API → PostgreSQL (OHLCV, adj close, treasury 12 tenors, VIX, fundamentals, sector perf, sectors)
│   ├── features/
│   │   ├── technical.py           # Technical + macro + fundamental + sector features (Polars)
│   │   └── selection.py           # Feature selection (null/variance/correlation filters)
│   ├── models/
│   │   ├── base_model.py          # LSTMForecaster (Lightning module)
│   │   └── dataset.py             # TradingDataModule with temporal splits + purge gaps
│   ├── training/
│   │   └── train.py               # Training loop with MLflow logging
│   ├── evaluation/
│   │   ├── backtest.py            # Portfolio-level backtesting with risk management
│   │   └── promote.py             # Model registry promotion (champion alias)
│   └── strategy/
│       └── runner.py              # Generate BUY/HOLD signals from champion model
├── tests/
│   ├── test_features.py
│   └── test_backtest.py
├── data/                          # Feature parquet files (gitignored)
└── notebooks/                     # Exploration
```

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [UV](https://docs.astral.sh/uv/) (`brew install uv`)
- Python 3.12+
- An API key from [financialmodelingprep.com](https://financialmodelingprep.com/)

### Setup

```bash
# Clone and enter the project
cd ai-pipeline

# Configure environment
cp .env.example .env
# Edit .env and set your FMP_API_KEY and POSTGRES_PASSWORD

# Install dependencies
uv sync

# Start infrastructure
make up
```

### Run the Full Pipeline

```bash
make pipeline    # ingest → features → select-features → cluster → train → aggregate → portfolio → backtest
```

Or run each step individually:

```bash
make ingest           # Fetch all data from FMP API into PostgreSQL
make features         # Generate features → data/features.parquet
make select-features  # Feature selection → data/features_selected.parquet
make cluster          # Cluster stocks by sector
make train            # Train LSTM per cluster with MPS, log to MLflow
make aggregate        # Consolidate per-cluster predictions
make portfolio        # Optimize 3 portfolio profiles
make backtest         # Regime-aware backtesting
make promote          # Register best models as champions in MLflow
make signals          # Generate BUY/HOLD signals from champion models
```

### Generate Trading Signals

```bash
make signals
# or for specific symbols:
uv run python -m src.strategy.runner --symbols AAPL NVDA TSLA
```

### View Experiments

```bash
open http://localhost:5000    # MLflow UI
```

## Pipeline Details

### Data Ingestion

Fetches data from the FMP API for S&P 500 stocks. The start date is computed dynamically as `today - 20 years`. Seven data sources:

- **OHLCV**: Daily price data per symbol
- **Adjusted Close**: Dividend-adjusted close prices via dedicated FMP endpoint
- **Treasury Rates**: All 12 US tenors (1M, 2M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y)
- **VIX**: Volatility index data
- **Key Metrics**: Quarterly fundamental metrics per symbol (~47 fields, stored as JSONB)
- **Financial Ratios**: Quarterly financial ratios per symbol (~66 fields, stored as JSONB)
- **Sector Performance**: Daily historical average change per GICS sector

Use `--skip-adjclose`, `--skip-treasury`, `--skip-vix`, `--skip-fundamentals`, `--skip-sector-perf`, `--skip-sectors` flags to skip individual sources. Symbols that return HTTP errors are skipped gracefully.

### Feature Engineering

Computes features using Polars and saves to `data/features.parquet`. When `adj_close` is available, all price-derived indicators (SMAs, EMAs, RSI, MACD, Bollinger, ATR) are computed on dividend-adjusted prices for consistency with the target labels.

- **Moving Averages**: SMA and EMA at windows [5, 10, 20, 50, 200], expressed as price-relative ratios
- **Momentum**: RSI(14), MACD(12, 26, 9), Stochastic Oscillator (%K, %D)
- **Volatility**: Bollinger Bands(20), ATR(14), realized volatility at 5d/20d/60d horizons, mean-reversion z-score
- **Volume**: Volume SMA(20), relative volume, OBV rate-of-change (20d)
- **Returns**: 1-day, 5-day, 20-day returns (from dividend-adjusted close)
- **Macro**: All 12 treasury tenors, 8 yield spreads + curve slope, daily changes per tenor, lagged spreads (5d, 20d)
- **VIX**: Close, SMA(5/20), SMA20 ratio, intraday range, daily change/return, percentile rank (252d), lagged VIX (5d, 20d)
- **Cross-Sectional**: Relative strength vs SPY (stock 20d return minus SPY 20d return)
- **Fundamentals**: ~20 key metrics + ~20 financial ratios, quarterly data forward-filled to daily, with true QoQ changes (computed on quarterly data before forward-fill)
- **Sector**: Daily sector avg change, 5d/20d sector momentum, relative-to-sector performance
- **Time Encoding**: Cyclical sin/cos encoding of day-of-week and month-of-year
- **Target**: Ternary label — BUY (≥+5%), SELL (≤-3%), HOLD (neither) in 63 trading days

**Null handling**: Fundamentals are forward-filled per symbol (quarterly gaps are expected), remaining nulls are median-filled per symbol, and only rows with null returns or target are dropped — preserving significantly more data than a naive drop-all approach.

**Feature selection** (`make select-features`): Filters features by null rate (>90%), near-zero variance (bottom 1%), and high correlation (>0.95), saving the result to `data/features_selected.parquet` and a manifest of selected feature names to `data/selected_features.json`. When enabled, training, aggregation, and inference automatically use the selected features.

### Temporal Splits

All split boundaries are relative to today for daily retraining. A 63-day purge gap between each split prevents label leakage (matches the 63-day target horizon):

```
train (17yr) │ PURGE (63d) │ val (1yr) │ PURGE (63d) │ test (2yr) │ today
```

Data in purge gaps is discarded. Features are Z-score normalized using training-set statistics only. The sliding-window dataset uses symbol-boundary-aware indexing to ensure no sequence ever mixes data from different stocks.

### Model

LSTM-based ternary classifier built with PyTorch Lightning:

- **Architecture**: 2-layer LSTM (128 hidden), LayerNorm, GELU, dropout (0.3)
- **Task**: Classify BUY (≥+5%), SELL (≤-3%), or HOLD in 63 trading days (~3 months)
- **Regularization**: Weight decay (0.01), gradient clipping (1.0), label smoothing (0.05)
- **Optimizer**: AdamW with ReduceLROnPlateau scheduler
- **Early stopping**: Monitor `val_acc`, patience 20 epochs
- **Hardware**: Apple MPS GPU acceleration

### Backtesting

Portfolio-level simulation on the 2-year test period with risk management:

- **Position sizing**: Equal-weight across up to 20 concurrent positions
- **Entry**: BUY signal when model probability ≥ 60% confidence threshold
- **Stop-loss**: Exit at -8% from entry
- **Take-profit**: Exit at +50% from entry
- **Circuit breaker**: Stop trading if portfolio drawdown hits -25%, resume after 2-day cooldown
- **Commission**: 0.1% per trade

Metrics logged to MLflow: total return, annual return, Sharpe ratio, max drawdown, win rate, number of trades.

### Model Promotion

The `promote` step finds the best training run (highest `val_acc` with a checkpoint artifact) and registers it as `champion` in the MLflow Model Registry. The `signals` step always loads the most recent champion model.

### Configuration

All parameters are in `configs/default.yaml`:

```yaml
ingestion:
  source: sp500                       # dynamic from FMP API
  start_years_back: 20                # 20 years of data

model:
  type: lstm
  hidden_size: 128
  num_layers: 2
  dropout: 0.3
  sequence_length: 30

features:
  fundamentals: true       # key metrics + financial ratios
  sector_performance: true # sector daily performance

feature_selection:
  enabled: true
  max_null_pct: 0.90
  max_correlation: 0.95
  min_variance_pct: 0.01

training:
  batch_size: 64
  max_epochs: 200
  learning_rate: 0.001
  test_years: 2           # relative to today
  val_years: 1
  purge_days: 63           # gap between splits

backtest:
  risk:
    position_stop_loss: 0.08
    position_take_profit: 0.50
    max_drawdown_limit: 0.25
```

## Environment Variables

| Variable | Description |
|---|---|
| `FMP_API_KEY` | financialmodelingprep.com API key |
| `POSTGRES_HOST` | Database host (default: `localhost`) |
| `POSTGRES_PORT` | Database port (default: `5432`) |
| `POSTGRES_DB` | Database name (default: `trading`) |
| `POSTGRES_USER` | Database user (default: `trading`) |
| `POSTGRES_PASSWORD` | Database password |
| `MLFLOW_TRACKING_URI` | MLflow server URL (default: `http://localhost:5000`) |

## Useful Commands

```bash
# Infrastructure
make up                  # Start Postgres + MLflow
make down                # Stop all containers

# Full pipeline
make pipeline            # ingest → features → select-features → cluster → train → aggregate → portfolio → backtest

# Individual steps
make ingest              # Fetch all data from FMP API
make features            # Generate features parquet
make select-features     # Feature selection
make cluster             # Cluster stocks by sector
make train               # Train per-cluster models
make aggregate           # Consolidate predictions
make portfolio           # Optimize portfolios
make backtest            # Regime-aware backtesting
make promote             # Register best models
make signals             # Generate trading signals

# Database access
docker exec -it trading-postgres psql -U trading -d trading

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/ tests/
```
