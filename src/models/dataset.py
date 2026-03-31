"""Dataset and DataModule for time series sequences."""

from __future__ import annotations

import datetime as dt
import os

import lightning as L
import numpy as np
import polars as pl
import torch
from torch.utils.data import DataLoader, Dataset

_NUM_WORKERS = min(os.cpu_count() or 0, 8)

EXCLUDE_COLS = {"id", "symbol", "date", "target", "adj_close"}


class TimeSeriesDataset(Dataset):
    """Sliding window dataset with symbol-boundary-aware indexing.

    Only yields windows that fall entirely within a single symbol's
    time series, preventing cross-symbol contamination.

    Args:
        features: Flat feature array of shape (total_timesteps, n_features).
        targets: Flat target array of shape (total_timesteps,).
        seq_len: Number of timesteps per sample.
        valid_indices: Pre-computed starting indices for windows that
            do not cross symbol boundaries.
        target_dtype: Torch dtype for targets (int64 for classification).
    """

    def __init__(
        self,
        features: np.ndarray,
        targets: np.ndarray,
        seq_len: int,
        valid_indices: np.ndarray,
        target_dtype: torch.dtype = torch.int64,
        is_train: bool = False,
        noise_std: float = 0.01,
    ) -> None:
        self.features = torch.tensor(features, dtype=torch.float32)
        self.targets = torch.tensor(targets, dtype=target_dtype)
        self.seq_len = seq_len
        self.valid_indices = valid_indices
        self.is_train = is_train
        self.noise_std = noise_std

    def __len__(self) -> int:
        return len(self.valid_indices)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        start = int(self.valid_indices[idx])
        x = self.features[start : start + self.seq_len]
        y = self.targets[start + self.seq_len]

        # Gaussian noise augmentation during training only
        if self.is_train and self.noise_std > 0:
            x = x + torch.randn_like(x) * self.noise_std

        return x, y


class TradingDataModule(L.LightningDataModule):
    """DataModule for loading and splitting trading feature data.

    Uses date-based temporal splits with purge gaps:
    train [start..train_end] | PURGE | val [val_start..val_end] | PURGE | test [test_start..]

    Supports per-cluster filtering when cluster_id is specified.

    Args:
        parquet_path: Path to features parquet file.
        seq_len: Sequence length for sliding window.
        batch_size: Batch size for dataloaders.
        split_dates: SplitDates instance with all date boundaries.
        cluster_id: Optional cluster ID to filter symbols.
        clusters_parquet: Path to cluster assignments parquet.
    """

    def __init__(
        self,
        parquet_path: str = "data/features.parquet",
        seq_len: int = 30,
        batch_size: int = 64,
        *,
        split_dates: "SplitDates | None" = None,
        cluster_id: str | None = None,
        clusters_parquet: str = "data/clusters.parquet",
    ) -> None:
        super().__init__()
        from src.config import SplitDates

        if split_dates is None:
            split_dates = SplitDates(
                start_date=dt.date(2016, 4, 1),
                train_end=dt.date(2022, 10, 1),
                val_start=dt.date(2023, 1, 1),
                val_end=dt.date(2023, 12, 1),
                test_start=dt.date(2024, 4, 1),
                today=dt.date.today(),
            )

        self.parquet_path = parquet_path
        self.seq_len = seq_len
        self.batch_size = batch_size
        self.split_dates = split_dates
        self.cluster_id = cluster_id
        self.clusters_parquet = clusters_parquet

        self.feature_cols: list[str] = []
        self.class_weights: list[float] | None = None
        self.train_ds: TimeSeriesDataset | None = None
        self.val_ds: TimeSeriesDataset | None = None
        self.test_ds: TimeSeriesDataset | None = None

    def setup(self, stage: str | None = None) -> None:
        """Load data, normalize, and create date-based temporal splits per symbol."""
        df = pl.read_parquet(self.parquet_path)
        df = df.sort(["symbol", "date"])

        # Filter to cluster symbols if specified
        if self.cluster_id is not None:
            clusters_df = pl.read_parquet(self.clusters_parquet)
            cluster_symbols = (
                clusters_df.filter(pl.col("cluster_id") == self.cluster_id)["symbol"]
                .to_list()
            )
            df = df.filter(pl.col("symbol").is_in(cluster_symbols))
            if df.is_empty():
                raise ValueError(f"No data found for cluster {self.cluster_id}")
            print(f"  Filtered to cluster {self.cluster_id}: {len(cluster_symbols)} symbols")

        sd = self.split_dates
        self.feature_cols = [c for c in df.columns if c not in EXCLUDE_COLS]

        all_train_x, all_train_y = [], []
        all_val_x, all_val_y = [], []
        all_test_x, all_test_y = [], []
        train_valid, val_valid, test_valid = [], [], []
        train_offset, val_offset, test_offset = 0, 0, 0

        for symbol in df["symbol"].unique().sort().to_list():
            sym_df = df.filter(pl.col("symbol") == symbol)

            train_df = sym_df.filter(pl.col("date") < sd.train_end)
            val_df = sym_df.filter(
                (pl.col("date") >= sd.val_start) & (pl.col("date") < sd.val_end)
            )
            test_df = sym_df.filter(pl.col("date") >= sd.test_start)

            for split_df, x_list, y_list, valid_list, offset in [
                (train_df, all_train_x, all_train_y, train_valid, train_offset),
                (val_df, all_val_x, all_val_y, val_valid, val_offset),
                (test_df, all_test_x, all_test_y, test_valid, test_offset),
            ]:
                n = len(split_df)
                if n > 0:
                    x_list.append(split_df.select(self.feature_cols).to_numpy())
                    y_list.append(split_df["target"].to_numpy().astype(np.int64))
                    if n > self.seq_len:
                        valid_list.extend(range(offset, offset + n - self.seq_len))

            train_offset += len(train_df)
            val_offset += len(val_df)
            test_offset += len(test_df)

        train_x = np.concatenate(all_train_x)
        train_y = np.concatenate(all_train_y)
        val_x = np.concatenate(all_val_x)
        val_y = np.concatenate(all_val_y)
        test_x = np.concatenate(all_test_x)
        test_y = np.concatenate(all_test_y)

        train_vi = np.array(train_valid, dtype=np.int64)
        val_vi = np.array(val_valid, dtype=np.int64)
        test_vi = np.array(test_valid, dtype=np.int64)

        print(
            f"  Split sizes — train: {len(train_y):,} | "
            f"val: {len(val_y):,} | test: {len(test_y):,}"
        )
        print(sd.summary())

        # Class balance report for ternary targets
        class_names = {0: "HOLD", 1: "BUY", 2: "SELL"}
        for name, y in [("train", train_y), ("val", val_y), ("test", test_y)]:
            counts = {cls_name: int((y == cls_idx).sum()) for cls_idx, cls_name in class_names.items()}
            total = len(y)
            parts = " | ".join(
                f"{cls_name}: {count:,} ({count/total:.1%})"
                for cls_name, count in counts.items()
            )
            print(f"  {name} class balance — {parts}")

        # Compute inverse-frequency class weights from training set
        unique, counts = np.unique(train_y, return_counts=True)
        total = counts.sum()
        weight_map = {int(cls): total / (len(unique) * cnt) for cls, cnt in zip(unique, counts)}
        self.class_weights = [weight_map.get(i, 1.0) for i in range(max(int(unique.max()) + 1, 3))]
        print(f"  class weights — " + " | ".join(
            f"{class_names.get(i, i)}: {w:.3f}" for i, w in enumerate(self.class_weights)
        ))

        # Replace Inf/NaN with 0 before normalization
        for arr in (train_x, val_x, test_x):
            np.nan_to_num(arr, copy=False, nan=0.0, posinf=0.0, neginf=0.0)

        # Normalize using training set statistics only
        self._mean = train_x.mean(axis=0)
        self._std = train_x.std(axis=0)
        self._std[self._std == 0] = 1.0
        train_x = (train_x - self._mean) / self._std
        val_x = (val_x - self._mean) / self._std
        test_x = (test_x - self._mean) / self._std

        self.train_ds = TimeSeriesDataset(train_x, train_y, self.seq_len, train_vi, target_dtype=torch.int64, is_train=True)
        self.val_ds = TimeSeriesDataset(val_x, val_y, self.seq_len, val_vi, target_dtype=torch.int64)
        self.test_ds = TimeSeriesDataset(test_x, test_y, self.seq_len, test_vi, target_dtype=torch.int64)

    @property
    def input_size(self) -> int:
        """Number of input features."""
        return len(self.feature_cols)

    def train_dataloader(self) -> DataLoader:
        assert self.train_ds is not None
        return DataLoader(
            self.train_ds,
            batch_size=self.batch_size,
            shuffle=True,
            num_workers=_NUM_WORKERS,
            persistent_workers=_NUM_WORKERS > 0,
        )

    def val_dataloader(self) -> DataLoader:
        assert self.val_ds is not None
        return DataLoader(
            self.val_ds,
            batch_size=self.batch_size,
            num_workers=_NUM_WORKERS,
            persistent_workers=_NUM_WORKERS > 0,
        )

    def test_dataloader(self) -> DataLoader:
        assert self.test_ds is not None
        return DataLoader(
            self.test_ds,
            batch_size=self.batch_size,
            num_workers=_NUM_WORKERS,
            persistent_workers=_NUM_WORKERS > 0,
        )
