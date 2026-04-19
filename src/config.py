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
        config = yaml.safe_load(f)
    validate_config(config)
    return config


def validate_config(config: dict) -> None:
    """Validate config values for correctness and coherence."""
    errors: list[str] = []

    # Target
    target = config.get("target", {})
    if target.get("horizon", 1) <= 0:
        errors.append("target.horizon must be positive")
    if target.get("buy_threshold", 0.025) <= 0:
        errors.append("target.buy_threshold must be positive")

    # Model
    model = config.get("model", {})
    if model.get("hidden_size", 1) <= 0:
        errors.append("model.hidden_size must be positive")
    if model.get("num_layers", 1) <= 0:
        errors.append("model.num_layers must be positive")
    dropout = model.get("dropout", 0.0)
    if not (0.0 <= dropout < 1.0):
        errors.append("model.dropout must be in [0, 1)")

    # Training
    train = config.get("training", {})
    if train.get("purge_days", 1) <= 0:
        errors.append("training.purge_days must be positive")

    # Clustering
    clustering = config.get("clustering", {})
    min_k = clustering.get("min_clusters", 3)
    max_k = clustering.get("max_clusters", 10)
    if min_k > max_k:
        errors.append(f"clustering.min_clusters ({min_k}) must be <= max_clusters ({max_k})")

    # Regime
    regime = config.get("regime", {})
    if regime.get("sma_short", 50) >= regime.get("sma_long", 200):
        errors.append("regime.sma_short must be < regime.sma_long")
    if regime.get("bear_threshold", -0.10) >= 0:
        errors.append("regime.bear_threshold must be negative")
    if regime.get("bull_threshold", 0.10) <= 0:
        errors.append("regime.bull_threshold must be positive")

    # Portfolio constraints
    constraints = config.get("portfolio", {}).get("constraints", {})
    max_pos = constraints.get("max_single_position", 0.10)
    if not (0.0 < max_pos <= 1.0):
        errors.append("portfolio.constraints.max_single_position must be in (0, 1]")

    # Feature selection
    fs = config.get("feature_selection", {})
    if fs.get("enabled", False):
        if not (0.0 < fs.get("max_null_pct", 0.90) <= 1.0):
            errors.append("feature_selection.max_null_pct must be in (0, 1]")
        if not (0.0 < fs.get("max_correlation", 0.95) <= 1.0):
            errors.append("feature_selection.max_correlation must be in (0, 1]")

    if errors:
        raise ValueError("Config validation failed:\n  " + "\n  ".join(errors))


def resolve_env_value(value: int | float | dict, default: int | float = 0) -> int | float:
    """Resolve a config value that may be a scalar or a dict with dev/prod keys."""
    if isinstance(value, (int, float)):
        return value
    from src.keys import PIPELINE_ENV

    return value.get(PIPELINE_ENV, value.get("dev", default))


def resolve_start_years_back(config: dict) -> int:
    """Resolve start_years_back based on PIPELINE_ENV.

    Supports both int (legacy) and dict with dev/prod keys.
    """
    return int(resolve_env_value(config["ingestion"]["start_years_back"], default=5))


@dataclass
class SplitDates:
    """Date boundaries for temporal train/val/test splits with purge gaps.

    Timeline:
        start_date ... train_end | PURGE | val_start ... val_end | PURGE | test_start ... today
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


def compute_cv_fold_splits(
    split_dates: SplitDates,
    n_folds: int = 3,
    purge_days: int = 21,
) -> list[SplitDates]:
    """Compute expanding-window time-series CV fold boundaries.

    Divides the training period [start_date, train_end] into n_folds segments.
    Each fold uses an expanding training window and validates on the next segment.
    The last fold matches the original split (train up to train_end, val = original val).

    Args:
        split_dates: Original SplitDates with full train/val/test boundaries.
        n_folds: Number of CV folds (default 3).
        purge_days: Gap between train and val in each fold to prevent label leakage.

    Returns:
        List of SplitDates, one per fold.
    """
    sd = split_dates
    total_train_days = (sd.train_end - sd.start_date).days
    segment_days = total_train_days // n_folds

    folds = []
    for i in range(n_folds):
        if i < n_folds - 1:
            # Intermediate folds: train up to T_i, validate on [T_i+purge, T_{i+1}]
            fold_train_end = sd.start_date + dt.timedelta(days=(i + 1) * segment_days)
            fold_val_start = fold_train_end + dt.timedelta(days=purge_days)
            fold_val_end = sd.start_date + dt.timedelta(days=(i + 2) * segment_days)
            # Ensure val_end doesn't exceed original train_end
            if fold_val_end > sd.train_end:
                fold_val_end = sd.train_end
        else:
            # Last fold: matches the original split exactly
            fold_train_end = sd.train_end
            fold_val_start = sd.val_start
            fold_val_end = sd.val_end

        folds.append(
            SplitDates(
                start_date=sd.start_date,
                train_end=fold_train_end,
                val_start=fold_val_start,
                val_end=fold_val_end,
                test_start=sd.test_start,
                today=sd.today,
            )
        )

    return folds


# --- New config dataclasses for 5-stage pipeline ---


@dataclass
class ClusterConfig:
    """Configuration for stock clustering (Stage 1)."""

    method: str = "kmeans"
    max_clusters: int = 10
    min_clusters: int = 3
    include_sector_features: bool = True
    pca_variance_ratio: float = 0.95
    features_for_clustering: list[str] = field(
        default_factory=lambda: [
            "return_20d_mean",
            "volatility_60d",
            "volume_profile",
            "rsi_14_mean",
            "beta_60d",
            "momentum_60d",
            "drawdown_max",
            "relative_to_sector_avg",
            "vix_beta",
            "yield_sensitivity",
            "km_returnonequity",
            "km_earningsyield",
            "km_freecashflowyield",
            "km_evtoebitda",
            "fr_grossprofitmargin",
            "fr_netprofitmargin",
            "fr_debttoequityratio",
            "fr_pricetoearningsratio",
            "fr_pricetobookratio",
            "fr_dividendyield",
        ]
    )
    min_cluster_size: int = 10
    output_parquet: str = "data/clusters.parquet"
    cluster_thresholds: dict[str, dict[str, float]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> ClusterConfig:
        """Create from config dict section."""
        return cls(
            method=d.get("method", "kmeans"),
            max_clusters=d.get("max_clusters", 10),
            min_clusters=d.get("min_clusters", 3),
            include_sector_features=d.get("include_sector_features", True),
            pca_variance_ratio=d.get("pca_variance_ratio", 0.95),
            features_for_clustering=d.get(
                "features_for_clustering",
                cls.__dataclass_fields__["features_for_clustering"].default_factory(),
            ),
            min_cluster_size=d.get("min_cluster_size", 10),
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


@dataclass
class PromotionEvalConfig:
    """Configuration for precision-based model evaluation and promotion."""

    thresholds: list[float] = field(
        default_factory=lambda: [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
    )
    primary_threshold: float = 0.65
    min_recall: float = 0.10
    min_signals_per_window: int = 5
    max_val_test_gap: float = 0.20
    wf_window_size: int = 63
    wf_step_size: int = 21
    max_std_ratio: float = 0.15
    stability_penalty: float = 1.5
    tiebreak_margin: float = 0.01

    @classmethod
    def from_dict(cls, promotion_cfg: dict) -> PromotionEvalConfig:
        """Create from the full promotion config section."""
        eval_cfg = promotion_cfg.get("evaluation", {})
        wf_cfg = promotion_cfg.get("walk_forward", {})
        rank_cfg = promotion_cfg.get("ranking", {})
        return cls(
            thresholds=eval_cfg.get("thresholds", [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]),
            primary_threshold=eval_cfg.get("primary_threshold", 0.65),
            min_recall=eval_cfg.get("min_recall", 0.10),
            min_signals_per_window=eval_cfg.get("min_signals_per_window", 5),
            max_val_test_gap=eval_cfg.get("max_val_test_gap", 0.20),
            wf_window_size=wf_cfg.get("window_size", 63),
            wf_step_size=wf_cfg.get("step_size", 21),
            max_std_ratio=wf_cfg.get("max_std_ratio", 0.15),
            stability_penalty=wf_cfg.get("stability_penalty", 1.5),
            tiebreak_margin=rank_cfg.get("tiebreak_margin", 0.01),
        )


def get_features_parquet_path(config: dict) -> str:
    """Resolve the features parquet path based on feature selection config.

    Returns features_selected.parquet when feature selection is enabled.
    Raises FileNotFoundError if enabled but file missing.
    """
    sel_cfg = config.get("feature_selection", {})
    if sel_cfg.get("enabled", False):
        selected_path = "data/features_selected.parquet"
        if Path(selected_path).exists():
            return selected_path
        raise FileNotFoundError(f"{selected_path} not found. Run `make select-features` first.")
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


def get_normalized_parquet_path(config: dict) -> str:
    """Resolve the normalized features parquet path.

    Returns features_normalized.parquet when normalization config exists.
    Raises FileNotFoundError if normalization hasn't been run.
    """
    norm_cfg = config.get("normalization", {})
    norm_path = norm_cfg.get("output_parquet", "data/features_normalized.parquet")
    if Path(norm_path).exists():
        return norm_path
    raise FileNotFoundError(f"{norm_path} not found. Run `make normalize` first.")


def get_normalization_stats_path(config: dict) -> str:
    """Resolve the normalization statistics JSON path."""
    norm_cfg = config.get("normalization", {})
    return norm_cfg.get("output_stats", "data/normalization_stats.json")


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
