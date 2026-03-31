# Stage 2: Model Training

**File**: `src/training/train.py`
**Model**: `src/models/base_model.py`
**Dataset**: `src/models/dataset.py`
**Makefile target**: `make train`
**Command**: `uv run python -m src.training.train`

## Purpose

Train a separate LSTM ternary classifier (BUY/SELL/HOLD) for each stock cluster. Each model specializes in predicting forward 63-day returns for behaviorally similar stocks. Training uses PyTorch Lightning with MPS acceleration and logs everything to MLflow.

## Model Architecture: LSTMForecaster

```
Input (batch, seq_len, n_features)
    │
    ▼
LSTM (num_layers, hidden_size, dropout)
    │
    ▼
LayerNorm(hidden_size)
    │
    ▼
GELU activation
    │
    ▼
Dropout
    │
    ▼
Linear(hidden_size → num_classes=3)
    │
    ▼
Softmax (during inference only)
```

### Key Design Choices

| Parameter | Default | Rationale |
|---|---|---|
| `hidden_size` | 128 | Balances capacity and overfitting risk with ~500 stock, 20yr data |
| `num_layers` | 2 | Deep enough for temporal patterns without vanishing gradients |
| `dropout` | 0.3 | Regularization for financial data with low signal-to-noise |
| `label_smoothing` | 0.05 | Prevents overconfident predictions on noisy labels |
| `num_classes` | 3 | Ternary: 0=HOLD, 1=BUY, 2=SELL |

### Training Configuration

| Parameter | Default | Rationale |
|---|---|---|
| `learning_rate` | 0.001 | Standard for Adam on financial data |
| `weight_decay` | 0.0 | Regularization via dropout and label smoothing instead |
| `batch_size` | 64 | Fits in 24GB memory with MPS |
| `max_epochs` | 100 | Capped by early stopping |
| `gradient_clip_val` | 1.0 | Prevents gradient explosions on volatile regimes |
| `early_stopping_patience` | 10 | Stops when val_acc plateaus |

### Optimizer and Scheduler

- **Optimizer**: AdamW (from Lightning's configure_optimizers)
- **Scheduler**: `ReduceLROnPlateau` monitoring `val_loss`, factor=0.5, patience=5
- **Loss**: CrossEntropyLoss with label smoothing

## Dataset: TradingDataModule

### Data Loading Flow

```
features.parquet (or features_selected.parquet)
    │
    ▼
Filter by cluster_id using clusters.parquet
    │
    ▼
Sort by (symbol, date) — temporal order within each stock
    │
    ▼
Split into train / val / test by SplitDates
    │
    ▼
Per-split, per-symbol:
  Extract features array, track valid window indices
    │
    ▼
Concatenate all symbols into single array per split
    │
    ▼
TimeSeriesDataset with valid_indices guard
```

### Symbol-Boundary-Aware Windowing

The critical design feature in `dataset.py`. When stocks from a cluster are concatenated into a single feature matrix, naive sliding-window indexing would create sequences that span two different stocks:

```
... AAPL day N-1, AAPL day N | MSFT day 1, MSFT day 2 ...
                              ↑
              Window must NOT cross this boundary
```

The `setup()` method tracks an `offset` counter as it appends each symbol's data. For each symbol, valid window start indices are computed as `[offset, offset+1, ..., offset + len(symbol_data) - seq_len]`. Only these indices are stored in `valid_indices`. The dataset's `__getitem__` uses `valid_indices[idx]` to retrieve the sequence start position.

This ensures every training window contains data from exactly one stock.

### Feature Exclusion

The following columns are excluded from the feature matrix before training:

```python
EXCLUDE_COLS = {"id", "symbol", "date", "target", "adj_close"}
```

The `input_size` property of `TradingDataModule` returns `n_total_columns - len(EXCLUDE_COLS)`.

## Temporal Splits

Split dates are computed by `compute_split_dates(config, reference_date)` in `src/config.py`:

```
                    ┌──── train_end ────┐    ┌── val_end ──┐
|------- 17yr ------|----- purge 21d ---|-- 1yr --|- purge -|-- 2yr --|
start            train_end           val_start  val_end   test_start  today
```

| Segment | Duration | Purpose |
|---|---|---|
| Training | ~17 years | Learn price patterns |
| Purge gap | 21 days | Prevent target label leakage |
| Validation | 1 year | Hyperparameter tuning, early stopping |
| Purge gap | 21 days | Same |
| Test | 2 years | Held-out evaluation |

The 21-day purge gap matches the target horizon (21 trading days). Without this gap, validation samples near the train/val boundary would have target labels computed from prices that the training set also sees, causing overly optimistic validation metrics.

## Per-Cluster Training

`train_all_clusters(config)`:

1. Load `clusters.parquet` → get unique `cluster_id` list
2. For each cluster_id:
   a. Create `TradingDataModule` filtered to that cluster
   b. Verify sufficient data (train > 0, val > 0 sequences)
   c. Initialize `LSTMForecaster` with `input_size` from DataModule
   d. Configure `MLFlowLogger` with experiment `{prefix}/{cluster_id}`
   e. Train with Lightning `Trainer`:
      - `accelerator="mps"` for Apple GPU
      - `ModelCheckpoint` saves best by `val_acc`
      - `EarlyStopping` on `val_acc` with patience=10
      - `gradient_clip_val=1.0`
   f. Log best checkpoint to MLflow as artifact
   g. Log split dates, cluster_id, and architecture params

Clusters with insufficient data (empty splits) are skipped with a warning.

## MLflow Integration

### Experiment Naming

Each cluster gets its own MLflow experiment: `cluster/{cluster_id}` (e.g., `cluster/Technology_0`). The prefix is configurable.

### Logged Parameters

- `cluster_id`, `seq_len`, `batch_size`, `max_epochs`
- `hidden_size`, `num_layers`, `dropout`, `learning_rate`, `label_smoothing`
- `train_start`, `train_end`, `val_start`, `val_end`, `test_start`, `test_end`
- `train_samples`, `val_samples`

### Logged Metrics (per epoch)

- `train_loss`, `train_acc` — training set
- `val_loss`, `val_acc` — validation set

### Logged Artifacts

- Best checkpoint file (`.ckpt`) by validation accuracy

## CLI Arguments

| Flag | Default | Description |
|---|---|---|
| `--config` | `configs/default.yaml` | Config file path |
| `--cluster` | all | Train single cluster (e.g., `Technology_0`) |
