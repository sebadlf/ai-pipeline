# Stage 3: Prediction Aggregation

**File**: `src/aggregation/consolidate.py`
**Makefile target**: `make aggregate`
**Command**: `uv run python -m src.aggregation.consolidate`

## Purpose

Load the best trained checkpoint for each cluster, run inference on the most recent time window for every stock, and consolidate all per-cluster predictions into a single unified output. This bridges the gap between per-cluster model training and portfolio-level decision making.

## End-to-End Flow

```
For each cluster_id in clusters.parquet:
    │
    ▼
Find champion checkpoint from MLflow registry (fallback: local .ckpt)
    │
    ▼
Load LSTMForecaster from checkpoint
    │
    ▼
For each symbol in cluster:
    │
    ▼
  Load features (from features_selected.parquet if enabled)
    │
    ▼
  Extract last seq_len rows for the symbol
    │
    ▼
  Z-score normalize using training-period statistics
    │
    ▼
  Forward pass → softmax → prob_up = P(UP)
    │
    ▼
Merge all predictions into single DataFrame
    │
    ▼
Save to predictions.parquet + DB + MLflow
```

## Checkpoint Discovery

`find_best_checkpoint(cluster_id, config)` searches for `.ckpt` files using a multi-path glob strategy across `checkpoints/`, `mlruns/`, and the workspace root. If multiple checkpoints exist, the most recently modified file is selected.

The aggregation step first tries to download the **champion** checkpoint from MLflow Model Registry (via `download_champion_checkpoint()`). If no champion is registered for a cluster, it falls back to local checkpoint discovery.

## Inference Logic

`run_inference_for_cluster(cluster_id, model, features_df, clusters_df, config, split_dates)`:

1. Filter features to symbols in the cluster
2. Determine feature columns (from `get_selected_feature_names()` if enabled, else all non-meta columns)
3. Validate feature count matches model's `input_size`
4. Compute normalization statistics from training period only (Z-score)
5. For each symbol:
   - Extract the last `seq_len` rows (most recent data)
   - If insufficient data, skip
   - Normalize features using training-period mean/std
   - Convert to tensor, forward pass → `predict_proba()` returns `[P(NOT_UP), P(UP)]`
   - Extract `prob_up = float(probs[1])`
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
