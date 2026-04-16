# Stage 2: Model Training

**Files**: `src/training/train.py`, `src/training/optimize.py`
**Model**: `src/models/base_model.py`
**Dataset**: `src/models/dataset.py`
**Makefile target**: `make train-clusters`
**Command**: `uv run python -m src.training.train`

## Purpose

Train a separate LSTM binary classifier (UP/NOT_UP) for each stock cluster. Each model specializes in predicting whether a stock will rise >= buy_threshold (default +2.5%) in 21 trading days. Training uses PyTorch Lightning with MPS acceleration, Optuna hyperparameter optimization, and logs everything to MLflow.

## Model Architecture: LSTMForecaster

```
Input (batch, seq_len, n_features)
    |
    v
Input Dropout (tunable 0.05-0.4)
    |
    v
LSTM (num_layers, hidden_size, dropout, optional bidirectional)
    |
    v
[Optional] MultiheadAttention + LayerNorm (disabled by default)
    |
    v
Last-timestep selection (lstm_out[:, -1, :])
    |
    v
+ Residual connection (Linear projection of last input timestep only)
    |
    v
MLP Head:
  LayerNorm -> Linear(hidden -> head_hidden) -> GELU -> Dropout -> Linear(head_hidden -> 2)
    |
    v
FocalLoss (training) / Softmax (inference)
```

### Key Design Choices

| Parameter | Range (Optuna) | Rationale |
|---|---|---|
| `hidden_size` | [64, 96, 128] | Capped at 128 to prevent overfitting on ~50K samples per cluster |
| `num_layers` | 1-3 | Max 3 layers to limit capacity |
| `dropout` | 0.2-0.65 | Aggressive regularization for financial data with low SNR |
| `input_dropout` | 0.05-0.4 | Additional regularization on raw features |
| `head_hidden_ratio` | 0.25-0.5 | MLP head size as fraction of hidden_size |
| `label_smoothing` | 0.02-0.12 | Prevents overconfident predictions on noisy labels |
| `focal_gamma` | 0.0-3.0 | Focal loss focusing parameter (0 = standard CrossEntropy) |

### Residual Connection

The residual connection projects the **last timestep only** of the input (`x[:, -1, :]`) to match `effective_hidden` dimension, then adds it to the LSTM output. This avoids bypassing the LSTM with a full-sequence linear shortcut while still providing gradient flow.

### Loss Function

- **FocalLoss** (when `focal_gamma > 0`): Down-weights well-classified examples, focusing training on hard negatives. Combined with inverse-frequency class weights for double imbalance correction
- **CrossEntropy** (when `focal_gamma = 0`): Standard loss with class weights and label smoothing
- Class weights are computed automatically from training set class distribution

### Optimizer and Scheduler

- **Optimizer**: AdamW (default, fixed param). Also supports RAdam, SGD+Nesterov, Lion
- **Scheduler**: `ReduceLROnPlateau` monitoring `val_precision_up` (mode="max"), factor=0.5, patience=5
- **Gradient clipping**: 2.0 (prevents gradient explosions on volatile regimes)

### Logged Metrics (per epoch)

| Metric | Description |
|---|---|
| `train_loss`, `val_loss` | Loss per split |
| `train_acc`, `val_acc` | Overall accuracy |
| `train_precision_up`, `val_precision_up` | Precision for UP class |
| `train_recall_up`, `val_recall_up` | Recall for UP class |
| `val_mean_prob_up` | Mean predicted probability of UP |
| `val_prob_up_std` | Std of predicted probabilities |
| `val_pct_above_060`, `val_pct_above_065` | Calibration diagnostics |

## Data Augmentation

Two augmentation techniques are applied **only during training**:

1. **Gaussian noise injection**: Adds `N(0, noise_std)` to input features. `noise_std` is tunable (0.01-0.08) via Optuna
2. **Feature masking**: Randomly zeroes out 10% of features per sample (`feature_mask_rate=0.10`, fixed param). Forces the model to not depend on individual features

Both are implemented in `TimeSeriesDataset.__getitem__()`.

## Dataset: TradingDataModule

### Data Loading Flow

```
features_normalized.parquet
    |
    v
Filter by cluster_id using clusters.parquet
    |
    v
[Optional] Filter to optimization symbols (for Optuna subset search)
    |
    v
Sort by (symbol, date) -- temporal order within each stock
    |
    v
Split into train / val / test by SplitDates
    |
    v
Per-split, per-symbol:
  Extract features array, track valid window indices
    |
    v
Concatenate all symbols into single array per split
    |
    v
TimeSeriesDataset with valid_indices guard + augmentation (train only)
```

### Symbol-Boundary-Aware Windowing

When stocks from a cluster are concatenated into a single feature matrix, naive sliding-window indexing would create sequences that span two different stocks:

```
... AAPL day N-1, AAPL day N | MSFT day 1, MSFT day 2 ...
                              ^
              Window must NOT cross this boundary
```

The `setup()` method tracks an `offset` counter as it appends each symbol's data. For each symbol, valid window start indices are computed as `[offset, offset+1, ..., offset + len(symbol_data) - seq_len]`. Only these indices are stored in `valid_indices`. The dataset's `__getitem__` uses `valid_indices[idx]` to retrieve the sequence start position.

### Feature Exclusion

```python
EXCLUDE_COLS = {"id", "symbol", "date", "target", "adj_close"}
```

Columns starting with `forward_return_` are also excluded. The `input_size` property returns the count of remaining feature columns.

## Temporal Splits

Split dates are computed by `compute_split_dates(config, reference_date)` in `src/config.py`:

```
                    +---- train_end ----+    +-- val_end --+
|------- ~6yr ------|----- purge 21d ---|-- 1yr --|- purge -|-- 1yr --|
start            train_end           val_start  val_end   test_start  today
```

| Segment | Duration | Purpose |
|---|---|---|
| Training | ~6 years (dev: 8yr lookback minus val+test) | Learn price patterns |
| Purge gap | 21 days | Prevent target label leakage |
| Validation | 1 year | Hyperparameter tuning, early stopping |
| Purge gap | 21 days | Same |
| Test | 1 year | Held-out evaluation |

The 21-day purge gap matches the target horizon (21 trading days). Without this gap, validation samples near the train/val boundary would have target labels computed from prices that the training set also sees.

## Optuna Hyperparameter Optimization

### Overview

Each cluster gets its own Optuna study (`cluster-v2/{cluster_id}`) persisted to PostgreSQL for warm-starting across pipeline runs.

### Search Space (~12 tunable params)

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

### Fixed Params (not searched)

| Parameter | Value | Rationale |
|---|---|---|
| optimizer_name | adamw | Robust default |
| scheduler_factor | 0.5 | Standard LR reduction |
| scheduler_patience | 5 | Standard plateau detection |
| gradient_clip_val | 2.0 | Prevents gradient explosions |
| bidirectional | false | Reduces capacity |
| num_attention_heads | 0 | Disabled to reduce overfitting |
| activation | gelu | Best empirical performance |
| feature_mask_rate | 0.10 | 10% random feature dropout |

### Objective Function

The objective is mean `precision_at_threshold` (threshold=0.50) across 3 time-series CV folds:

1. For each fold, train on expanding window, validate on next segment
2. Compute precision of UP predictions at the configured probability threshold
3. Apply **recall floor**: if recall < 0.15, apply quadratic penalty
4. Average across folds

#### Overfitting Gap Penalty

After each fold, the overfit gap is computed: `gap = max(0, train_acc - val_acc)`. If the average gap across folds exceeds `max_overfit_gap` (default 0.30), the objective score is scaled down:

```
if avg_gap > max_overfit_gap:
    score *= max_overfit_gap / avg_gap   # e.g., 0.30/0.40 = 0.75
```

This prevents Optuna from selecting configs that memorize the training set even if they achieve decent validation precision by chance.

### Convergence and Pruning

- **Convergence detection**: Study stops if no improvement in 3 (dev) / 5 (prod) consecutive completed trials
- **Pruning**: MedianPruner applied on last fold, with startup period (2 dev / 5 prod trials) without pruning
- **Subset search**: During Optuna trials, only `n_symbols_per_cluster` (dev:2, prod:3) symbols are used for speed

### Ensemble Training

After Optuna completes:

1. **Deduplication**: Top trials are checked for near-duplicates across 10 key params (learning_rate, hidden_size, num_layers, dropout, etc.). Configs within tolerance thresholds are collapsed
2. **Top-3 training**: The top 3 deduplicated configs are trained as full models on the complete cluster data (all symbols, full epochs)
3. **MLflow logging**: Each ensemble member gets its own MLflow run under `cluster/{cluster_id}`

### Champion Selection

After all 3 ensemble members are trained, the best one is tagged as "champion" using a **generalization-adjusted score**:

```python
base_score = val_precision_up
if val_precision_up > 0 and test_precision_up > 0:
    gen_ratio = min(test_precision_up / val_precision_up, 1.0)
    score = base_score * (1.0 + gen_ratio) / 2.0
```

This prefers models where test precision is close to validation precision, penalizing models that overfit to the validation set.

### Dual Early Stopping

Two early stopping callbacks during final model training:

1. **Primary**: Monitors `val_precision_up`, patience dev:3 / prod:10. Stops when precision plateaus
2. **Secondary (circuit breaker)**: Monitors `val_loss`, patience = primary_patience + 10. Prevents training continuation when validation loss is diverging even if precision hasn't dropped yet

## Per-Cluster Training Flow

`train_all_clusters(config)`:

1. Load `clusters.parquet` -> get unique `cluster_id` list
2. Run per-cluster Optuna optimization (in parallel, `max_workers` processes with `spawn` context)
3. For each cluster:
   a. Create Optuna study (or load existing from PostgreSQL)
   b. Run `n_trials` with 3-fold CV each
   c. Select top-3 deduplicated configs
   d. Train full models for each config
   e. Tag champion based on generalization-adjusted score
   f. Log all runs to MLflow under `cluster/{cluster_id}`

### Parallel Training

Clusters train in parallel via `multiprocessing` with `spawn` context (required for MPS safety). Each worker gets its own MPS context and DB connection. Configurable via `training.max_workers` (default: 4 in dev/prod). ~2-3GB RAM per worker; 4 workers fit in 24GB with headroom.

## MLflow Integration

### Experiment Naming

Each cluster gets its own MLflow experiment: `cluster/{cluster_id}` (e.g., `cluster/Technology_0`). The prefix is configurable via `training.cluster_experiment_prefix`.

### Logged Parameters

- `cluster_id`, `seq_len`, `batch_size`, `max_epochs`
- `hidden_size`, `num_layers`, `dropout`, `learning_rate`, `label_smoothing`
- `focal_gamma`, `noise_std`, `input_dropout`, `head_hidden_ratio`, `weight_decay`
- `train_start`, `train_end`, `val_start`, `val_end`, `test_start`, `test_end`
- `train_samples`, `val_samples`
- `ensemble_rank` (1, 2, or 3)

### Logged Metrics

Per-epoch metrics (see table above) plus final test metrics.

### Logged Artifacts

- Best checkpoint file (`.ckpt`) by `val_precision_up`

## Training Configuration (dev vs prod)

| Parameter | Dev | Prod |
|---|---|---|
| `max_epochs` | 10 | 50 |
| `batch_size` | 256 | 128 |
| `early_stopping_patience` | 3 | 10 |
| `optuna.n_trials` | 5 | 15 |
| `optuna.epochs_per_trial` | 5 | 30 |
| `optuna.patience_per_trial` | 3 | 7 |
| `optuna.startup_trials` | 2 | 5 |
| `optuna.convergence_patience` | 3 | 5 |
| `optuna.n_symbols_per_cluster` | 2 | 3 |
| `optuna.max_history_days` | 7 | 60 |

## CLI Arguments

| Flag | Default | Description |
|---|---|---|
| `--config` | `configs/default.yaml` | Config file path |
| `--cluster` | all | Train single cluster (e.g., `Technology_0`) |
