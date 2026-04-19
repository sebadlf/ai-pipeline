"""Feature selection and dimensionality reduction.

Filters features by null rate, variance, and correlation to reduce
the feature space before model training.

Usage:
    uv run python -m src.features.selection
"""
# ruff: noqa: N806  # ML convention: capital X for feature matrices

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
        print(
            f"  Computing selection statistics on training data only "
            f"(< {train_end}, {len(stats_df):,} rows)"
        )

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
        print(
            f"  Variance filter (bottom {min_variance_pct:.0%}): "
            f"dropped {len(low_var)}, kept {len(feature_cols)}"
        )

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
            print(
                f"  Correlation filter (>{max_correlation}): "
                f"dropped {len(to_drop)}, kept {len(feature_cols)}"
            )

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


def _detect_feature_changes(selected_cols: list[str], manifest_path: Path) -> dict:
    """Compare selected features with previous manifest and detect changes.

    Returns:
        dict with 'added', 'removed', 'unchanged' feature lists and 'significant_change' bool.
    """
    if not manifest_path.exists():
        return {"added": selected_cols, "removed": [], "unchanged": [], "significant_change": True}

    try:
        with open(manifest_path) as f:
            prev = json.load(f)
        prev_features = set(prev.get("features", []))
        curr_features = set(selected_cols)

        added = list(curr_features - prev_features)
        removed = list(prev_features - curr_features)
        unchanged = list(curr_features & prev_features)

        # Consider significant if >10% features changed or any feature removed
        total_prev = len(prev_features) if prev_features else 1
        change_ratio = (len(added) + len(removed)) / total_prev
        significant = change_ratio > 0.1 or len(removed) > 0

        return {
            "added": added,
            "removed": removed,
            "unchanged": unchanged,
            "significant_change": significant,
            "prev_count": len(prev_features),
            "curr_count": len(selected_cols),
        }
    except (OSError, json.JSONDecodeError):
        return {"added": selected_cols, "removed": [], "unchanged": [], "significant_change": True}


def detect_drift(
    df: pl.DataFrame,
    config: dict,
    recent_months: int = 6,
    rank_change_threshold: float = 0.30,
    verbose: bool = True,
) -> dict:
    """Detect feature drift by comparing MI rankings in recent vs full period.

    Compares mutual information rankings of features computed on the full
    training period against the most recent `recent_months` months. Features
    whose relative rank changes by more than `rank_change_threshold` are
    flagged as drifting.

    Args:
        df: Features DataFrame with symbol, date, target columns.
        config: Full config dict.
        recent_months: Number of recent months to compare against full period.
        rank_change_threshold: Flag features with rank change > this fraction.
        verbose: Print drift report.

    Returns:
        dict with 'drifted_features', 'rank_changes', 'n_features', 'has_significant_drift'.
    """
    from sklearn.feature_selection import mutual_info_classif

    feature_cols = [c for c in df.columns if _is_feature_col(c)]
    if not feature_cols or "target" not in df.columns:
        return {
            "drifted_features": [],
            "rank_changes": {},
            "n_features": 0,
            "has_significant_drift": False,
        }

    # Full period MI
    full_df = df.select(feature_cols + ["target"]).drop_nulls()
    X_full = full_df.select(feature_cols).to_numpy()
    y_full = full_df["target"].to_numpy()
    np.nan_to_num(X_full, copy=False, nan=0.0, posinf=0.0, neginf=0.0)

    if len(X_full) < 100:
        return {
            "drifted_features": [],
            "rank_changes": {},
            "n_features": len(feature_cols),
            "has_significant_drift": False,
        }

    mi_full = mutual_info_classif(X_full, y_full, random_state=42)

    # Recent period MI
    cutoff = df["date"].max() - dt.timedelta(days=recent_months * 30)
    recent_df = df.filter(pl.col("date") >= cutoff).select(feature_cols + ["target"]).drop_nulls()
    X_recent = recent_df.select(feature_cols).to_numpy()
    y_recent = recent_df["target"].to_numpy()
    np.nan_to_num(X_recent, copy=False, nan=0.0, posinf=0.0, neginf=0.0)

    if len(X_recent) < 100:
        if verbose:
            print(f"  Feature drift: not enough recent data ({len(X_recent)} rows), skipping")
        return {
            "drifted_features": [],
            "rank_changes": {},
            "n_features": len(feature_cols),
            "has_significant_drift": False,
        }

    mi_recent = mutual_info_classif(X_recent, y_recent, random_state=42)

    # Compare rankings (normalized to [0, 1])
    n = len(feature_cols)
    rank_full = np.argsort(np.argsort(-mi_full)).astype(float) / max(n - 1, 1)
    rank_recent = np.argsort(np.argsort(-mi_recent)).astype(float) / max(n - 1, 1)

    rank_changes = {}
    drifted = []
    for i, col in enumerate(feature_cols):
        change = abs(rank_full[i] - rank_recent[i])
        rank_changes[col] = round(float(change), 4)
        if change > rank_change_threshold:
            drifted.append(col)

    has_drift = len(drifted) > max(1, int(n * 0.1))  # significant if >10% of features drifted

    if verbose:
        print(f"\n  Feature drift analysis (last {recent_months} months vs full period):")
        print(f"    Total features: {n}")
        print(f"    Drifted features (rank change > {rank_change_threshold:.0%}): {len(drifted)}")
        if drifted:
            # Sort by drift magnitude
            drifted_sorted = sorted(drifted, key=lambda c: rank_changes[c], reverse=True)
            for col in drifted_sorted[:10]:
                print(f"      {col}: rank change = {rank_changes[col]:.2%}")
            if len(drifted_sorted) > 10:
                print(f"      ... and {len(drifted_sorted) - 10} more")
        if has_drift:
            print("    WARNING: Significant feature drift detected! Consider retraining.")

    return {
        "drifted_features": drifted,
        "rank_changes": rank_changes,
        "n_features": n,
        "has_significant_drift": has_drift,
    }


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

    # Detect changes from previous manifest
    manifest_path = Path(args.manifest)
    changes = _detect_feature_changes(selected_cols, manifest_path)

    if changes["significant_change"] and manifest_path.exists():
        print("\n  ⚠️  WARNING: Significant feature changes detected!")
        print(f"     Previous: {changes.get('prev_count', 0)} features")
        print(f"     Current:  {changes['curr_count']} features")
        if changes["added"]:
            print(f"     Added:   {len(changes['added'])} features")
        if changes["removed"]:
            print(f"     Removed: {len(changes['removed'])} features")
        print("\n     ... existing models were trained with DIFFERENT features.")
        print("     ... you MUST retrain models: make train")
        print("     ... otherwise aggregate/signals will fail or be unreliable.\n")

    # Feature drift detection — compare recent vs full period MI rankings
    drift_result = detect_drift(df, config, recent_months=6, verbose=True)
    if drift_result["has_significant_drift"]:
        print(
            f"\n  WARNING: {len(drift_result['drifted_features'])} features show significant drift."
        )
        print("  Models trained on older data may underperform. Consider retraining.")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df_selected.write_parquet(args.output)
    print(f"  Saved {len(df_selected):,} rows to {args.output}")

    with open(manifest_path, "w") as f:
        json.dump({"features": selected_cols, "count": len(selected_cols)}, f, indent=2)
    print(f"  Feature manifest saved to {manifest_path}")


if __name__ == "__main__":
    main()
