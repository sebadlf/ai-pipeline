"""Shared configuration utilities."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
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


# --- New config dataclasses for 5-stage pipeline ---


@dataclass
class ClusterConfig:
    """Configuration for stock clustering (Stage 1)."""

    method: str = "kmeans"
    n_clusters_per_sector: int = 3
    features_for_clustering: list[str] = field(
        default_factory=lambda: [
            "return_20d_mean",
            "volatility_60d",
            "volume_profile",
            "rsi_14_mean",
            "beta_60d",
        ]
    )
    min_cluster_size: int = 3
    output_parquet: str = "data/clusters.parquet"
    cluster_thresholds: dict[str, dict[str, float]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> ClusterConfig:
        """Create from config dict section."""
        return cls(
            method=d.get("method", "kmeans"),
            n_clusters_per_sector=d.get("n_clusters_per_sector", 3),
            features_for_clustering=d.get(
                "features_for_clustering",
                cls.__dataclass_fields__["features_for_clustering"].default_factory(),
            ),
            min_cluster_size=d.get("min_cluster_size", 3),
            output_parquet=d.get("output_parquet", "data/clusters.parquet"),
            cluster_thresholds=d.get("cluster_thresholds", {}),
        )


@dataclass
class PortfolioProfileConfig:
    """Configuration for a single portfolio profile."""

    primary_metric: str
    complementary_metric: str
    validation_metric: str
    max_positions: int = 20
    max_sector_weight: float = 0.25
    min_confidence: float = 0.55
    allow_short: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> PortfolioProfileConfig:
        """Create from config dict section."""
        return cls(
            primary_metric=d["primary_metric"],
            complementary_metric=d["complementary_metric"],
            validation_metric=d["validation_metric"],
            max_positions=d.get("max_positions", 20),
            max_sector_weight=d.get("max_sector_weight", 0.25),
            min_confidence=d.get("min_confidence", 0.55),
            allow_short=d.get("allow_short", False),
        )


@dataclass
class RegimeConfig:
    """Configuration for market regime detection."""

    benchmark: str = "SPY"
    lookback_days: int = 126
    bull_threshold: float = 0.10
    bear_threshold: float = -0.10
    sma_short: int = 50
    sma_long: int = 200

    @classmethod
    def from_dict(cls, d: dict) -> RegimeConfig:
        """Create from config dict section."""
        return cls(
            benchmark=d.get("benchmark", "SPY"),
            lookback_days=d.get("lookback_days", 126),
            bull_threshold=d.get("bull_threshold", 0.10),
            bear_threshold=d.get("bear_threshold", -0.10),
            sma_short=d.get("sma_short", 50),
            sma_long=d.get("sma_long", 200),
        )


def get_cluster_thresholds(
    config: dict, cluster_id: str
) -> tuple[float, float]:
    """Resolve buy/sell thresholds for a cluster, falling back to defaults.

    Args:
        config: Full config dict.
        cluster_id: Cluster identifier (e.g. "Technology_0").

    Returns:
        Tuple of (buy_threshold, sell_threshold).
    """
    target_cfg = config.get("target", {})
    default_buy = target_cfg.get("buy_threshold", 0.05)
    default_sell = target_cfg.get("sell_threshold", 0.03)

    cluster_cfg = config.get("clustering", {})
    overrides = cluster_cfg.get("cluster_thresholds", {})
    if cluster_id in overrides:
        ct = overrides[cluster_id]
        return ct.get("buy_threshold", default_buy), ct.get("sell_threshold", default_sell)

    return default_buy, default_sell
