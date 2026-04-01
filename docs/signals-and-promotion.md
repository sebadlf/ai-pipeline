# Model Promotion and Signal Generation

**Files**: `src/evaluation/promote.py`, `src/strategy/runner.py`
**Makefile targets**: `make promote`, `make signals`
**Commands**: `uv run python -m src.evaluation.promote`, `uv run python -m src.strategy.runner`

## Purpose

These two modules close the loop between model training and actionable trading recommendations:

1. **Promotion** registers the best trained checkpoint per cluster in MLflow's Model Registry with a "champion" alias
2. **Signal generation** loads the champion models, builds features from the latest data, and outputs `prob_up` predictions (probability of rising ≥ buy_threshold) for each stock

## Model Promotion

### Process

For each cluster:

1. Look up the MLflow experiment `{prefix}/{cluster_id}` (e.g., `cluster/Technology_0`)
2. Search runs with `val_acc > 0`, ordered by `val_acc DESC`
3. For each candidate run (best accuracy first):
   - List artifacts looking for `.ckpt` files in all artifact directories
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
4. Run fill_nulls() — forward-fill fundamentals, fill_nan(None), median-fill
5. Drop all-null columns
6. Filter to selected features (if feature_selection.enabled)
7. Compute normalization stats from training period only
8. Load per-cluster champion models from MLflow registry
9. For each symbol:
   a. Find its cluster_id from clusters.parquet
   b. Extract last seq_len rows of features
   c. Z-score normalize using training statistics
   d. Forward pass through cluster model
   e. predict_proba() → [P(NOT_UP), P(UP)]
   f. Extract prob_up = P(UP)
10. Output all predictions as DataFrame
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

This prevents data leakage from future data into the normalization statistics. Residual NaN values (from columns that are entirely null for a symbol) are replaced with 0.0 via `np.nan_to_num`.

### Feature Selection Integration

When `feature_selection.enabled` is true:

1. `get_selected_feature_names(config)` loads the manifest from `data/selected_features.json`
2. The feature column list is filtered to only include features present in both the manifest and the computed DataFrame
3. This ensures the runner uses exactly the same features that were used during training

### Checkpoint Discovery

The runner loads champion models from the MLflow Model Registry using `download_champion_checkpoint(cluster_id)`. If no champion is registered, it falls back to local checkpoint discovery via glob patterns.

### Output Format

The `main()` function prints predictions in two groups, sorted by `prob_up` descending:

```
=== ACTIONABLE (prob_up >= 70%) — 15 stocks ===
  AAPL    prob_up=85.3%  [Technology_0]
  MSFT    prob_up=78.1%  [Technology_0]
  GOOGL   prob_up=72.4%  [Technology_1]

=== BELOW THRESHOLD — 488 stocks ===
  JPM     prob_up=65.0%  [Finance_0]
  ...

Target: +2.5% in 21 trading days (~1 month)
Min prob_up threshold: 70%
```

### DataFrame Schema (returned by `generate_signals`)

| Column | Type | Description |
|---|---|---|
| symbol | str | Stock ticker |
| date | date | Date of latest data used |
| prob_up | float | Probability of rising ≥ buy_threshold in 21 days |
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

In the full pipeline, promotion runs after training and before aggregation:

```
make train → make promote → make aggregate → make portfolio → make backtest → make signals
```

However, `make promote` and `make signals` can also be run independently:

- `make promote` after a training session to register new champions
- `make signals` at any time to get recommendations from the current champions
