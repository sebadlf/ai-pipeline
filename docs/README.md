# Documentation Index

This directory contains detailed documentation for each stage of the trading ML pipeline. For a quick overview, see [AGENTS.md](../AGENTS.md) in the project root.

## Pipeline Stages

The pipeline consists of 5 main stages plus supporting workflows:

### Stage 0: Data Ingestion & Feature Engineering
- **[stage-0-ingestion.md](stage-0-ingestion.md)** — FMP API data fetching into PostgreSQL
  - 7 data sources (OHLCV, adj close, treasury, VIX, fundamentals, sector performance)
  - Smart adjClose refresh with probe-and-refresh mechanism
  - Database schema details

- **[stage-0-features.md](stage-0-features.md)** — Feature engineering and selection
  - 11 categories of features (technical, macro, VIX, fundamentals, sector)
  - Feature selection filters (null, variance, correlation)
  - Null handling strategy

### Stage 1: Stock Clustering
- **[stage-1-clustering.md](stage-1-clustering.md)** — KMeans clustering by sector
  - 19 clustering features (behavioral, macro-sensitivity, fundamentals)
  - Automatic K selection via silhouette scoring
  - PCA dimensionality reduction

### Stage 2: Model Training
- **[stage-2-training.md](stage-2-training.md)** — LSTM training per cluster
  - LSTMForecaster architecture (96 hidden, 2 layers, 0.35 dropout)
  - Temporal splits with 21-day purge gaps
  - Optuna hyperparameter optimization
  - MPS GPU acceleration on macOS

### Stage 3: Prediction Aggregation
- **[stage-3-aggregation.md](stage-3-aggregation.md)** — Consolidate per-cluster predictions
  - Champion model loading from MLflow Registry
  - Inference and prob_up extraction
  - Feature selection integration

### Stage 4: Portfolio Optimization
- **[stage-4-portfolio.md](stage-4-portfolio.md)** — Multi-profile portfolio design
  - 3 risk profiles (Aggressive, Moderate, Conservative)
  - SLSQP optimization with diversification constraints
  - Risk metrics (Sharpe, Sortino, Calmar, Omega, Information)

### Stage 5: Backtesting
- **[stage-5-backtest.md](stage-5-backtest.md)** — Regime-aware backtesting
  - Bull/bear/sideways regime detection
  - Position-level stop-loss/take-profit
  - Portfolio circuit breaker at 25% drawdown

### Promotion & Signals
- **[signals-and-promotion.md](signals-and-promotion.md)** — Model registry and trading signals
  - Champion model registration in MLflow
  - Precision-focused promotion algorithm
  - Signal generation from champion models

## Architecture

- **[architecture.md](architecture.md)** — High-level system design
  - Hybrid Docker/Native architecture rationale
  - Data flow diagrams
  - Key design decisions

## Quick Navigation

| If you want to... | Read this file |
|-------------------|----------------|
| Understand the overall system | [architecture.md](architecture.md) |
| Add new data sources | [stage-0-ingestion.md](stage-0-ingestion.md) |
| Modify features or add indicators | [stage-0-features.md](stage-0-features.md) |
| Change clustering algorithm | [stage-1-clustering.md](stage-1-clustering.md) |
| Modify model architecture | [stage-2-training.md](stage-2-training.md) |
| Adjust training hyperparameters | [stage-2-training.md](stage-2-training.md) + `configs/default.yaml` |
| Change portfolio constraints | [stage-4-portfolio.md](stage-4-portfolio.md) |
| Modify backtest risk management | [stage-5-backtest.md](stage-5-backtest.md) |
| Understand model promotion | [signals-and-promotion.md](signals-and-promotion.md) |
| Generate trading signals | [signals-and-promotion.md](signals-and-promotion.md) |

## Related Files

- **Primary context**: [AGENTS.md](../AGENTS.md) — Complete technical reference for AI assistants
- **User guide**: [README.md](../README.md) — Setup and basic usage
- **Configuration**: [configs/default.yaml](../configs/default.yaml) — All hyperparameters
- **Orchestration**: [Makefile](../Makefile) — All available commands

## Commands Reference

```bash
# Start infrastructure
docker compose up -d

# Run pipeline stages
make ingest              # Stage 0a
make features            # Stage 0b
make select-features     # Stage 0c
make cluster             # Stage 1
make train               # Stage 2
make aggregate           # Stage 3
make portfolio           # Stage 4
make backtest            # Stage 5

# Promotion and signals
make promote             # Register best models
make signals             # Generate trading signals

# Full pipeline
make pipeline            # Run all stages
```

## Data Flow

```
FMP API
    │
    ▼
PostgreSQL (11 tables)
    │
    ├──▶ Features ──▶ Selection ──▶ Clustering
    │      │                            │
    │      │                            ▼
    │      └──────────────────────▶ Training ──▶ MLflow
    │                                        │
    │                                        ▼
    │                              Aggregation ──▶ Predictions
    │                                        │
    │                                        ▼
    │                              Portfolio ──▶ Allocations
    │                                        │
    │                                        ▼
    │                              Backtest ──▶ Results
    │                                        │
    └────────────────────────────────────────┘
```

---

*For the complete technical context including detailed tables, configuration reference, and common tasks, see [AGENTS.md](../AGENTS.md).*
