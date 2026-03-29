# Trading ML Pipeline

Local ML pipeline for evaluating stock trading strategies on S&P 500 stocks available as CEDEARs in the Argentine market. Runs on a Mac Mini M4 Pro (24GB RAM) using a hybrid architecture: infrastructure in Docker, compute native on macOS to leverage Apple MPS GPU acceleration.

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
│  │  │ VIX data            │  │ Model promotion        │ │   │
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
├── CLAUDE.md                      # AI assistant instructions
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
│   │   └── fmp_loader.py          # FMP API → PostgreSQL (OHLCV, treasury, VIX)
│   ├── features/
│   │   └── technical.py           # Technical indicators + macro features (Polars)
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
make pipeline    # ingest → features → train → evaluate
```

Or run each step individually:

```bash
make ingest      # Fetch OHLCV, treasury rates, VIX from FMP API into PostgreSQL
make features    # Generate technical indicators + macro features → data/features.parquet
make train       # Train LSTM model with MPS acceleration, log to MLflow
make evaluate    # Portfolio backtest on test set, log metrics to MLflow
make promote     # Register best training model as champion in MLflow
make signals     # Generate BUY/HOLD signals from champion model
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

Fetches data from the FMP API for 132 S&P 500 stocks available as CEDEARs in BYMA. The start date is computed dynamically as `today - 10 years`. Three data sources:

- **OHLCV**: Daily price data per symbol
- **Treasury Rates**: US 2Y, 10Y, 30Y yields
- **VIX**: Volatility index data

Symbols that return HTTP errors (e.g., 402 Payment Required) are skipped gracefully.

### Feature Engineering

Computes features using Polars and saves to `data/features.parquet`:

- **Moving Averages**: SMA and EMA at windows [5, 10, 20, 50, 200]
- **Momentum**: RSI(14), MACD(12, 26, 9)
- **Volatility**: Bollinger Bands(20), ATR(14)
- **Volume**: Volume SMA(20), relative volume
- **Returns**: 1-day, 5-day, 20-day returns
- **Macro**: Treasury yields (2Y, 10Y, 30Y), yield spreads (10Y-2Y, 30Y-10Y)
- **VIX**: Close, SMA(20), percentile rank(252d), regime (low/mid/high/extreme)
- **Target**: Binary label — 1 if 63-day forward return ≥ 3%, else 0

### Temporal Splits

All split boundaries are relative to today for daily retraining. A 63-day purge gap between each split prevents label leakage (matches the 63-day target horizon):

```
train (7yr) │ PURGE (63d) │ val (1yr) │ PURGE (63d) │ test (2yr) │ today
```

Data in purge gaps is discarded. Features are Z-score normalized using training-set statistics only.

### Model

LSTM-based binary classifier built with PyTorch Lightning:

- **Architecture**: 2-layer LSTM (128 hidden), LayerNorm, GELU, dropout (0.3)
- **Task**: Predict probability of ≥3% gain in 63 trading days (~3 months)
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
  symbols: [AAPL, MSFT, GOOGL, ...]  # 132 S&P 500 CEDEAR symbols
  start_years_back: 10                # dynamically computed

model:
  type: lstm
  hidden_size: 128
  num_layers: 2
  dropout: 0.3
  sequence_length: 30

training:
  batch_size: 64
  max_epochs: 200
  learning_rate: 0.001
  test_years: 2         # relative to today
  val_years: 1
  purge_days: 63         # gap between splits

evaluation:
  confidence_threshold: 0.6
  max_positions: 20
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
make pipeline            # ingest → features → train → evaluate

# Individual steps
make ingest              # Fetch data from FMP API
make features            # Generate features parquet
make train               # Train model
make evaluate            # Backtest
make promote             # Register best model
make signals             # Generate trading signals

# Database access
docker exec -it trading-postgres psql -U trading -d trading

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/ tests/
```
