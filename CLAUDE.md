# CLAUDE.md — Trading ML Pipeline

## Project overview

Local ML pipeline for evaluating stock trading strategies on 132 S&P 500 stocks available as CEDEARs in the Argentine market. Runs on a Mac Mini M4 Pro (24GB RAM) using a hybrid architecture: infrastructure in Docker, compute native on macOS to leverage MPS GPU acceleration. Designed for daily retraining with fully relative date splits and purge gaps to prevent label leakage.

## Architecture decisions

### Hybrid Docker / Native split

**Docker Compose** (infrastructure, stateful services):
- PostgreSQL with TimescaleDB extension — stores OHLCV, treasury rates, VIX data and serves as MLflow backend store
- MLflow Tracking Server (v3.10.1) — experiment tracking, run comparison, model registry. Exposes UI on `localhost:5000`
- Volumes: `./pgdata` for Postgres persistence, `./mlruns` for MLflow artifacts
- All services share a Docker network called `ml-network`

**Native macOS** (compute, leverages MPS):
- Data ingestion scripts: FMP API → PostgreSQL (OHLCV, treasury rates, VIX)
- Feature engineering with Polars (technical indicators + macro features)
- Model training with PyTorch Lightning (`accelerator="mps"`)
- Portfolio backtesting with risk management
- Strategy execution: load champion model and generate BUY/HOLD signals

### Why this split
Docker on Apple Silicon runs Linux VMs — PyTorch inside Docker has NO access to MPS. Training natively gives us GPU acceleration. Infrastructure (Postgres, MLflow) runs perfectly in Docker and benefits from containerization (reproducibility, isolation, easy teardown).

### Temporal split design

All date boundaries are computed relative to `date.today()` to support daily retraining. Purge gaps of 63 trading days (~3 months, matching the target horizon) between splits prevent label leakage.

```
train (7yr) | PURGE 63d | val (1yr) | PURGE 63d | test (2yr) | today
```

Configured via relative durations in `configs/default.yaml`, computed by `compute_split_dates()` in `src/config.py`.

## Tech stack

| Layer | Tool | Purpose |
|---|---|---|
| Data source | financialmodelingprep.com API | OHLCV, treasury rates, VIX |
| Database | PostgreSQL + TimescaleDB | Time-series storage, hypertables |
| Feature engineering | Polars | Rolling windows, technical indicators, macro features |
| ML framework | PyTorch | LSTM-based binary classifier (BUY/HOLD) |
| Training wrapper | PyTorch Lightning | Training loop, MPS support, MLflow auto-logging |
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
│   ├── config.py                  # Config loading, compute_split_dates(), SplitDates
│   ├── db.py                      # SQLAlchemy schema (ohlcv_daily, treasury_rates, vix_daily)
│   ├── keys.py                    # Environment variable loading
│   ├── ingestion/
│   │   └── fmp_loader.py          # FMP API → PostgreSQL (OHLCV, treasury, VIX)
│   ├── features/
│   │   └── technical.py           # Polars feature engineering (indicators + macro)
│   ├── models/
│   │   ├── base_model.py          # LSTMForecaster (Lightning module)
│   │   └── dataset.py             # TradingDataModule with temporal splits + purge gaps
│   ├── training/
│   │   └── train.py               # Training with MLflow logging
│   ├── evaluation/
│   │   ├── backtest.py            # Portfolio-level backtesting with risk management
│   │   └── promote.py             # Promote best model to MLflow registry
│   └── strategy/
│       └── runner.py              # Load champion model, generate BUY/HOLD signals
├── data/                          # Feature parquet files (gitignored)
├── tests/
│   ├── test_features.py
│   └── test_backtest.py
└── notebooks/
```

## Key connections

- Ingestion writes to Postgres via SQLAlchemy (OHLCV, treasury rates, VIX)
- Features reads from Postgres, transforms with Polars, outputs `data/features.parquet`
- Training uses PyTorch Lightning with `MLFlowLogger` pointing to `http://localhost:5000`
- Data is normalized using training-set statistics only (Z-score), applied to val/test/inference
- Evaluation runs a portfolio backtest with risk management (stop-loss, take-profit, drawdown circuit breaker)
- Promote finds the best training run (highest `val_acc` with checkpoint) and registers it as `champion` in MLflow
- Strategy loads the champion model and generates per-symbol BUY/HOLD signals

## Makefile targets

```makefile
make setup       # Create venv and install dependencies with UV
make up          # docker compose up -d (Postgres + MLflow)
make down        # docker compose down
make ingest      # FMP API → PostgreSQL (OHLCV + treasury + VIX)
make features    # Generate feature parquet from DB
make train       # Train LSTM with Lightning + MPS, log to MLflow
make evaluate    # Portfolio backtest on test set, log metrics
make promote     # Register best model as champion in MLflow
make signals     # Generate BUY/HOLD signals from champion model
make pipeline    # Run: ingest → features → train → evaluate
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
```

## Model details

- **Architecture**: LSTM with LayerNorm, GELU activation, 2 layers, 128 hidden units
- **Task**: Binary classification — probability of ≥3% gain in 63 trading days (~3 months)
- **Regularization**: Dropout (0.3), weight decay, gradient clipping (1.0), label smoothing (0.05)
- **Optimizer**: AdamW with ReduceLROnPlateau scheduler
- **Early stopping**: Monitors `val_acc`, patience 20 epochs

## Features

- **Technical indicators**: SMA, EMA, RSI, MACD, Bollinger Bands, ATR, volume SMA (at windows 5, 10, 20, 50, 200)
- **Returns**: 1-day, 5-day, 20-day returns
- **Macro**: US Treasury rates (2Y, 10Y, 30Y), yield spreads (10Y-2Y, 30Y-10Y), VIX (close, SMA, percentile, regime)

## Risk management (backtest)

- Max 20 concurrent equal-weight positions
- Per-position stop-loss at -8%, take-profit at +50%
- Portfolio drawdown circuit breaker at -25% with 2-day cooldown
- Commission: 0.1%

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

# Generate trading signals
make signals

# Check MLflow UI
open http://localhost:5000

# Run with UV directly
uv run python -m src.ingestion.fmp_loader
uv run python -m src.training.train
uv run python -m src.strategy.runner --symbols AAPL NVDA TSLA

# Check Postgres
docker exec -it trading-postgres psql -U trading -d trading
```
