# Stage 3: Prediction Aggregation

**File**: `src/aggregation/consolidate.py`
**Makefile target**: `make aggregate`
**Command**: `uv run python -m src.aggregation.consolidate`

## Purpose

Load the ensemble model checkpoints (top-3) for each cluster, run inference on the most recent time window for every stock, compute weighted-average predictions, and consolidate all per-cluster results into a single unified output. This bridges the gap between per-cluster model training and portfolio-level decision making.

## End-to-End Flow

```
For each cluster_id in clusters.parquet:
    │
    ▼
Load ensemble checkpoints (up to 3) from MLflow registry
    │
    ▼
Load LSTMForecaster from each checkpoint
    │
    ▼
For each symbol in cluster:
    │
    ▼
  Load features (from features_normalized.parquet)
    │
    ▼
  Extract last seq_len rows for the symbol
    │
    ▼
  Normalize using training-period statistics (from normalization_stats.json)
    │
    ▼
  Forward pass through each ensemble member → softmax → prob_up
    │
    ▼
  Weighted average: weights proportional to each model's val_precision_up
    │
    ▼
Merge all predictions into single DataFrame
    │
    ▼
Detect normalization drift (warn if feature distributions deviate >3 std)
    │
    ▼
Save to predictions.parquet + DB + MLflow
```

## Checkpoint Discovery

The aggregation step loads **ensemble member** checkpoints from MLflow Model Registry. For each cluster, it downloads the champion and any additional ensemble members tagged in the experiment. If no champion is registered for a cluster, it falls back to local checkpoint discovery via glob patterns across `checkpoints/`, `mlruns/`, and the workspace root.

## Weighted Ensemble Inference

When multiple ensemble members are available for a cluster:

1. Each model produces its own `prob_up` prediction per symbol
2. Predictions are combined using a **weighted average**, where weights are proportional to each model's `val_precision_up` metric
3. Models with higher validation precision contribute more to the final prediction

This reduces variance compared to simple averaging and gives more influence to the best-calibrated models.

## Normalization Drift Detection

After computing predictions, the aggregation step checks for **normalization drift**: whether the current feature distributions have shifted significantly from the training-period statistics used for normalization. If any feature's mean or std deviates by more than 3 standard deviations from the stored training statistics, a warning is logged. This helps detect data quality issues or concept drift.

## Inference Logic

`run_inference_for_cluster(cluster_id, models, features_df, clusters_df, config, split_dates)`:

1. Filter features to symbols in the cluster
2. Determine feature columns (from `get_selected_feature_names()` if enabled, else all non-meta columns)
3. Validate feature count matches model's `input_size`
4. Load normalization statistics from `normalization_stats.json`
5. For each symbol:
   - Extract the last `seq_len` rows (most recent data)
   - If insufficient data, skip
   - Normalize features using training-period mean/std
   - Forward pass through each ensemble member → `predict_proba()` returns `[P(NOT_UP), P(UP)]`
   - Weighted average of `prob_up` across ensemble members
6. Return list of dicts with `symbol`, `cluster_id`, `prob_up`

## Output

### `data/predictions.parquet`

| Column | Type | Description |
|---|---|---|
| symbol | str | Stock ticker |
| cluster_id | str | Which cluster model produced this |
| prob_up | float | Probability of rising ≥ buy_threshold in 21 days |
| model_run_id | str | MLflow run ID of the model used (null for local fallback) |

### `predictions` table (PostgreSQL)

Same columns plus `run_date`, upserted on `(run_date, symbol)` conflict.

## MLflow Logging

- **Experiment**: `aggregation`
- **Metrics**: `total_predictions`, `n_actionable` (prob_up ≥ 70%), `mean_prob_up`
- **Artifact**: `data/predictions.parquet`

## Feature Selection Integration

When `feature_selection.enabled` is true in config:
- Features are loaded from `data/features_selected.parquet` instead of `data/features.parquet`
- The `get_features_parquet_path(config)` helper function centralizes this logic
- This ensures inference uses exactly the same features that were used during training

## Edge Cases

- **Missing checkpoint**: If no `.ckpt` file is found for a cluster, the cluster is skipped with a warning
- **Insufficient data**: Symbols with fewer than `seq_len` recent rows are skipped
- **Empty clusters**: If a cluster has no successful predictions, it is skipped
- **Feature mismatch**: If the number of features doesn't match the model's `input_size`, a `ValueError` is raised
