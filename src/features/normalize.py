"""Feature normalization step (post-selection, pre-training).

Computes normalization statistics from the training period and applies
percentile clipping + Z-score normalization to all features. Produces
a normalized parquet and a stats JSON that serve as the single source
of truth for both training and inference.

For features with near-degenerate distributions where clipping collapses
the kept-mass band to a razor-thin range (e.g., ~50 fundamental ratios
that collapse to a constant after [p01, p99] clipping), a rank /
quantile-normal transform is used as a fallback so the LSTM sees unit
variance on those features too. See BEC-41.

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
from scipy.stats import norm

from src.config import (
    compute_split_dates,
    get_features_parquet_path,
    get_normalization_stats_path,
    load_config,
)

# Columns that are metadata, not features
_EXCLUDE_COLS = {"id", "symbol", "date", "target", "adj_close"}

# Default parameters for the rank-transform fallback.
# `degenerate_range_ratio` is the minimum acceptable ratio of
# (clipping range) / (raw absolute scale); below this we consider the
# feature too degenerate for linear z-score and fall back to quantile-
# normal transform. 0.01 means the kept-mass band must span at least 1%
# of the raw series' magnitude.
_DEFAULT_DEGENERATE_RANGE_RATIO = 0.01
_DEFAULT_QUANTILE_KNOTS = 256


def _is_feature_col(col: str) -> bool:
    """Check if a column should be used as a model feature."""
    return col not in _EXCLUDE_COLS and not col.startswith("forward_return_")


def _fit_quantile_knots(values: np.ndarray, n_knots: int) -> list[float]:
    """Fit quantile knots for a rank-normal transform.

    Mimics ``sklearn.preprocessing.QuantileTransformer`` with
    ``output_distribution='normal'``: sorts training values and stores a
    uniform grid of quantiles that can later be used to map new values to
    their approximate uniform rank, followed by an inverse-normal CDF.

    Args:
        values: 1-D array of finite training values.
        n_knots: Number of quantile knots to store.

    Returns:
        List of ``n_knots`` sorted quantile points (floats), suitable for
        JSON serialization.
    """
    if values.size == 0:
        # Degenerate edge case; return neutral knots
        return [0.0] * n_knots
    probs = np.linspace(0.0, 1.0, n_knots)
    knots = np.quantile(values, probs)
    return [float(v) for v in knots]


def _apply_quantile_normal(values: np.ndarray, knots: list[float]) -> np.ndarray:
    """Apply a rank-normal transform given pre-fit quantile knots.

    Uses ``np.interp`` to map values to a uniform rank in [0, 1] via the
    training-set quantile knots, then applies the inverse normal CDF
    (``scipy.stats.norm.ppf``) to obtain an approximately N(0, 1) output.

    Args:
        values: Input array (any shape), NaN/Inf already replaced.
        knots: Fitted quantile knots from ``_fit_quantile_knots``.

    Returns:
        Array of the same shape with (approx) standard-normal distribution.
    """
    knots_arr = np.asarray(knots, dtype=np.float64)
    probs = np.linspace(0.0, 1.0, len(knots_arr))
    uniform = np.interp(values, knots_arr, probs)
    # Clip away the exact tails to avoid +/- inf from norm.ppf
    eps = 1.0 / (2.0 * max(len(knots_arr), 2))
    uniform = np.clip(uniform, eps, 1.0 - eps)
    return norm.ppf(uniform)


def compute_normalization_stats(config: dict) -> dict:
    """Compute normalization statistics from the training period.

    Reads the selected features parquet, filters to the training period,
    and computes per-feature statistics. For each feature we apply
    percentile clipping + z-score; if the clipped-range ratio to the raw
    absolute scale is below ``degenerate_range_ratio`` (default 0.01) or
    the clipped training distribution collapses to a single point, we
    flag it as degenerate and fit a quantile-normal transform instead.

    Args:
        config: Full config dict.

    Returns:
        Stats dictionary with per-feature statistics, including the
        transform type (``"zscore"`` or ``"quantile"``) used for each
        feature.
    """
    features_path = get_features_parquet_path(config)
    split_dates = compute_split_dates(config)
    norm_cfg = config.get("normalization", {})
    clip_pcts = norm_cfg.get("clip_percentiles", [1, 99])
    degenerate_range_ratio = float(
        norm_cfg.get("degenerate_range_ratio", _DEFAULT_DEGENERATE_RANGE_RATIO)
    )
    quantile_knots = int(norm_cfg.get("quantile_knots", _DEFAULT_QUANTILE_KNOTS))

    print(f"  Reading features from {features_path}")
    df = pl.read_parquet(features_path)

    # Filter to training period only for computing statistics
    train_df = df.filter(pl.col("date") < split_dates.train_end)
    feature_cols = [c for c in df.columns if _is_feature_col(c)]

    print(f"  Training period: up to {split_dates.train_end}")
    print(f"  Training samples: {len(train_df):,}")
    print(f"  Features: {len(feature_cols)}")

    # Compute statistics per feature on the training window. For degeneracy
    # detection we compare the clipped-training std against the clipped
    # training RANGE (p_high - p_low) — if the spread after clipping is
    # effectively zero in absolute terms, z-score cannot produce unit
    # variance on the val/test windows either (and typically collapses to
    # std≈0, since clipping already pinned the mass to a single point).
    train_matrix = train_df.select(feature_cols).to_numpy()
    np.nan_to_num(train_matrix, copy=False, nan=0.0, posinf=0.0, neginf=0.0)

    stats = {
        "computed_date": date.today().isoformat(),
        "train_end": split_dates.train_end.isoformat(),
        "n_samples": len(train_df),
        "n_features": len(feature_cols),
        "clip_percentiles": clip_pcts,
        "degenerate_range_ratio": degenerate_range_ratio,
        "quantile_knots": quantile_knots,
        "features": {},
    }

    n_quantile = 0
    for i, col in enumerate(feature_cols):
        col_data = train_matrix[:, i]
        p_low = float(np.percentile(col_data, clip_pcts[0]))
        p_high = float(np.percentile(col_data, clip_pcts[1]))
        # Compute mean/std on the CLIPPED distribution so Z-score does not
        # compress features into a tiny band when the raw distribution has
        # heavy tails. See BEC-36.
        clipped_train = np.clip(col_data, p_low, p_high)
        mean = float(np.mean(clipped_train))
        std = float(np.std(clipped_train))

        # Degeneracy detection — a feature is degenerate when the clipped
        # distribution has effectively zero spread relative to its raw
        # scale. On such features z-score cannot deliver unit variance on
        # the val/test windows: clipping already pinned the mass to a
        # single point or a razor-thin band, so `(clipped - mean) / std`
        # collapses to ~0. See BEC-41.
        clip_range = p_high - p_low
        raw_scale = float(max(np.abs(col_data).max(), 1.0))
        unique_clipped = int(np.unique(clipped_train).size)
        # Relative clip range: how wide the kept-mass band is compared to
        # the overall magnitude of the raw series. Small ratio => clipping
        # saturated almost everything.
        relative_clip_range = clip_range / raw_scale
        is_degenerate = (
            std <= 0.0 or unique_clipped <= 1 or relative_clip_range < degenerate_range_ratio
        )

        if is_degenerate:
            # Fallback: rank / quantile-normal transform.
            # Fit the knots on RAW (unclipped) training values — clipping to
            # [p_low, p_high] on a degenerate distribution already collapses
            # the bulk to a constant, which would leave the quantile
            # transform with no information to recover. The transform is
            # robust to outliers by construction, so clipping is not needed.
            knots = _fit_quantile_knots(col_data, quantile_knots)
            stats["features"][col] = {
                "transform": "quantile",
                "mean": mean,
                "std": std if std > 0 else 1.0,
                "p_low": p_low,
                "p_high": p_high,
                "quantiles": knots,
                "clip_range": clip_range,
                "unique_clipped": unique_clipped,
            }
            n_quantile += 1
        else:
            stats["features"][col] = {
                "transform": "zscore",
                "mean": mean,
                "std": std if std > 0 else 1.0,
                "p_low": p_low,
                "p_high": p_high,
            }

    stats["n_zscore"] = len(feature_cols) - n_quantile
    stats["n_quantile"] = n_quantile
    print(
        f"  Transforms: {stats['n_zscore']} z-score, "
        f"{stats['n_quantile']} quantile-normal (degenerate features)"
    )

    return stats


def normalize_features(config: dict, stats: dict | None = None) -> pl.DataFrame:
    """Apply percentile clipping and normalization to features.

    Reads the selected features parquet, applies clipping and the
    per-feature transform (``zscore`` or ``quantile``) using pre-computed
    statistics, and returns the normalized DataFrame.

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

    # Split features by transform type so we can handle them in bulk
    zscore_cols = [
        c for c in feature_cols if feature_stats[c].get("transform", "zscore") == "zscore"
    ]
    quantile_cols = [c for c in feature_cols if feature_stats[c].get("transform") == "quantile"]

    # Z-score path — vectorized Polars expressions
    zscore_exprs = []
    for col in zscore_cols:
        s = feature_stats[col]
        zscore_exprs.append(
            pl.col(col)
            .fill_nan(0.0)
            .clip(s["p_low"], s["p_high"])
            .sub(s["mean"])
            .truediv(s["std"])
            .alias(col)
        )

    # Quantile-normal path — per-feature numpy transform. There are typically
    # only a few dozen degenerate features so this is not a bottleneck.
    # Note: we intentionally do NOT clip before the quantile transform —
    # clipping collapses the bulk of a degenerate distribution (which is
    # why z-score fails in the first place), and the quantile-normal
    # transform is already robust to outliers by construction.
    quantile_series: dict[str, np.ndarray] = {}
    for col in quantile_cols:
        s = feature_stats[col]
        raw = df.get_column(col).to_numpy().astype(np.float64, copy=True)
        np.nan_to_num(raw, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
        quantile_series[col] = _apply_quantile_normal(raw, s["quantiles"])

    metadata_cols = [c for c in df.columns if c not in feature_stats]
    df_normalized = df.select([pl.col(c) for c in metadata_cols] + zscore_exprs)

    for col, arr in quantile_series.items():
        df_normalized = df_normalized.with_columns(pl.Series(name=col, values=arr))

    # Reorder columns to match original DataFrame layout
    df_normalized = df_normalized.select(df.columns)

    # Final safety: replace any remaining NaN/Inf on feature columns
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
    features consistently with training. Dispatches per-feature based on
    the transform type recorded at fit time.

    Args:
        features: Array of shape (n_samples, n_features) or (seq_len, n_features).
        feature_cols: Feature column names matching the array columns.
        stats: Normalization stats dict from load_normalization_stats().

    Returns:
        Normalized array of same shape.
    """
    feature_stats = stats["features"]
    result = features.astype(np.float64, copy=True)
    np.nan_to_num(result, copy=False, nan=0.0, posinf=0.0, neginf=0.0)

    for i, col in enumerate(feature_cols):
        s = feature_stats.get(col)
        if s is None:
            continue
        transform = s.get("transform", "zscore")
        if transform == "quantile" and "quantiles" in s:
            # Quantile-normal transform applied directly on raw values.
            # Clipping is intentionally skipped: the transform is already
            # robust to outliers, and clipping would collapse the bulk of
            # the distribution (the exact reason z-score fails on these
            # features in the first place). See BEC-41.
            result[:, i] = _apply_quantile_normal(result[:, i], s["quantiles"])
        else:
            clipped = np.clip(result[:, i], s["p_low"], s["p_high"])
            result[:, i] = (clipped - s["mean"]) / s["std"]

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
            f"clip=[{s['p_low']:.4f}, {s['p_high']:.4f}]  transform={s.get('transform', 'zscore')}"
        )

    # List features that fell back to quantile-normal transform
    degenerate_features = [
        (col, s) for col, s in feature_stats.items() if s.get("transform") == "quantile"
    ]
    if degenerate_features:
        print(
            f"\n  Degenerate features using quantile-normal transform ({len(degenerate_features)}):"
        )
        for col, s in degenerate_features[:20]:
            print(
                f"    {col:>35}: std={s['std']:.6f}  "
                f"clip=[{s['p_low']:.4f}, {s['p_high']:.4f}]  "
                f"unique_clipped={s.get('unique_clipped', 'n/a')}"
            )
        if len(degenerate_features) > 20:
            print(f"    ... and {len(degenerate_features) - 20} more")

    print("\nNormalizing features...")
    df_normalized = normalize_features(config, stats)

    # Stock-preservation audit (BEC-44): normalization is a row-wise
    # transform and must not drop any symbol that reached this stage.
    from src.features.stock_audit import audit_symbols

    input_symbols = set(
        pl.read_parquet(get_features_parquet_path(config))["symbol"].unique().to_list()
    )
    output_symbols = set(df_normalized["symbol"].unique().to_list())
    audit_symbols("normalize", input_symbols, output_symbols)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df_normalized.write_parquet(output_path)
    print(f"  Saved normalized features to {output_path} ({len(df_normalized):,} rows)")


if __name__ == "__main__":
    main()
