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


# ---------------------------------------------------------------------------
# BEC-41: rank-transform fallback for degenerate features
# ---------------------------------------------------------------------------


@pytest.fixture
def degenerate_parquet(tmp_path: Path) -> Path:
    """Create a parquet with a feature whose post-clipping std is tiny.

    Simulates a fundamental ratio where most mass sits in a narrow band
    but a few tail samples are orders of magnitude larger. Clipping at
    [p01, p99] trims the tails, and the remaining bulk's std is so small
    relative to the original scale that z-score normalization on the full
    (train+val+test) window yields std much less than 1.
    """
    rng = np.random.default_rng(7)
    n = 5000
    # 99% narrow bulk, 1% extreme tails. Clipping at p01/p99 keeps only a
    # razor-thin band from the bulk (std << 1% of raw magnitude), so the
    # z-score output on the full window collapses to near-zero variance.
    bulk = rng.normal(loc=0.25, scale=0.01, size=int(0.99 * n))
    tail_pos = rng.uniform(low=50.0, high=100.0, size=int(0.005 * n))
    tail_neg = rng.uniform(low=-100.0, high=-50.0, size=int(0.005 * n))
    feature = np.concatenate([bulk, tail_pos, tail_neg])
    rng.shuffle(feature)

    dates = [dt.date(2020, 1, 1) + dt.timedelta(days=i) for i in range(n)]
    df = pl.DataFrame(
        {
            "symbol": ["AAA"] * n,
            "date": dates,
            "target": [0] * n,
            "adj_close": [100.0] * n,
            "feat_degenerate": feature,
            # A well-behaved companion so the parquet has >1 feature column
            "feat_normal": rng.normal(size=n),
        }
    )
    path = tmp_path / "features_selected.parquet"
    df.write_parquet(path)
    return path


def test_degenerate_feature_uses_quantile_transform(
    degenerate_parquet: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Degenerate features should be flagged and routed through quantile-normal.

    Acceptance criterion (BEC-41): normalization_stats records which
    features use z-score vs quantile transform.
    """
    import src.features.normalize as norm_mod

    monkeypatch.setattr(norm_mod, "get_features_parquet_path", lambda _cfg: str(degenerate_parquet))
    monkeypatch.setattr(
        norm_mod,
        "compute_split_dates",
        lambda _cfg: type("S", (), {"train_end": dt.date(2099, 1, 1)})(),
    )

    config = _config_for_parquet(degenerate_parquet)
    stats = compute_normalization_stats(config)

    assert stats["features"]["feat_degenerate"]["transform"] == "quantile"
    assert "quantiles" in stats["features"]["feat_degenerate"]
    # The well-behaved companion must stay on z-score
    assert stats["features"]["feat_normal"]["transform"] == "zscore"
    # Top-level counters
    assert stats["n_quantile"] >= 1
    assert stats["n_zscore"] >= 1


def test_quantile_transform_produces_unit_variance(
    degenerate_parquet: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On a near-degenerate distribution, the quantile fallback lifts std to ~1.

    Acceptance criterion (BEC-41): normalization produces std ≈ 1 on a
    synthetic degenerate-distribution input.
    """
    import src.features.normalize as norm_mod

    monkeypatch.setattr(norm_mod, "get_features_parquet_path", lambda _cfg: str(degenerate_parquet))
    monkeypatch.setattr(
        norm_mod,
        "compute_split_dates",
        lambda _cfg: type("S", (), {"train_end": dt.date(2099, 1, 1)})(),
    )

    config = _config_for_parquet(degenerate_parquet)
    stats = compute_normalization_stats(config)
    normalized = normalize_features(config, stats)

    norm_std = float(normalized["feat_degenerate"].std())
    # Without the quantile fallback this feature's std collapses to well
    # under 0.1. With the quantile-normal transform it should recover to
    # approximately unit variance.
    assert 0.7 <= norm_std <= 1.3, (
        f"post-normalization std of degenerate feature = {norm_std:.3f}, "
        f"expected ~1.0 (BEC-41 quantile-normal fallback)."
    )


def test_apply_normalization_to_array_handles_quantile_transform() -> None:
    """Inference path (numpy) must dispatch to quantile transform when stored."""
    # Build a minimal quantile knot set covering [0, 1] so inputs map to
    # roughly uniform ranks. Inverse normal CDF of {0.1, 0.5, 0.9} ≈
    # {-1.28, 0.0, +1.28}.
    knots = list(np.linspace(0.0, 1.0, 256))
    stats = {
        "features": {
            "f_deg": {
                "transform": "quantile",
                "mean": 0.5,
                "std": 1.0,
                "p_low": 0.0,
                "p_high": 1.0,
                "quantiles": knots,
            },
            "f_normal": {
                "transform": "zscore",
                "mean": 0.0,
                "std": 1.0,
                "p_low": -2.0,
                "p_high": 2.0,
            },
        }
    }
    x = np.array([[0.1, -10.0], [0.5, 0.0], [0.9, 10.0]])
    out = apply_normalization_to_array(x, ["f_deg", "f_normal"], stats)

    # Quantile transform on uniform knots should preserve order and
    # produce symmetric values around 0 for 0.1 / 0.9.
    assert out[0, 0] < out[1, 0] < out[2, 0]
    assert out[1, 0] == pytest.approx(0.0, abs=0.05)
    assert out[0, 0] == pytest.approx(-out[2, 0], abs=0.1)
    # Z-score column still clips + scales linearly
    assert out[0, 1] == pytest.approx(-2.0)
    assert out[2, 1] == pytest.approx(2.0)
