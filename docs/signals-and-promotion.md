# Model Promotion and Signal Generation

**Files**: `src/evaluation/promote.py`, `src/strategy/runner.py`
**Makefile targets**: `make promote`, `make signals`
**Commands**: `uv run python -m src.evaluation.promote`, `uv run python -m src.strategy.runner`

## Purpose

These two modules close the loop between model training and actionable trading recommendations:

1. **Promotion** registers the best trained checkpoint per cluster in MLflow's Model Registry with a "champion" alias
2. **Signal generation** loads the champion models, builds features from the latest data, and outputs BUY/SELL/HOLD recommendations with confidence scores

## Model Promotion

### Process

For each cluster:

1. Look up the MLflow experiment `{prefix}/{cluster_id}` (e.g., `cluster/Technology_0`)
2. Search runs with `val_acc > 0`, ordered by `val_acc DESC`
3. For each candidate run (best accuracy first):
   - List artifacts looking for `.ckpt` files under `checkpoints/` or at root level
   - If a checkpoint is found → register this run
   - If no checkpoint → try the next run
4. Register the model:
   - Create a registered model named `trading-forecaster-{cluster_id}` (if not exists)
   - Create a new model version pointing to the checkpoint artifact
   - Set the alias `champion` on that version

### Why Best val_acc with Checkpoint

The promotion step explicitly selects training runs (which have checkpoints), not backtest or aggregation runs (which log metrics like Sharpe but have no checkpoint artifacts). This prevents the error of trying to load a model from a run that only has evaluation metrics.

### MLflow Model Registry

```
Model name:    trading-forecaster-Technology_0
Alias:         champion → v3
Source:        runs:/{run_id}/checkpoints/best-epoch=5-val_acc=0.7303.ckpt
```

The `champion` alias is a pointer that always resolves to the latest promoted version. Previous versions remain in the registry for comparison but are not actively used.

## Signal Generation

### End-to-End Flow

```
1. Load all symbols from clusters.parquet (or --symbols override)
2. Load OHLCV from database for those symbols
3. Run build_features() — full feature engineering pipeline
4. Drop all-null columns (e.g., adj_close when missing)
5. Filter to selected features (if feature_selection.enabled)
6. Drop rows with null features
7. Compute normalization stats from training period only
8. Load per-cluster checkpoint models
9. For each symbol:
   a. Find its cluster_id from clusters.parquet
   b. Extract last seq_len rows of features
   c. Z-score normalize using training statistics
   d. Forward pass through cluster model
   e. predict_proba() → [P(HOLD), P(BUY), P(SELL)]
   f. Classification: argmax → signal
10. Output all signals as DataFrame
```

### Normalization

Features are z-score normalized using statistics computed **only from the training period**:

```python
train_df = df.filter(pl.col("date") < train_end)
train_mean = train_df.select(feature_cols).to_numpy().mean(axis=0)
train_std  = train_df.select(feature_cols).to_numpy().std(axis=0)

# Applied to inference window
features = (raw_features - train_mean) / train_std
```

This prevents data leakage from future data into the normalization statistics.

### Feature Selection Integration

When `feature_selection.enabled` is true:

1. `get_selected_feature_names(config)` loads the manifest from `data/selected_features.json`
2. The feature column list is filtered to only include features present in both the manifest and the computed DataFrame
3. This ensures the runner uses exactly the same features that were used during training

### Checkpoint Discovery

The runner searches for checkpoints using glob patterns:

```
1. First pass: **/{cluster_id}-best-*.ckpt (excluding mlruns/)
2. Fallback:   mlruns/**/{cluster_id}-best-*.ckpt
```

Within matches, the most recently modified file is selected. This allows the runner to find checkpoints whether they are stored directly by Lightning or as MLflow artifacts.

### Output Format

The `main()` function prints signals grouped by type, sorted by confidence:

```
=== BUY (15 stocks) ===
  AAPL    conf=72.3%  buy=72.3%  sell=8.1%  hold=19.6%  [Technology_0]
  MSFT    conf=68.1%  buy=68.1%  sell=5.2%  hold=26.7%  [Technology_0]

=== SELL (8 stocks) ===
  XOM     conf=65.0%  buy=12.0%  sell=65.0%  hold=23.0%  [Energy_1]

=== HOLD (477 stocks) ===
  ...

Target: +2.5% BUY / -1.5% SELL in 21 trading days (~1 month)
```

### DataFrame Schema (returned by `generate_signals`)

| Column | Type | Description |
|---|---|---|
| symbol | str | Stock ticker |
| date | date | Date of latest data used |
| signal | str | "BUY", "SELL", or "HOLD" |
| confidence | float | Max probability across 3 classes |
| prob_buy | float | P(BUY) |
| prob_sell | float | P(SELL) |
| prob_hold | float | P(HOLD) |
| cluster_id | str | Which cluster model produced this |

## CLI Arguments

### `promote.py`

| Flag | Default | Description |
|---|---|---|
| `--config` | `configs/default.yaml` | Config file path |
| `--cluster` | all | Promote a single cluster only |

### `runner.py`

| Flag | Default | Description |
|---|---|---|
| `--symbols` | all from `clusters.parquet` | Override symbol list |

## Typical Pipeline Integration

In the full pipeline, promotion runs after backtesting and before signal generation:

```
make train → make aggregate → make portfolio → make backtest → make promote → make signals
```

However, `make promote` and `make signals` can also be run independently:

- `make promote` after a training session to register new champions
- `make signals` at any time to get recommendations from the current champions
