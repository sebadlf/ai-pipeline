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
    """Sliding window dataset over feature matrix.

    Args:
        features: Feature array of shape (timesteps, n_features).
        targets: Target array of shape (timesteps,).
        seq_len: Number of timesteps per sample.
    """

    def __init__(self, features: np.ndarray, targets: np.ndarray, seq_len: int) -> None:
        self.features = torch.tensor(features, dtype=torch.float32)
        self.targets = torch.tensor(targets, dtype=torch.float32)
        self.seq_len = seq_len

    def __len__(self) -> int:
        return len(self.features) - self.seq_len

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        x = self.features[idx : idx + self.seq_len]
        y = self.targets[idx + self.seq_len]
        return x, y


class TradingDataModule(L.LightningDataModule):
    """DataModule for loading and splitting trading feature data.

    Uses date-based temporal splits with purge gaps:
    train [start..train_end] | PURGE | val [val_start..val_end] | PURGE | test [test_start..]

    Args:
        parquet_path: Path to features parquet file.
        seq_len: Sequence length for sliding window.
        batch_size: Batch size for dataloaders.
        split_dates: SplitDates instance with all date boundaries.
    """

    def __init__(
        self,
        parquet_path: str = "data/features.parquet",
        seq_len: int = 30,
        batch_size: int = 64,
        *,
        split_dates: "SplitDates | None" = None,
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

        self.feature_cols: list[str] = []
        self.train_ds: TimeSeriesDataset | None = None
        self.val_ds: TimeSeriesDataset | None = None
        self.test_ds: TimeSeriesDataset | None = None

    def setup(self, stage: str | None = None) -> None:
        """Load data, normalize, and create date-based temporal splits per symbol."""
        df = pl.read_parquet(self.parquet_path)
        df = df.sort(["symbol", "date"])

        sd = self.split_dates
        self.feature_cols = [c for c in df.columns if c not in EXCLUDE_COLS]

        all_train_x, all_train_y = [], []
        all_val_x, all_val_y = [], []
        all_test_x, all_test_y = [], []

        for symbol in df["symbol"].unique().sort().to_list():
            sym_df = df.filter(pl.col("symbol") == symbol)

            train_df = sym_df.filter(pl.col("date") < sd.train_end)
            val_df = sym_df.filter(
                (pl.col("date") >= sd.val_start) & (pl.col("date") < sd.val_end)
            )
            test_df = sym_df.filter(pl.col("date") >= sd.test_start)

            for split_df, x_list, y_list in [
                (train_df, all_train_x, all_train_y),
                (val_df, all_val_x, all_val_y),
                (test_df, all_test_x, all_test_y),
            ]:
                if len(split_df) > 0:
                    x_list.append(split_df.select(self.feature_cols).to_numpy())
                    y_list.append(split_df["target"].to_numpy())

        train_x = np.concatenate(all_train_x)
        train_y = np.concatenate(all_train_y)
        val_x = np.concatenate(all_val_x)
        val_y = np.concatenate(all_val_y)
        test_x = np.concatenate(all_test_x)
        test_y = np.concatenate(all_test_y)

        print(
            f"  Split sizes — train: {len(train_y):,} | "
            f"val: {len(val_y):,} | test: {len(test_y):,}"
        )
        print(sd.summary())
        for name, y in [("train", train_y), ("val", val_y), ("test", test_y)]:
            pos = (y == 1).sum()
            print(f"  {name} class balance — pos: {pos:,} ({pos/len(y):.1%}) | neg: {len(y)-pos:,} ({1-pos/len(y):.1%})")

        # Normalize using training set statistics only
        self._mean = train_x.mean(axis=0)
        self._std = train_x.std(axis=0)
        self._std[self._std == 0] = 1.0
        train_x = (train_x - self._mean) / self._std
        val_x = (val_x - self._mean) / self._std
        test_x = (test_x - self._mean) / self._std

        self.train_ds = TimeSeriesDataset(train_x, train_y, self.seq_len)
        self.val_ds = TimeSeriesDataset(val_x, val_y, self.seq_len)
        self.test_ds = TimeSeriesDataset(test_x, test_y, self.seq_len)

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
