# CLAUDE.md — Trading ML Pipeline

## Project overview

Local ML pipeline for evaluating stock trading strategies on the full S&P 500 universe (~503 stocks, fetched dynamically from the FMP API). Runs on a Mac Mini M4 Pro (24GB RAM) using a hybrid architecture: infrastructure in Docker, compute native on macOS to leverage MPS GPU acceleration. The pipeline uses a 7-stage architecture: data ingestion/features, stock clustering, model training with Optuna optimization, model promotion, prediction aggregation, portfolio optimization, and regime-aware backtesting.

## Architecture — 7-Stage Pipeline

### Stage 0: Data Ingestion & Feature Engineering
- **Ingestion** (`fmp_loader.py`): FMP API -> PostgreSQL (OHLCV, adj close, treasury 12 tenors, VIX, key metrics, financial ratios, sector performance, GICS sectors)
- **Feature Engineering** (`technical.py`): Polars-based computation of technical indicators + macro + fundamentals + sector features -> `data/features.parquet`
- **Feature Selection** (`selection.py`): Filters by null rate (>90%), variance (bottom 1%), correlation (>0.95), and mutual information -> `data/features_selected.parquet` + `data/selected_features.json` manifest
- **Normalization** (`normalize.py`): Computes training-set statistics (mean, std, p01, p99), clips outliers to [p01, p99], applies Z-score normalization -> `data/features_normalized.parquet` + `data/normalization_stats.json`

### Stage 1: Stock Clustering
- Global KMeans clustering (prod) or sector-based clustering (dev) using behavioral, fundamental, and macro-sensitivity features
- PCA for dimensionality reduction (95% variance retained), auto-K selection via silhouette analysis
- Merges small clusters (< min_cluster_size) to nearest centroid
- Output: `data/clusters.parquet`, `cluster_assignments` table

### Stage 2: Model Training
- **Per-cluster Optuna optimization** (`optimize.py`): Each cluster gets its own Optuna study with 3-fold time-series CV, ~12 tunable params, overfitting gap penalty, and convergence-based early stopping
- **Ensemble training** (`train.py`): Top-3 deduplicated Optuna configs per cluster are trained as full models for ensemble inference
- **Champion selection**: Best ensemble member is tagged as "champion" using a generalization-adjusted score that penalizes val→test precision gap
- Each cluster gets its own MLflow experiment (`cluster/{cluster_id}`) with 3 runs (one per ensemble member)
- Model output is `prob_up` -- the probability of UP, weighted-averaged across ensemble by val_precision_up. This is the sole signal used downstream

### Stage 3: Model Promotion
- **Cascading elimination** (`promote.py` + `precision_eval.py`): Precision-focused evaluation with walk-forward stability, minimum recall filters, and FP severity tiebreaking
- **Legacy fallback**: Simple metric comparison when `promotion.evaluation` section is absent
- Registers best model per cluster as "champion" alias in MLflow Model Registry

### Stage 4: Prediction Aggregation
- Loads ensemble model checkpoints (top-3) per cluster from MLflow registry
- Validates feature consistency between models and current data
- Runs inference with each ensemble member, computes **weighted average** of `prob_up` per symbol (weights proportional to each model's `val_precision_up`)
- Detects normalization drift: warns if feature distributions deviate >3 std from training-period statistics
- Output: `data/predictions.parquet`, `predictions` table

### Stage 5: Portfolio Optimization

Stocks with `prob_up >= min_prob_up` (per profile) are candidates for portfolio inclusion.

**Aggressive Portfolio** (maximize return):
- Primary: Sortino | Complementary: Omega | Validation: Information ratio
- min_prob_up: 0.60 | max_positions: 25 | max_sector_weight: 30%

**Moderate Portfolio** (risk/return balance):
- Primary: Sharpe | Complementary: Calmar | Validation: Sortino
- min_prob_up: 0.65 | max_positions: 20 | max_sector_weight: 25%

**Conservative Portfolio** (capital preservation):
- Primary: Calmar | Complementary: Sortino | Validation: Sharpe
- min_prob_up: 0.70 | max_positions: 15 | max_sector_weight: 20%

Output: portfolio allocations with optimized weights (`data/portfolios.parquet`)

### Stage 6: Regime-Aware Backtesting
- Detects market regimes (bull/bear/sideways) using SPY SMA crossover + trailing annualized returns
- Backtests each portfolio across each regime with risk management (stop-loss, take-profit, circuit breaker)
- Computes all metrics: Sharpe, Sortino, Calmar, Omega, Information ratio, max drawdown
- Generates markdown reports in `data/backtest_reports/`

### Stage 7: Signal Generation
- Loads champion models per cluster from MLflow registry
- Generates prob_up predictions for specified symbols (or all)
- Outputs actionable stocks above threshold with BUY/HOLD signals

## Architecture decisions

### Hybrid Docker / Native split

**Docker Compose** (infrastructure, stateful services):
- PostgreSQL with TimescaleDB extension -- stores OHLCV, treasury rates, VIX data, sectors, clusters, predictions, portfolios, backtest results. Also serves as MLflow backend store and Optuna study storage
- MLflow Tracking Server (v3.10.1) -- experiment tracking, run comparison, model registry. Exposes UI on `localhost:5000`
- Volumes: `./pgdata` for Postgres persistence, `mlflow-artifacts` for MLflow artifacts
- All services share a Docker network called `ml-network`

**Native macOS** (compute, leverages MPS):
- Data ingestion scripts: FMP API -> PostgreSQL
- Feature engineering with Polars
- Feature selection (null filter, variance filter, correlation filter, mutual information)
- Feature normalization (percentile clipping + Z-score with persistent training-set statistics)
- Stock clustering with scikit-learn (KMeans with PCA)
- Optuna hyperparameter optimization (persisted to PostgreSQL)
- Model training with PyTorch Lightning (`accelerator="mps"`)
- Portfolio optimization with scipy (SLSQP)
- Regime-aware backtesting with comprehensive risk metrics
- Strategy execution: load champion models and generate trading signals

### Why this split
Docker on Apple Silicon runs Linux VMs -- PyTorch inside Docker has NO access to MPS. Training natively gives us GPU acceleration. Infrastructure (Postgres, MLflow) runs perfectly in Docker and benefits from containerization.

### Temporal split design

All date boundaries are computed relative to `date.today()` to support daily retraining. Purge gaps of 21 trading days (~1 month, matching the target horizon) between splits prevent label leakage.

```
train | PURGE 21d | val (1yr) | PURGE 21d | test (1yr) | today
```

Start date is `start_years_back` before today (dev: 8yr, prod: 20yr). Configured via relative durations in `configs/default.yaml`, computed by `compute_split_dates()` in `src/config.py`.

## Tech stack

| Layer | Tool | Purpose |
|---|---|---|
| Data source | financialmodelingprep.com API | OHLCV, adj close, treasury (12 tenors), VIX, key metrics, ratios, sector perf, GICS sectors |
| Database | PostgreSQL + TimescaleDB | Time-series storage, hypertables, Optuna study storage |
| Feature engineering | Polars | Rolling windows, technical indicators, macro features |
| Clustering | scikit-learn | KMeans per sector, PCA, silhouette score validation |
| ML framework | PyTorch | LSTM-based binary classifier (UP/NOT_UP) |
| Training wrapper | PyTorch Lightning | Training loop, MPS support, MLflow auto-logging |
| Hyperparameter optimization | Optuna | F-beta objective, study persistence, warm-starting |
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
│   ├── config.py                  # Config loading, validation, SplitDates, ClusterConfig, etc.
│   ├── db.py                      # SQLAlchemy schema (11 tables), in_params helper
│   ├── keys.py                    # Environment variable loading
│   ├── ingestion/
│   │   └── fmp_loader.py          # FMP API -> PostgreSQL (OHLCV, adj close, treasury, VIX, fundamentals, sector perf, sectors)
│   ├── features/
│   │   ├── technical.py           # Polars feature engineering (indicators + macro + fundamentals + sector)
│   │   ├── selection.py           # Feature selection (null/variance/correlation/MI filters)
│   │   ├── normalize.py           # Percentile clipping + Z-score normalization with persistent stats
│   │   └── clustering.py          # Stage 1: KMeans clustering with PCA + auto-K
│   ├── models/
│   │   ├── base_model.py          # LSTMForecaster (binary UP/NOT_UP Lightning module) with FocalLoss
│   │   └── dataset.py             # TradingDataModule with per-cluster filtering and temporal splits
│   ├── training/
│   │   ├── optimize.py            # Optuna hyperparameter optimization (global + per-cluster)
│   │   └── train.py               # Stage 2: Per-cluster training with MLflow logging
│   ├── aggregation/
│   │   └── consolidate.py         # Stage 4: Merge per-cluster predictions with feature validation
│   ├── portfolio/
│   │   ├── metrics.py             # Sharpe, Sortino, Omega, Calmar, Information ratio
│   │   └── optimizer.py           # Stage 5: Multi-profile portfolio optimization
│   ├── evaluation/
│   │   ├── precision_eval.py      # Precision-at-threshold walk-forward evaluation
│   │   ├── promote.py             # Stage 3: Cascading model promotion to MLflow registry
│   │   ├── regime.py              # Market regime detection (bull/bear/sideways)
│   │   ├── backtest.py            # Stage 6: Regime-aware portfolio backtesting
│   │   ├── champion.py            # Champion checkpoint loader from MLflow registry
│   │   └── clean_runs.py          # MLflow run cleanup utility
│   └── strategy/
│       └── runner.py              # Stage 7: Load champion models, generate trading signals
├── scripts/
│   ├── mlflow_report.py           # MLflow experiment summary report
│   ├── mlflow_runs_report.py      # Detailed per-run MLflow report
│   ├── fmp_discover.py            # FMP API endpoint discovery
│   └── sync_fmp_docs.py           # FMP API documentation sync
├── data/                          # Feature parquet files, clusters, predictions, portfolios
├── tests/
│   ├── test_features.py
│   ├── test_clustering.py
│   ├── test_aggregation.py
│   ├── test_portfolio_metrics.py
│   ├── test_portfolio_optimizer.py
│   ├── test_precision_eval.py
│   ├── test_promotion.py
│   ├── test_regime.py
│   └── test_backtest.py
└── notebooks/
```

## Database tables

| Table | Purpose |
|---|---|
| `ohlcv_daily` | Daily OHLCV + adj_close price data |
| `treasury_rates` | US Treasury rates (12 tenors: 1M, 2M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y) |
| `vix_daily` | VIX volatility index data |
| `key_metrics_quarterly` | Quarterly key metrics per symbol (JSONB) |
| `financial_ratios_quarterly` | Quarterly financial ratios per symbol (JSONB) |
| `sector_performance_daily` | Historical sector performance (avg daily change) |
| `stock_sectors` | GICS sector mapping per symbol |
| `cluster_assignments` | Stage 1 output: stock-to-cluster mapping |
| `predictions` | Stage 4 output: aggregated prob_up predictions per symbol |
| `portfolio_allocations` | Stage 5 output: optimized weights per profile |
| `backtest_results` | Stage 6 output: metrics per (profile, regime) |

## Key connections

- Ingestion writes to Postgres via SQLAlchemy (OHLCV + adj close, treasury 12 tenors, VIX, key metrics, financial ratios, sector performance, GICS sectors)
- Features reads from Postgres, transforms with Polars, outputs `data/features.parquet`. Uses adj_close for all price-derived indicators when available
- Feature selection filters by null rate, variance, correlation, and mutual information; outputs `data/features_selected.parquet` and `data/selected_features.json` manifest
- Normalization reads `features_selected.parquet`, computes training-set stats, clips outliers, applies Z-score, outputs `data/features_normalized.parquet` + `data/normalization_stats.json`
- Training and aggregation read from `features_normalized.parquet`; runner uses `normalization_stats.json` for inference-time normalization
- Clustering reads sectors from DB + features, assigns clusters with KMeans + PCA, outputs `data/clusters.parquet`
- Optuna optimizes hyperparameters per-cluster (persisted to PostgreSQL), with overfitting gap penalty and warm-starting from previous studies
- Aggregation loads champion models from MLflow registry, validates feature compatibility, runs weighted-average ensemble inference (weights by val_precision_up), detects normalization drift
- Portfolio optimizer uses predictions + historical returns to construct 3 risk-profiled portfolios
- Backtesting simulates portfolios across bull/bear/sideways regimes with risk management
- Data is normalized in a dedicated step (`normalize.py`): outlier clipping to [p01, p99] + Z-score with training-set statistics. Stats saved to `data/normalization_stats.json`, normalized data to `data/features_normalized.parquet`. Used by training, aggregation, and inference
- TimeSeriesDataset uses symbol-boundary-aware indexing -- windows never cross from one stock's data into another's

## Makefile targets

```makefile
make setup              # Create venv and install dependencies with UV
make up                 # docker compose up -d (Postgres + MLflow)
make down               # docker compose down

# Stage 0: Ingestion & Features
make ingest             # Shows message to use ingest-force (dev safety)
make ingest-force       # FMP API -> PostgreSQL
make features           # Generate feature parquet from DB
make select-features    # Feature selection (null/variance/correlation/MI filters)
make normalize          # Percentile clipping + Z-score normalization

# Stage 1: Clustering
make cluster            # KMeans clustering of stocks

# Stage 2: Training
make train-clusters     # Per-cluster Optuna optimization + ensemble training
make train-global       # Alias for train-clusters

# Stage 3: Promotion
make promote            # Register best per-cluster models as champions

# Stage 4: Aggregation
make aggregate          # Consolidate per-cluster predictions

# Stage 5: Portfolio
make portfolio          # Optimize 3 portfolio profiles

# Stage 6: Backtesting
make backtest           # Regime-aware backtesting

# Stage 7: Signals
make signals            # Generate trading signals from champion models

# Full Pipeline
make pipeline           # Dev pipeline (skips ingestion, conditional features/clusters)
make pipeline-prod      # Prod pipeline (includes ingest-force)
make pipeline-loop      # Infinite loop of dev pipelines (Ctrl+C to stop)

# Utilities
make cleanup            # Clean MLflow runs and restart server
make test               # Run all tests
make mlflow-report      # Generate MLflow experiment summary
make mlflow-report-prod # MLflow report using remote server (192.168.68.64:5000)
make mlflow-runs-report # Detailed per-run MLflow report
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
OPTUNA_STORAGE_URL=    # Defaults to same PostgreSQL as pipeline
PIPELINE_ENV=dev       # dev or prod (see Dev/Prod differences below)
```

### Dev/Prod differences (`PIPELINE_ENV`)

| Setting | Dev | Prod |
|---|---|---|
| `ingestion.start_years_back` | 8 years | 20 years |
| `training.batch_size` | 256 | 128 |
| `training.max_epochs` | 10 | 50 |
| `training.early_stopping_patience` | 3 | 10 |
| `training.optuna.epochs_per_trial` | 5 | 30 |
| `training.optuna.convergence_patience` | 3 | 5 |
| `training.optuna.max_history_days` | 7 days | 60 days |
| Clustering mode | Sector-based (fast) | Global KMeans |
| Pipeline default | Skips ingestion | Includes ingestion |

## Model details

- **Architecture**: LSTM with input dropout, configurable activation (GELU/SiLU/Mish), last-timestep residual connection, optional MultiheadAttention, optional bidirectional. MLP classification head with tunable `head_hidden_ratio`
- **Task**: Binary classification -- UP (>=+2.5%) vs NOT_UP in 21 trading days
- **Loss**: FocalLoss (gamma tunable 0-3) with label smoothing, handles class imbalance. Falls back to CrossEntropy with class weights when focal_gamma=0
- **Threshold**: buy_threshold configurable per cluster in `configs/default.yaml` under `clustering.cluster_thresholds`
- **Optimizer**: AdamW with ReduceLROnPlateau scheduler monitoring `val_precision_up` (mode="max")
- **Early stopping**: Dual early stopping — primary on `val_precision_up` (patience dev:3/prod:10), secondary circuit breaker on `val_loss` (patience+10, prevents diverging val_loss)
- **Data augmentation**: Gaussian noise injection (tunable 0.01-0.08 std) + feature masking (10% random feature dropout per sample) during training only
- **Feature names**: Stored in checkpoint hparams for reproducible inference
- **Precision**: Configurable via `training.precision` — `"32"` (default) or `"16-mixed"` (MPS mixed precision, reduces memory ~40%)
- **Residual connection**: Projects input features at the last timestep only (not all timesteps) to avoid LSTM bypass

**Note on model/training defaults in YAML**: The values in `model` and `training` sections (hidden_size, dropout, etc.) are **fallback defaults only**. In the standard pipeline flow (`make train-clusters`), Optuna optimizes ~12 tunable hyperparameters per cluster — the YAML defaults are never used. Fixed params (optimizer, activation, etc.) are read from `training.optuna.fixed_params`.

## Optuna optimization

- **Per-cluster mode**: Each cluster gets its own Optuna study (`cluster-v2/{cluster_id}`)
- **Objective**: Mean precision-at-threshold (0.50) across 3 time-series CV folds, with overfitting gap penalty
- **Overfitting penalty**: If avg train_acc - val_acc > `max_overfit_gap` (0.30), the objective score is scaled down by `max_gap / actual_gap`. This prevents Optuna from selecting configs that memorize the training set
- **Recall floor**: Minimum recall of 0.15 before applying quadratic penalty to objective
- **Trials**: 5 (dev) / 15 (prod) per cluster, with convergence-based early stopping
- **Convergence detection**: Study stops if no improvement in 3 (dev) / 5 (prod) consecutive completed trials
- **CV folds**: 3 expanding-window folds with purge gaps to prevent data leakage
- **Ensemble**: Top-3 deduplicated trial configs (10 key params checked for near-duplicates) are trained as full models for ensemble inference
- **Champion selection**: Best ensemble member tagged as "champion" using generalization-adjusted score: `base_score * (1 + test_prec/val_prec) / 2`. Prefers models where test precision is close to validation precision
- **Pruning**: Startup period without pruning, then MedianPruner on last fold
- **Persistence**: Studies stored in PostgreSQL for warm-starting; old trials filtered by `max_history_days` (dev:7d, prod:60d)
- **Overtuning mitigations**: Reduced search space (~12 params), time-series CV, convergence stop, ensemble top-3, holdout test, noise augmentation, feature masking, overfitting gap penalty, capacity limits (max 128 hidden, max 3 layers)
- **Tunable search space** (~12 params, configurable in `training.optuna.search_space`):

| Parameter | Type | Range/Values |
|---|---|---|
| learning_rate | float (log) | 1e-4 to 1e-2 |
| batch_size | categorical | [64, 128, 256] |
| weight_decay | float (log) | 1e-3 to 0.2 |
| label_smoothing | float | 0.02-0.12 |
| focal_gamma | float | 0.0-3.0 |
| noise_std | float | 0.01-0.08 |
| hidden_size | categorical | [64, 96, 128] |
| num_layers | int | 1-3 |
| dropout | float | 0.2-0.65 |
| sequence_length | categorical | [10, 20, 30] |
| input_dropout | float | 0.05-0.4 |
| head_hidden_ratio | float | 0.25-0.5 |

- **Fixed params** (not searched, in `training.optuna.fixed_params`): optimizer_name=adamw, scheduler_factor=0.5, scheduler_patience=5, gradient_clip_val=2.0, bidirectional=false, num_attention_heads=0, activation=gelu, feature_mask_rate=0.10

## Temperature calibration

- **Post-training calibration**: Temperature scaling (Guo et al. 2017) with composite NLL + signal-preservation objective
- **Temperature bounds**: [0.5, 4.0] — prevents pathological T>>1 that collapses all probabilities to ~0.50
- **Signal preservation**: Penalizes calibrations where <3% of predictions exceed primary_threshold (0.65)
- **Safety check**: Falls back to T=1.0 if post-calibration yields <1% signals above 0.60
- **Diagnostics**: Pre/post calibration probability distribution stats logged to MLflow

## Model promotion (cascading elimination)

- **Precision-at-threshold evaluation**: Tests model at thresholds [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
- **Primary threshold**: 0.65 (used for stability score and recall filters), with adaptive fallback
- **Adaptive threshold**: When no predictions exceed primary_threshold, searches downward to find highest usable threshold (min 0.50) with >=5% signal rate and >=50% precision
- **Walk-forward stability**: window=63 days (3x horizon), step=21 days (=horizon)
- **Stability score**: `mean_precision - 1.0 * std_precision` (penalizes inconsistent precision), with generalization penalty for val-test gap >20%
- **Filters**: max std ratio 0.25, min recall 0.10, min 3 UP signals per window, max val-test gap 0.20
- **Tiebreaking**: Within 0.01 margin, breaks ties by FP severity (false positive analysis)
- **Graduated fallback**: Tier 1 (passed all filters) -> Tier 2 (failed signals/coverage only) -> Tier 3 (failed one filter) -> Tier 4 (most recent with checkpoint)
- **Legacy fallback**: When `promotion.evaluation` section is absent, uses simple metric comparison

## Features

All price-derived indicators use `adj_close` when available, ensuring consistency between indicators and target labels.

- **Technical indicators**: SMA, EMA, RSI, MACD, Bollinger Bands, ATR, Stochastic Oscillator (%K, %D), volume SMA (at windows 5, 10, 20, 50, 200)
- **Returns**: 1-day, 5-day, 20-day returns (from dividend-adjusted close)
- **Volatility**: Multi-window realized volatility (5d, 20d, 60d rolling std of returns), ATR ratio, mean-reversion z-score
- **Volume**: Relative volume, OBV rate-of-change (20d)
- **Macro**: US Treasury rates (12 tenors: 1M to 30Y), 8 yield spreads + curve slope, daily changes per tenor, lagged spreads (5d, 20d)
- **VIX**: Close, SMA(5/20), SMA20 ratio, intraday range, VIX percentile rank (252d rolling min/max), lagged VIX (5d, 20d)
- **Cross-sectional**: Relative strength vs SPY (20d return minus SPY 20d return)
- **Fundamentals**: ~20 key metrics + ~20 financial ratios, quarterly data forward-filled to daily, with true quarter-over-quarter changes
- **Sector performance**: Daily sector avg change, 5d/20d sector momentum, relative-to-sector performance
- **Time encoding**: Cyclical sin/cos encoding of day-of-week and month-of-year
- **Clustering features**: 7 behavioral + 2 macro-sensitivity + 1 sector-relative + 4 key metrics + 6 financial ratios = 20 features with PCA and auto-K selection
- **Feature selection**: Post-engineering filter removing >90% null features, bottom 1% variance, highly correlated pairs (>0.95), and low mutual information (<0.01). Output consumed by normalization step
- **Normalization**: Dedicated pre-training step computes training-set statistics (mean, std, p01, p99 percentiles), clips outliers to [p01, p99], applies Z-score. Stats persisted in `data/normalization_stats.json` for consistent training/inference normalization. Replaces inline Z-score in dataset.py and LayerNorm in model
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
- Periodic rebalancing every 21 trading days: closes all positions and re-opens at target weights using current equity
- Sector weight limits per profile (20-30%)
- Max single position weight: 10%, min: 1%
- Commission: 0.1%, slippage: 5 basis points
- Initial capital: $100,000

## Constraints and preferences

- **RAM**: 24GB -- prefer Polars over pandas
- **GPU**: Apple MPS via PyTorch Lightning -- always set `accelerator="mps"` in Trainer
- **DataLoader workers**: 0 on macOS to avoid MPS/multiprocessing conflicts
- **Parallel training**: Clusters train in parallel via `multiprocessing` with `spawn` context (required for MPS safety). Configurable via `training.max_workers` (default: 4 in dev/prod). Each worker gets its own MPS context and DB connection. ~2-3GB RAM per worker; 4 workers fit in 24GB with headroom
- **DB in subprocesses**: SQLAlchemy engine singleton is safe with `spawn` (clean process). Workers call `dispose_engine()` on exit to release connections
- **No cloud services**: Everything runs locally
- **CLI-first**: No dashboards beyond MLflow UI
- **Python version**: 3.12+
- **Code style**: Type hints everywhere, docstrings on public functions
- **SQL queries**: Use parameterized queries via SQLAlchemy `text()` with `:param` bindings. Use `in_params()` from `src/db.py` for IN clause lists

## Common commands

```bash
# Start infrastructure
docker compose up -d

# Run full pipeline (dev -- skips ingestion)
make pipeline

# Run full pipeline (prod -- includes ingestion)
make pipeline-prod

# Run pipeline continuously
make pipeline-loop

# Individual stages
make train-clusters        # Per-cluster Optuna + ensemble training
make train-global          # Alias for train-clusters

# Generate trading signals
make signals

# Check MLflow UI
open http://localhost:5000

# Run with UV directly
uv run python -m src.ingestion.fmp_loader
uv run python -m src.features.technical
uv run python -m src.features.selection
uv run python -m src.features.normalize
uv run python -m src.features.clustering
uv run python -m src.training.train
uv run python -m src.training.train --cluster Technology_0
uv run python -m src.evaluation.promote
uv run python -m src.aggregation.consolidate
uv run python -m src.portfolio.optimizer
uv run python -m src.evaluation.backtest
uv run python -m src.strategy.runner
uv run python -m src.strategy.runner --symbols AAPL NVDA TSLA

# Check Postgres
docker exec -it trading-postgres psql -U trading -d trading

# Run tests
make test

# Clean MLflow runs
make cleanup

# MLflow reports
make mlflow-report
make mlflow-runs-report
```

## Autonomous improvement loop

Slash commands under `.claude/commands/pipeline-*.md` implement an autonomous loop that runs the pipeline, analyzes results across all 7 stages, proposes improvements as Linear issues (label `pipeline-auto`), implements them serially (one PR per issue with active CI/merge recovery), and exits when the analysis phase declares `plateau`/`unclear`, the 20-cycle budget is exhausted, or 3 consecutive PR abandons trip the circuit breaker. On clean exit the coordinator hands off to `make pipeline-loop`.

- **Entry point**: `/pipeline-loop` — coordinator. Detects state, delegates each phase to an isolated subagent, reschedules itself via `ScheduleWakeup` until an exit condition fires.
- **Phase commands**: `/pipeline-run`, `/pipeline-analyze`, `/pipeline-propose`, `/pipeline-implement`, `/pipeline-cleanup` — each runnable standalone for manual use or by the coordinator.
- **Deterministic helpers**: `src/pipeline_loop/` — `state` (JSON state + verdict + loop log), `mlflow_helpers` (run count / days since cleanup), `merge` (PR polling + terminal classification). Invocable via `uv run python -m src.pipeline_loop.<module>`.
- **Artifacts**: `ai-pipeline-vault/projects/ai-pipeline/pipeline-loop/` holds `state.json`, `verdict.json`, `loop-log.md`, and `reports/YYYY-MM-DD-cycle-N.md`.
- **Stop flag**: create `data/.loop-stop` to force-exit at the next iteration; the Linear label `loop-stop` on any open issue does the same.

## External References

- **Linear team**: `Becerra` (prefix `BEC`). Use the Linear MCP (`mcp__linear__*`) to read/create/update issues. Issues de este repo van con label o sub-project `ai-pipeline`.
- **Obsidian vault**: `./ai-pipeline-vault/` — accessible via the `obsidian` MCP server. Contains:
  - `projects/ai-pipeline/` — project-specific notes (domain, ADRs, runbooks)
  - `knowledge/` — cross-project knowledge (Python, ML, architecture, DevOps, tools)
  - `workflows/` — documented workflows
  - `daily-logs/` — per-day informal log
- **GitHub**: repo `sebadlf/ai-pipeline`. Use the `github` MCP for PRs, issues, reviews.
- **MLflow**: local tracking server en `http://localhost:5000` (y `http://192.168.68.64:5000` para reports remotos). Source of truth experimental — no duplicar métricas de runs en el vault.

## Git Conventions

- **Branch format**: `sebadlf-bec-{issue-number}-{short-description}` (copy from the Linear issue — it auto-generates this)
- **PR body**: must include the Linear issue ID (e.g., `BEC-42`) — triggers auto-link in Linear
- **Never commit directly to `main`** — protected branch, PR required
- **CI must pass** before merge: Ruff lint + format check, pytest (`.github/workflows/ci.yml`)
- **Auto-merge**: PRs no-draft se auto-mergean (squash) cuando CI pasa (`.github/workflows/auto-merge.yml`)

## Workflow

Para issues nuevos, el flujo es:

1. Leer el issue en Linear (via MCP) para entender el contexto.
2. Consultar notas relevantes del vault (`ai-pipeline-vault/`, via obsidian MCP) — al menos `projects/ai-pipeline/README.md`, ADRs relevantes, runbooks y domain notes que toquen el área. Para temas de ML/trading transversales, revisar `knowledge/ml/`.
3. Crear branch con el formato correcto.
4. Implementar, correr Ruff + tests localmente (`uv run ruff check . && uv run ruff format --check . && uv run pytest`).
5. Commitear y crear PR con link al issue de Linear.
6. Esperar CI verde y mergear (auto-merge se encarga). Linear auto-cierra el issue.
7. **Cierre del ticket — actualizar el vault (paso obligatorio, no opcional).** Antes de pasar al próximo ticket, escribir lo que corresponda usando el `obsidian` MCP. Criterios:
   - **ADR** en `projects/ai-pipeline/decisions/` — si introdujiste una decisión arquitectónica nueva, cambiaste una previa, o evaluaste alternativas que vale la pena recordar. Usar `_templates/tpl-adr.md` y numerar correlativo (`ADR-NNN`).
   - **Runbook** en `projects/ai-pipeline/runbooks/` — si codificaste un procedimiento operativo que se va a repetir (release, cleanup, debugging de un stage problemático). Usar `_templates/tpl-runbook.md`.
   - **Domain note** en `projects/ai-pipeline/domain/` — si descubriste un patrón del dominio (feature, modelo, comportamiento del pipeline) que el código solo no comunica.
   - **Daily log** del día en `daily-logs/YYYY-MM-DD.md` — siempre, una entrada por ticket cerrado con qué se hizo, aprendizajes, y links a notas creadas/actualizadas + runs de MLflow si aplica. Crear el archivo con `_templates/tpl-daily-log.md` si todavía no existe para hoy.
   - **`projects/ai-pipeline/README.md`** — actualizar si la nota nueva debería listarse en Decisiones, Runbooks o Notas de dominio.

   Si **ninguna** de las primeras tres aplica, igualmente registrar el ticket en el daily log con una línea que diga por qué no generó documentación nueva. Cero documentación silenciosa.
