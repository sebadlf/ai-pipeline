"""Shared configuration utilities."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.keys import POSTGRES_DB, POSTGRES_HOST, POSTGRES_PASSWORD, POSTGRES_PORT, POSTGRES_USER

PROJECT_ROOT = Path(__file__).parent.parent


def get_db_url() -> str:
    """Build PostgreSQL connection URL from environment variables."""
    return f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"


def load_config(path: str | None = None) -> dict:
    """Load YAML config file.

    Args:
        path: Path to config file. Defaults to configs/default.yaml.
    """
    if path is None:
        path = str(PROJECT_ROOT / "configs" / "default.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


@dataclass
class SplitDates:
    """Date boundaries for temporal train/val/test splits with purge gaps.

    Timeline: start_date ... train_end | PURGE | val_start ... val_end | PURGE | test_start ... today
    """

    start_date: dt.date
    train_end: dt.date
    val_start: dt.date
    val_end: dt.date
    test_start: dt.date
    today: dt.date

    def summary(self) -> str:
        purge1 = (self.val_start - self.train_end).days
        purge2 = (self.test_start - self.val_end).days
        return (
            f"  train:  {self.start_date} to {self.train_end}\n"
            f"  purge1: {self.train_end} to {self.val_start} ({purge1} days)\n"
            f"  val:    {self.val_start} to {self.val_end}\n"
            f"  purge2: {self.val_end} to {self.test_start} ({purge2} days)\n"
            f"  test:   {self.test_start} to {self.today}"
        )


def compute_split_dates(config: dict, reference_date: dt.date | None = None) -> SplitDates:
    """Compute date-based split boundaries relative to a reference date.

    Args:
        config: Full config dict with ingestion.start_years_back and
                training.test_years, val_years, purge_days.
        reference_date: Date to compute from. Defaults to today.
    """
    today = reference_date or dt.date.today()

    start_years_back = config["ingestion"]["start_years_back"]
    train_cfg = config["training"]
    test_years = train_cfg["test_years"]
    val_years = train_cfg["val_years"]
    purge_days = train_cfg["purge_days"]

    start_date = today.replace(year=today.year - start_years_back)
    test_start = today.replace(year=today.year - test_years)
    val_end = test_start - dt.timedelta(days=purge_days)
    val_start = val_end.replace(year=val_end.year - val_years)
    train_end = val_start - dt.timedelta(days=purge_days)

    return SplitDates(
        start_date=start_date,
        train_end=train_end,
        val_start=val_start,
        val_end=val_end,
        test_start=test_start,
        today=today,
    )
