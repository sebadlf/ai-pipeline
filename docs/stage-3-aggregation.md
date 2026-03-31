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
Find best checkpoint (.ckpt file)
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
  Forward pass → softmax probabilities
    │
    ▼
  Classify: argmax → BUY(1) / HOLD(0) / SELL(2)
    │
    ▼
Merge all predictions into single DataFrame
    │
    ▼
Save to predictions.parquet + DB + MLflow
```

## Checkpoint Discovery

`find_best_checkpoint(cluster_id, config)` searches for `.ckpt` files using a multi-path glob strategy:

1. First pass: search `checkpoints/`, `lightning_logs/` under the workspace root, excluding `mlruns/`
2. Second pass (fallback): search inside `mlruns/` directories

The search pattern matches files containing the `cluster_id` in the path. If multiple checkpoints exist, the file with the highest `val_acc` in its filename is selected (filenames follow Lightning's pattern: `best-epoch=X-val_acc=Y.Z.ckpt`).

## Inference Logic

`run_inference_for_cluster(cluster_id, symbols, config)`:

1. Load checkpoint → reconstruct `LSTMForecaster` with matching `input_size`
2. Load features parquet (respecting `get_features_parquet_path(config)`)
3. Filter to `symbol in symbols`
4. Exclude non-feature columns (`id`, `symbol`, `date`, `target`, `adj_close`)
5. For each symbol:
   - Extract the last `seq_len` rows (most recent data)
   - If insufficient data, skip
   - Convert to tensor, unsqueeze batch dimension
   - Forward pass → `predict_proba()` returns `[prob_hold, prob_buy, prob_sell]`
   - Classification: `argmax(probabilities)`
6. Return list of dicts with `symbol`, `prediction`, `confidence`, `prob_hold`, `prob_buy`, `prob_sell`, `cluster_id`

### Class Mapping

```python
CLASS_MAP = {0: "HOLD", 1: "BUY", 2: "SELL"}
```

## Output

### `data/predictions.parquet`

| Column | Type | Description |
|---|---|---|
| run_date | date | When predictions were generated |
| symbol | str | Stock ticker |
| cluster_id | str | Which cluster model produced this |
| prediction | str | "BUY", "HOLD", or "SELL" |
| confidence | float | Max probability across the 3 classes |
| prob_hold | float | P(HOLD) |
| prob_buy | float | P(BUY) |
| prob_sell | float | P(SELL) |

### `predictions` table (PostgreSQL)

Same schema, upserted on `(run_date, symbol)` conflict.

## MLflow Logging

- **Experiment**: `aggregation`
- **Metrics**: `total_predictions`, `buy_count`, `sell_count`, `hold_count`, `avg_confidence`
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
