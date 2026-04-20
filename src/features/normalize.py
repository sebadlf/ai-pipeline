"""Feature normalization step (post-selection, pre-training).

Computes normalization statistics from the training period and applies
percentile clipping + Z-score normalization to all features. Produces
a normalized parquet and a stats JSON that serve as the single source
of truth for both training and inference.

Usage:
    uv run python -m src.features.normalize
    uv run python -m src.features.normalize --config configs/default.yaml
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

from src.config import (
    compute_split_dates,
    get_features_parquet_path,
    get_normalization_stats_path,
    load_config,
)

# Columns that are metadata, not features
_EXCLUDE_COLS = {"id", "symbol", "date", "target", "adj_close"}


def _is_feature_col(col: str) -> bool:
    """Check if a column should be used as a model feature."""
    return col not in _EXCLUDE_COLS and not col.startswith("forward_return_")


def compute_normalization_stats(config: dict) -> dict:
    """Compute normalization statistics from the training period.

    Reads the selected features parquet, filters to the training period,
    and computes per-feature: mean, std, and percentile bounds for clipping.

    Args:
        config: Full config dict.

    Returns:
        Stats dictionary with per-feature statistics.
    """
    features_path = get_features_parquet_path(config)
    split_dates = compute_split_dates(config)
    norm_cfg = config.get("normalization", {})
    clip_pcts = norm_cfg.get("clip_percentiles", [1, 99])

    print(f"  Reading features from {features_path}")
    df = pl.read_parquet(features_path)

    # Filter to training period only for computing statistics
    train_df = df.filter(pl.col("date") < split_dates.train_end)
    feature_cols = [c for c in df.columns if _is_feature_col(c)]

    print(f"  Training period: up to {split_dates.train_end}")
    print(f"  Training samples: {len(train_df):,}")
    print(f"  Features: {len(feature_cols)}")

    # Compute statistics per feature
    train_matrix = train_df.select(feature_cols).to_numpy()
    np.nan_to_num(train_matrix, copy=False, nan=0.0, posinf=0.0, neginf=0.0)

    stats = {
        "computed_date": date.today().isoformat(),
        "train_end": split_dates.train_end.isoformat(),
        "n_samples": len(train_df),
        "n_features": len(feature_cols),
        "clip_percentiles": clip_pcts,
        "features": {},
    }

    for i, col in enumerate(feature_cols):
        col_data = train_matrix[:, i]
        p_low = float(np.percentile(col_data, clip_pcts[0]))
        p_high = float(np.percentile(col_data, clip_pcts[1]))
        # Compute mean/std on the CLIPPED distribution so Z-score does not
        # compress features into a tiny band when the raw distribution has
        # heavy tails. See BEC-36.
        clipped = np.clip(col_data, p_low, p_high)
        std = float(np.std(clipped))
        stats["features"][col] = {
            "mean": float(np.mean(clipped)),
            "std": std if std > 0 else 1.0,
            "p_low": p_low,
            "p_high": p_high,
        }

    return stats


def normalize_features(config: dict, stats: dict | None = None) -> pl.DataFrame:
    """Apply percentile clipping and Z-score normalization to features.

    Reads the selected features parquet, applies clipping and normalization
    using pre-computed statistics, and returns the normalized DataFrame.

    Args:
        config: Full config dict.
        stats: Pre-computed stats dict. If None, loads from stats JSON file.

    Returns:
        Normalized DataFrame with same schema as input.
    """
    if stats is None:
        stats = load_normalization_stats(config)

    features_path = get_features_parquet_path(config)
    df = pl.read_parquet(features_path)

    feature_stats = stats["features"]
    feature_cols = [c for c in df.columns if c in feature_stats]

    # Build clipping and normalization expressions
    exprs = []
    for col in feature_cols:
        s = feature_stats[col]
        exprs.append(
            pl.col(col)
            .fill_nan(0.0)
            .clip(s["p_low"], s["p_high"])
            .sub(s["mean"])
            .truediv(s["std"])
            .alias(col)
        )

    # Apply normalization only to feature columns, keep metadata as-is
    metadata_cols = [c for c in df.columns if c not in feature_stats]
    df_normalized = df.select([pl.col(c) for c in metadata_cols] + exprs)

    # Final safety: replace any remaining NaN/Inf
    for col in feature_cols:
        df_normalized = df_normalized.with_columns(pl.col(col).fill_nan(0.0).alias(col))

    return df_normalized


def load_normalization_stats(config: dict) -> dict:
    """Load normalization statistics from JSON file.

    Args:
        config: Full config dict.

    Returns:
        Stats dictionary.

    Raises:
        FileNotFoundError: If stats file doesn't exist.
    """
    stats_path = get_normalization_stats_path(config)
    if not Path(stats_path).exists():
        raise FileNotFoundError(f"{stats_path} not found. Run `make normalize` first.")
    with open(stats_path) as f:
        return json.load(f)


def apply_normalization_to_array(
    features: np.ndarray,
    feature_cols: list[str],
    stats: dict,
) -> np.ndarray:
    """Apply normalization to a numpy array using saved stats.

    Used by inference code (consolidate.py, runner.py) to normalize
    features consistently with training.

    Args:
        features: Array of shape (n_samples, n_features) or (seq_len, n_features).
        feature_cols: Feature column names matching the array columns.
        stats: Normalization stats dict from load_normalization_stats().

    Returns:
        Normalized array of same shape.
    """
    feature_stats = stats["features"]
    result = features.copy()
    np.nan_to_num(result, copy=False, nan=0.0, posinf=0.0, neginf=0.0)

    for i, col in enumerate(feature_cols):
        if col in feature_stats:
            s = feature_stats[col]
            result[:, i] = np.clip(result[:, i], s["p_low"], s["p_high"])
            result[:, i] = (result[:, i] - s["mean"]) / s["std"]

    np.nan_to_num(result, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
    return result


def check_staleness(stats: dict, max_age_days: int = 90) -> bool:
    """Check if normalization stats are stale.

    Args:
        stats: Normalization stats dict.
        max_age_days: Maximum acceptable age in days.

    Returns:
        True if stats are stale (older than max_age_days), False otherwise.
    """
    computed_str = stats.get("computed_date")
    if not computed_str:
        print("  WARNING: normalization stats missing computed_date — cannot check staleness")
        return True

    computed_date = date.fromisoformat(computed_str)
    age_days = (date.today() - computed_date).days

    if age_days > max_age_days:
        print(
            f"  WARNING: normalization stats are {age_days} days old "
            f"(computed {computed_str}, max allowed {max_age_days} days). "
            f"Run `make normalize` to refresh."
        )
        return True
    return False


def main() -> None:
    """Run feature normalization pipeline."""
    parser = argparse.ArgumentParser(description="Normalize features")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    args = parser.parse_args()

    config = load_config(args.config)
    norm_cfg = config.get("normalization", {})
    stats_path = norm_cfg.get("output_stats", "data/normalization_stats.json")
    output_path = norm_cfg.get("output_parquet", "data/features_normalized.parquet")

    print("Computing normalization statistics...")
    stats = compute_normalization_stats(config)

    # Save stats
    Path(stats_path).parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"  Saved stats to {stats_path}")

    # Print summary of extreme features
    feature_stats = stats["features"]
    print("\n  Feature scale summary (top 10 by raw std):")
    sorted_features = sorted(feature_stats.items(), key=lambda x: x[1]["std"], reverse=True)
    for col, s in sorted_features[:10]:
        print(
            f"    {col:>35}: mean={s['mean']:>10.4f}  std={s['std']:>10.4f}  "
            f"clip=[{s['p_low']:.4f}, {s['p_high']:.4f}]"
        )

    print("\nNormalizing features...")
    df_normalized = normalize_features(config, stats)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df_normalized.write_parquet(output_path)
    print(f"  Saved normalized features to {output_path} ({len(df_normalized):,} rows)")


if __name__ == "__main__":
    main()
