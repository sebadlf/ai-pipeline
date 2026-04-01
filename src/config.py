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


def resolve_start_years_back(config: dict) -> int:
    """Resolve start_years_back based on PIPELINE_ENV.

    Supports both int (legacy) and dict with dev/prod keys.
    """
    from src.keys import PIPELINE_ENV

    value = config["ingestion"]["start_years_back"]
    if isinstance(value, int):
        return value
    return value.get(PIPELINE_ENV, value.get("dev", 5))


def resolve_dev_sectors(config: dict) -> list[str] | None:
    """Return the sector filter list for dev mode, or None for prod (all sectors)."""
    from src.keys import PIPELINE_ENV

    if PIPELINE_ENV != "dev":
        return None
    return config.get("ingestion", {}).get("dev_sectors")


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

    start_years_back = resolve_start_years_back(config)
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
    max_clusters_per_sector: int = 6
    pca_variance_ratio: float = 0.95
    features_for_clustering: list[str] = field(
        default_factory=lambda: [
            "return_20d_mean", "volatility_60d", "volume_profile",
            "rsi_14_mean", "beta_60d", "momentum_60d", "drawdown_max",
            "relative_to_sector_avg", "vix_beta", "yield_sensitivity",
            "km_returnonequity", "km_earningsyield", "km_freecashflowyield",
            "km_evtoebitda", "fr_grossprofitmargin", "fr_netprofitmargin",
            "fr_debttoequityratio", "fr_pricetoearningsratio",
            "fr_pricetobookratio", "fr_dividendyield",
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
            max_clusters_per_sector=d.get("max_clusters_per_sector", 6),
            pca_variance_ratio=d.get("pca_variance_ratio", 0.95),
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
    min_prob_up: float = 0.70

    @classmethod
    def from_dict(cls, d: dict) -> PortfolioProfileConfig:
        """Create from config dict section."""
        return cls(
            primary_metric=d["primary_metric"],
            complementary_metric=d["complementary_metric"],
            validation_metric=d["validation_metric"],
            max_positions=d.get("max_positions", 20),
            max_sector_weight=d.get("max_sector_weight", 0.25),
            min_prob_up=d.get("min_prob_up", 0.70),
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


def get_features_parquet_path(config: dict) -> str:
    """Resolve the features parquet path based on feature selection config.

    Returns features_selected.parquet when feature selection is enabled,
    otherwise falls back to features.parquet.
    """
    sel_cfg = config.get("feature_selection", {})
    if sel_cfg.get("enabled", False):
        selected_path = "data/features_selected.parquet"
        if Path(selected_path).exists():
            return selected_path
    return "data/features.parquet"


def get_selected_feature_names(config: dict) -> list[str] | None:
    """Load the selected feature names from the manifest when available.

    Returns None if feature selection is disabled or manifest not found.
    """
    import json

    sel_cfg = config.get("feature_selection", {})
    if not sel_cfg.get("enabled", False):
        return None

    manifest_path = Path("data/selected_features.json")
    if manifest_path.exists():
        with open(manifest_path) as f:
            data = json.load(f)
        return data.get("features")
    return None


def get_cluster_buy_threshold(config: dict, cluster_id: str) -> float:
    """Resolve buy_threshold for a cluster, falling back to default.

    Args:
        config: Full config dict.
        cluster_id: Cluster identifier (e.g. "Technology_0").

    Returns:
        The buy_threshold for this cluster.
    """
    target_cfg = config.get("target", {})
    default_buy = target_cfg.get("buy_threshold", 0.025)

    cluster_cfg = config.get("clustering", {})
    overrides = cluster_cfg.get("cluster_thresholds", {})
    if cluster_id in overrides:
        return overrides[cluster_id].get("buy_threshold", default_buy)

    return default_buy
