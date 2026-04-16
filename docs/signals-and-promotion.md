# Model Promotion and Signal Generation

**Files**: `src/evaluation/promote.py`, `src/evaluation/precision_eval.py`, `src/strategy/runner.py`
**Makefile targets**: `make promote`, `make signals`
**Commands**: `uv run python -m src.evaluation.promote`, `uv run python -m src.strategy.runner`

## Purpose

These modules close the loop between model training and actionable trading recommendations:

1. **Promotion** (Stage 3) evaluates trained models using cascading elimination with precision-focused walk-forward analysis, then registers the best per cluster in MLflow's Model Registry with a "champion" alias
2. **Signal generation** (Stage 7) loads the champion models, builds features from the latest data, and outputs `prob_up` predictions (probability of rising >= buy_threshold) for each stock

## Model Promotion — Cascading Elimination

### Overview

The promotion algorithm uses a precision-focused cascading elimination strategy rather than simple metric comparison. It evaluates model stability across multiple probability thresholds using walk-forward windows.

### Process

For each cluster:

1. Look up the MLflow experiment `{prefix}/{cluster_id}` (e.g., `cluster/Technology_0`)
2. Load candidate runs with their checkpoints
3. Apply cascading elimination filters:
   a. **Precision-at-threshold evaluation**: Test model at thresholds [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
   b. **Walk-forward stability**: Evaluate precision in sliding windows of 63 days (3x target horizon), stepping by 21 days (= target horizon)
   c. **Stability score**: `mean_precision - 1.0 * std_precision` at the primary threshold (0.65)
   d. **Minimum recall filter**: Require recall >= 0.10 at primary threshold
   e. **Minimum signals filter**: Require >= 3 UP predictions per walk-forward window
   f. **Std ratio filter**: Reject models where `precision_std / precision_mean > 0.25`
4. **Tiebreaking**: Within 0.01 margin of the best stability score, break ties by FP severity (false positive analysis — models with less severe false positives are preferred)
5. Register the winning model as "champion" in MLflow Model Registry

### Generalization-Adjusted Scoring

During ensemble training (Stage 2), the champion is selected using a generalization-adjusted score that penalizes val-to-test precision gaps:

```python
base_score = val_precision_up
if val_precision_up > 0 and test_precision_up > 0:
    gen_ratio = min(test_precision_up / val_precision_up, 1.0)
    score = base_score * (1.0 + gen_ratio) / 2.0
```

This prefers models where test precision is close to validation precision. A model with val_precision=0.45 and test_precision=0.43 (gen_ratio=0.96) scores higher than one with val_precision=0.50 and test_precision=0.30 (gen_ratio=0.60).

### Legacy Fallback

When the `promotion.evaluation` section is absent from config, the system falls back to simple metric comparison (`val_stability_score` or other configured metric).

### MLflow Model Registry

```
Model name:    trading-forecaster-{cluster_id}
Alias:         champion -> v3
Source:        runs:/{run_id}/checkpoints/best-epoch=5-val_precision_up=0.4535.ckpt
```

The `champion` alias is a pointer that always resolves to the latest promoted version. Previous versions remain in the registry for comparison but are not actively used.

### Promotion Configuration

```yaml
promotion:
  evaluation:
    thresholds: [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
    primary_threshold: 0.65
    min_recall: 0.10
    min_signals_per_window: 3
  walk_forward:
    window_size: 63          # 3x target horizon (trading days)
    step_size: 21            # = target horizon
    max_std_ratio: 0.25
    stability_penalty: 1.0   # score = mean - penalty * std
  ranking:
    tiebreak_margin: 0.01
```

## Signal Generation

### End-to-End Flow

```
1. Load all symbols from clusters.parquet (or --symbols override)
2. Load OHLCV from database for those symbols
3. Run build_features() -- full feature engineering pipeline
4. Run fill_nulls() -- forward-fill fundamentals, fill_nan(None), median-fill
5. Drop all-null columns
6. Filter to selected features (if feature_selection.enabled)
7. Load normalization stats from data/normalization_stats.json (training-period statistics)
8. Load per-cluster champion models from MLflow registry
9. For each symbol:
   a. Find its cluster_id from clusters.parquet
   b. Extract last seq_len rows of features
   c. Normalize using training-period statistics (clip + Z-score)
   d. Forward pass through cluster model
   e. predict_proba() -> [P(NOT_UP), P(UP)]
   f. Extract prob_up = P(UP)
10. Output all predictions as DataFrame
```

### Normalization

Features are normalized using statistics computed **only from the training period** and persisted in `data/normalization_stats.json`:

```python
# Stats loaded from normalization_stats.json
# Applied to inference window:
features = np.clip(raw_features, p01, p99)  # percentile clipping
features = (features - train_mean) / train_std  # Z-score
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
=== ACTIONABLE (prob_up >= 70%) -- 15 stocks ===
  AAPL    prob_up=85.3%  [Technology_0]
  MSFT    prob_up=78.1%  [Technology_0]
  GOOGL   prob_up=72.4%  [Technology_1]

=== BELOW THRESHOLD -- 488 stocks ===
  JPM     prob_up=65.0%  [Finance_0]
  ...

Target: +2.5% in 21 trading days (~1 month)
Min prob_up threshold: 70%
```

The actionable threshold is configurable via `training.actionable_threshold` (default: 0.70).

### DataFrame Schema (returned by `generate_signals`)

| Column | Type | Description |
|---|---|---|
| symbol | str | Stock ticker |
| date | date | Date of latest data used |
| prob_up | float | Probability of rising >= buy_threshold in 21 days |
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
make train-clusters -> make promote -> make aggregate -> make portfolio -> make backtest -> make signals
```

However, `make promote` and `make signals` can also be run independently:

- `make promote` after a training session to register new champions
- `make signals` at any time to get recommendations from the current champions
