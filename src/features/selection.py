"""Feature selection and dimensionality reduction.

Filters features by null rate, variance, and correlation to reduce
the feature space before model training.

Usage:
    uv run python -m src.features.selection
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import numpy as np
import polars as pl

from src.config import load_config
from src.models.dataset import _is_feature_col


def select_features(
    df: pl.DataFrame,
    config: dict,
    *,
    train_end: dt.date | None = None,
    verbose: bool = True,
) -> tuple[pl.DataFrame, list[str]]:
    """Apply feature selection filters and return filtered DataFrame + selected column names.

    Args:
        df: Full features DataFrame (including symbol, date, target).
        config: Full config dict with feature_selection section.
        train_end: If provided, compute statistics only on data before this date
            to prevent leaking val/test information into feature selection.
        verbose: Print summary of each filter step.
    """
    sel_cfg = config.get("feature_selection", {})
    max_null_pct = sel_cfg.get("max_null_pct", 0.90)
    max_correlation = sel_cfg.get("max_correlation", 0.95)
    min_variance_pct = sel_cfg.get("min_variance_pct", 0.01)

    # Use only training data for computing statistics (avoid leaking val/test info)
    stats_df = df.filter(pl.col("date") < train_end) if train_end else df
    if verbose and train_end:
        print(f"  Computing selection statistics on training data only (< {train_end}, {len(stats_df):,} rows)")

    feature_cols = [c for c in df.columns if _is_feature_col(c)]
    initial_count = len(feature_cols)

    # 1. Remove features with too many nulls (computed on training data)
    null_fracs = {c: stats_df[c].null_count() / len(stats_df) for c in feature_cols}
    kept = [c for c in feature_cols if null_fracs[c] <= max_null_pct]
    dropped_nulls = initial_count - len(kept)
    if verbose:
        print(f"  Null filter (>{max_null_pct:.0%}): dropped {dropped_nulls}, kept {len(kept)}")
    feature_cols = kept

    # 2. Remove near-zero variance features (computed on training data)
    numeric_arr = stats_df.select(feature_cols).to_numpy()
    np.nan_to_num(numeric_arr, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
    variances = np.nanvar(numeric_arr, axis=0)
    variance_threshold = np.nanquantile(variances, min_variance_pct)
    low_var = [feature_cols[i] for i, v in enumerate(variances) if v <= variance_threshold]
    feature_cols = [c for c in feature_cols if c not in low_var]
    if verbose:
        print(f"  Variance filter (bottom {min_variance_pct:.0%}): dropped {len(low_var)}, kept {len(feature_cols)}")

    # 3. Remove highly correlated features (computed on training data)
    if len(feature_cols) > 1:
        corr_arr = stats_df.select(feature_cols).drop_nulls().to_numpy()
        np.nan_to_num(corr_arr, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
        corr_matrix = np.corrcoef(corr_arr.T)
        np.fill_diagonal(corr_matrix, 0)
        to_drop: set[str] = set()
        for i in range(len(feature_cols)):
            if feature_cols[i] in to_drop:
                continue
            for j in range(i + 1, len(feature_cols)):
                if feature_cols[j] in to_drop:
                    continue
                if abs(corr_matrix[i, j]) > max_correlation:
                    to_drop.add(feature_cols[j])
        feature_cols = [c for c in feature_cols if c not in to_drop]
        if verbose:
            print(f"  Correlation filter (>{max_correlation}): dropped {len(to_drop)}, kept {len(feature_cols)}")

    # 4. Remove features with low mutual information vs target
    min_mi = sel_cfg.get("min_mutual_info", 0.0)
    if min_mi > 0 and "target" in stats_df.columns and len(feature_cols) > 0:
        from sklearn.feature_selection import mutual_info_classif

        mi_df = stats_df.select(feature_cols + ["target"]).drop_nulls()
        X = mi_df.select(feature_cols).to_numpy()
        y = mi_df["target"].to_numpy()
        np.nan_to_num(X, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
        mi_scores = mutual_info_classif(X, y, random_state=42)
        low_mi = [feature_cols[i] for i, s in enumerate(mi_scores) if s < min_mi]
        feature_cols = [c for c in feature_cols if c not in low_mi]
        if verbose:
            print(f"  MI filter (>={min_mi}): dropped {len(low_mi)}, kept {len(feature_cols)}")

    if verbose:
        print(f"  Feature selection: {initial_count} -> {len(feature_cols)} features")

    keep_cols = ["symbol", "date"] + feature_cols + ["target"]
    keep_cols = [c for c in keep_cols if c in df.columns]
    return df.select(keep_cols), feature_cols


def main() -> None:
    """Run feature selection on the features parquet and save result."""
    from src.config import compute_split_dates

    config = load_config()

    parser = argparse.ArgumentParser(description="Feature selection")
    parser.add_argument("--input", default="data/features.parquet")
    parser.add_argument("--output", default="data/features_selected.parquet")
    parser.add_argument("--manifest", default="data/selected_features.json")
    args = parser.parse_args()

    if not config.get("feature_selection", {}).get("enabled", True):
        print("Feature selection disabled in config. Skipping.")
        return

    print(f"Loading features from {args.input}...")
    df = pl.read_parquet(args.input)
    print(f"  {len(df):,} rows, {len(df.columns)} columns")

    # Use only training data for computing selection statistics (avoid data leakage)
    split_dates = compute_split_dates(config)
    train_end = split_dates.train_end

    print("Running feature selection...")
    df_selected, selected_cols = select_features(df, config, train_end=train_end)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df_selected.write_parquet(args.output)
    print(f"  Saved {len(df_selected):,} rows to {args.output}")

    with open(args.manifest, "w") as f:
        json.dump({"features": selected_cols, "count": len(selected_cols)}, f, indent=2)
    print(f"  Feature manifest saved to {args.manifest}")


if __name__ == "__main__":
    main()
