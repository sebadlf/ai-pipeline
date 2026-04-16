# Documentation Index

This directory contains detailed documentation for each stage of the trading ML pipeline. For a quick overview, see [CLAUDE.md](../CLAUDE.md) in the project root.

## Pipeline Stages

The pipeline consists of 7 main stages:

### Stage 0: Data Ingestion & Feature Engineering
- **[stage-0-ingestion.md](stage-0-ingestion.md)** — FMP API data fetching into PostgreSQL
  - 7 data sources (OHLCV, adj close, treasury, VIX, fundamentals, sector performance)
  - Smart adjClose refresh with probe-and-refresh mechanism
  - Database schema details

- **[stage-0-features.md](stage-0-features.md)** — Feature engineering, selection, and normalization
  - 12 categories of features (technical, macro, VIX, fundamentals, sector, cyclical)
  - Feature selection filters (null, variance, correlation, mutual information)
  - Percentile clipping + Z-score normalization with persistent training-set stats
  - Null handling strategy

### Stage 1: Stock Clustering
- **[stage-1-clustering.md](stage-1-clustering.md)** — KMeans clustering
  - 20 clustering features (behavioral, macro-sensitivity, fundamentals)
  - Global KMeans (prod) or sector-based (dev)
  - Automatic K selection via silhouette scoring
  - PCA dimensionality reduction

### Stage 2: Model Training
- **[stage-2-training.md](stage-2-training.md)** — LSTM training per cluster
  - LSTMForecaster with FocalLoss, input dropout, residual connection, MLP head
  - Optuna optimization (~12 tunable params) with overfitting gap penalty
  - Ensemble top-3 deduplicated configs per cluster
  - Generalization-adjusted champion selection
  - Data augmentation (Gaussian noise + feature masking)
  - Dual early stopping (precision + val_loss circuit breaker)
  - MPS GPU acceleration on macOS

### Stage 3: Model Promotion
- **[signals-and-promotion.md](signals-and-promotion.md)** — Model registry and trading signals
  - Cascading elimination with precision-at-threshold evaluation
  - Walk-forward stability scoring with FP severity tiebreaking
  - Generalization-adjusted champion scoring (val-to-test precision gap)

### Stage 4: Prediction Aggregation
- **[stage-3-aggregation.md](stage-3-aggregation.md)** — Consolidate per-cluster predictions
  - Champion model loading from MLflow Registry
  - Weighted ensemble inference (weights by val_precision_up)
  - Normalization drift detection
  - Feature selection integration

### Stage 5: Portfolio Optimization
- **[stage-4-portfolio.md](stage-4-portfolio.md)** — Multi-profile portfolio design
  - 3 risk profiles (Aggressive min_prob_up 60%, Moderate 65%, Conservative 70%)
  - SLSQP optimization with diversification constraints
  - Risk metrics (Sharpe, Sortino, Calmar, Omega, Information)

### Stage 6: Backtesting
- **[stage-5-backtest.md](stage-5-backtest.md)** — Regime-aware backtesting
  - Bull/bear/sideways regime detection
  - Position-level stop-loss/take-profit
  - Portfolio circuit breaker at 25% drawdown
  - Periodic rebalancing every 21 trading days

### Stage 7: Signal Generation
- **[signals-and-promotion.md](signals-and-promotion.md)** — Trading signals from champion models
  - Load champion models per cluster from MLflow registry
  - Generate prob_up predictions for all or specified symbols
  - Actionable stock filtering above threshold

## Architecture

- **[architecture.md](architecture.md)** — High-level system design
  - Hybrid Docker/Native architecture rationale
  - 7-stage pipeline data flow diagrams
  - Key design decisions (overfitting mitigation, generalization scoring, etc.)

## Quick Navigation

| If you want to... | Read this file |
|-------------------|----------------|
| Understand the overall system | [architecture.md](architecture.md) |
| Add new data sources | [stage-0-ingestion.md](stage-0-ingestion.md) |
| Modify features or add indicators | [stage-0-features.md](stage-0-features.md) |
| Change clustering algorithm | [stage-1-clustering.md](stage-1-clustering.md) |
| Modify model architecture | [stage-2-training.md](stage-2-training.md) |
| Adjust training hyperparameters | [stage-2-training.md](stage-2-training.md) + `configs/default.yaml` |
| Understand Optuna optimization | [stage-2-training.md](stage-2-training.md) |
| Change portfolio constraints | [stage-4-portfolio.md](stage-4-portfolio.md) |
| Modify backtest risk management | [stage-5-backtest.md](stage-5-backtest.md) |
| Understand model promotion | [signals-and-promotion.md](signals-and-promotion.md) |
| Generate trading signals | [signals-and-promotion.md](signals-and-promotion.md) |

## Related Files

- **Primary context**: [CLAUDE.md](../CLAUDE.md) — Complete technical reference for AI assistants
- **User guide**: [README.md](../README.md) — Setup and basic usage
- **Configuration**: [configs/default.yaml](../configs/default.yaml) — All hyperparameters
- **Orchestration**: [Makefile](../Makefile) — All available commands

## Commands Reference

```bash
# Start infrastructure
docker compose up -d

# Run pipeline stages
make ingest-force        # Stage 0a: FMP API -> PostgreSQL
make features            # Stage 0b: Feature engineering
make select-features     # Stage 0c: Feature selection
make normalize           # Stage 0d: Percentile clipping + Z-score
make cluster             # Stage 1: Stock clustering
make train-clusters      # Stage 2: Optuna + ensemble training per cluster
make promote             # Stage 3: Cascading elimination -> champions
make aggregate           # Stage 4: Weighted ensemble predictions
make portfolio           # Stage 5: Portfolio optimization
make backtest            # Stage 6: Regime-aware backtesting
make signals             # Stage 7: Generate trading signals

# Full pipeline
make pipeline            # Dev pipeline (skips ingestion)
make pipeline-prod       # Prod pipeline (includes ingestion)
make pipeline-loop       # Continuous pipeline loop
```

## Data Flow

```
FMP API
    │
    ▼
PostgreSQL (11 tables)
    │
    ├──▶ Features ──▶ Selection ──▶ Normalize ──▶ Clustering
    │      │                                          │
    │      │                                          ▼
    │      └──────────────────────────────▶ Optuna + Training (per cluster)
    │                                              │
    │                                              ▼
    │                                     Promote ──▶ MLflow Registry
    │                                              │
    │                                              ▼
    │                                   Aggregation ──▶ Predictions
    │                                              │
    │                                              ▼
    │                                    Portfolio ──▶ Allocations
    │                                              │
    │                                              ▼
    │                                    Backtest ──▶ Results
    │                                              │
    └──────────────────────────────────────────────┘
```

---

*For the complete technical context including detailed tables, configuration reference, and common tasks, see [CLAUDE.md](../CLAUDE.md).*
