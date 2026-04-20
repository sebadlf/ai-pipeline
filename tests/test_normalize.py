"""Tests for feature normalization.

Focus: mean/std must be computed on the percentile-clipped distribution so
that heavy-tailed features get a reasonable Z-score scale (BEC-36).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from src.features.normalize import (
    apply_normalization_to_array,
    compute_normalization_stats,
    normalize_features,
)


@pytest.fixture
def heavy_tailed_parquet(tmp_path: Path) -> Path:
    """Create a parquet with a feature that has extreme outliers.

    Bulk of mass in [-1, 1], but 2 samples at +/-100. Without clipping,
    raw std is dominated by the outliers; with clipping at p01/p99 the
    outliers are brought to the bulk and std drops dramatically.
    """
    rng = np.random.default_rng(42)
    n = 1000
    bulk = rng.normal(loc=0.0, scale=1.0, size=n - 2)
    feature = np.concatenate([bulk, np.array([100.0, -100.0])])

    dates = [dt.date(2020, 1, 1) + dt.timedelta(days=i) for i in range(n)]
    df = pl.DataFrame(
        {
            "symbol": ["AAA"] * n,
            "date": dates,
            "target": [0] * n,
            "adj_close": [100.0] * n,
            "feat_heavy_tail": feature,
            "feat_normal": rng.normal(size=n),
        }
    )
    path = tmp_path / "features_selected.parquet"
    df.write_parquet(path)
    return path


def _config_for_parquet(parquet: Path) -> dict:
    """Build a minimal config dict pointing at a synthetic parquet."""
    return {
        "feature_selection": {"enabled": True},
        "normalization": {
            "clip_percentiles": [1, 99],
            "output_stats": str(parquet.parent / "normalization_stats.json"),
            "output_parquet": str(parquet.parent / "features_normalized.parquet"),
        },
        "ingestion": {"start_years_back": 8},
        "training": {
            "test_years": 1,
            "val_years": 1,
            "purge_days": 21,
        },
    }


def test_stats_computed_on_clipped_distribution(
    heavy_tailed_parquet: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mean/std must be computed after percentile clipping, not on raw data."""
    # Monkey-patch the path resolver so compute_normalization_stats reads our file
    import src.features.normalize as norm_mod

    monkeypatch.setattr(
        norm_mod, "get_features_parquet_path", lambda _cfg: str(heavy_tailed_parquet)
    )
    # Pin today far in the future so all sample dates fall in the training window
    monkeypatch.setattr(
        norm_mod,
        "compute_split_dates",
        lambda _cfg: type(
            "S",
            (),
            {
                "train_end": dt.date(2099, 1, 1),
            },
        )(),
    )

    config = _config_for_parquet(heavy_tailed_parquet)
    stats = compute_normalization_stats(config)

    feat_stats = stats["features"]["feat_heavy_tail"]
    # Std computed on raw data (with +/-100 outliers) would be ~6.3.
    # Std computed on clipped data (p01/p99 ~ [-2.3, 2.3]) should be ~1.0.
    assert feat_stats["std"] < 2.0, (
        f"std={feat_stats['std']:.3f} — stats appear to be computed on raw (unclipped) "
        "distribution; they must be computed AFTER percentile clipping."
    )
    # Sanity: the clip bounds themselves must still reflect the raw distribution's tails
    assert abs(feat_stats["p_low"]) < 5.0
    assert abs(feat_stats["p_high"]) < 5.0


def test_normalized_feature_std_close_to_one(
    heavy_tailed_parquet: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After normalization, clipped+z-scored features should have std ~ 1.

    This is the end-to-end property that BEC-36 is solving: previously,
    heavy-tailed features ended up with effective std << 1 after normalization.
    """
    import src.features.normalize as norm_mod

    monkeypatch.setattr(
        norm_mod, "get_features_parquet_path", lambda _cfg: str(heavy_tailed_parquet)
    )
    monkeypatch.setattr(
        norm_mod,
        "compute_split_dates",
        lambda _cfg: type("S", (), {"train_end": dt.date(2099, 1, 1)})(),
    )

    config = _config_for_parquet(heavy_tailed_parquet)
    stats = compute_normalization_stats(config)
    normalized = normalize_features(config, stats)

    norm_std = float(normalized["feat_heavy_tail"].std())
    assert 0.8 <= norm_std <= 1.2, (
        f"post-normalization std of heavy-tailed feature = {norm_std:.3f}, expected ~1.0 (BEC-36)."
    )


def test_apply_normalization_to_array_matches_clipped_stats() -> None:
    """apply_normalization_to_array should apply clip + Z-score using saved stats."""
    stats = {
        "features": {
            "f0": {"mean": 0.0, "std": 1.0, "p_low": -2.0, "p_high": 2.0},
        }
    }
    x = np.array([[-10.0], [0.0], [10.0]])
    out = apply_normalization_to_array(x, ["f0"], stats)
    # -10 -> clipped to -2, then (-2 - 0)/1 = -2
    # 10 -> clipped to +2, then (2 - 0)/1 = 2
    assert out[0, 0] == pytest.approx(-2.0)
    assert out[1, 0] == pytest.approx(0.0)
    assert out[2, 0] == pytest.approx(2.0)
