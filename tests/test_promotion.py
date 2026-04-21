"""Tests for promotion score comparison logic."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import mlflow.exceptions
import pytest

from src.evaluation.promote import (
    _count_registered_champions,
    _find_best_candidate,
    build_score_tuple,
    candidate_beats_champion,
    cascading_compare,
)

# --------------------------------------------------------------------------- #
# Default promotion config for tests                                           #
# --------------------------------------------------------------------------- #


@pytest.fixture
def promo_cfg() -> dict:
    return {
        "primary_metric": "val_acc",
        "higher_is_better": True,
        "tiebreak_metrics": ["val_acc_up"],
    }


# --------------------------------------------------------------------------- #
# build_score_tuple                                                            #
# --------------------------------------------------------------------------- #


class TestBuildScoreTuple:
    def test_basic_score(self, promo_cfg: dict) -> None:
        metrics = {"val_acc": 0.82, "val_acc_up": 0.75}
        score = build_score_tuple(metrics, promo_cfg)
        assert score == (0.82, 0.75)

    def test_missing_primary_returns_none(self, promo_cfg: dict) -> None:
        metrics = {"val_acc_up": 0.75}
        score = build_score_tuple(metrics, promo_cfg)
        assert score is None

    def test_missing_tiebreak_uses_neg_inf(self, promo_cfg: dict) -> None:
        metrics = {"val_acc": 0.80}
        score = build_score_tuple(metrics, promo_cfg)
        assert score is not None
        assert score[0] == 0.80
        assert score[1] == float("-inf")

    def test_higher_is_better_false(self) -> None:
        cfg = {
            "primary_metric": "val_loss",
            "higher_is_better": False,
            "tiebreak_metrics": [],
        }
        m1 = {"val_loss": 0.5}
        m2 = {"val_loss": 0.3}
        s1 = build_score_tuple(m1, cfg)
        s2 = build_score_tuple(m2, cfg)
        assert s1 is not None and s2 is not None
        # 0.3 flipped to -0.3, 0.5 flipped to -0.5 → m2 scores higher (less loss)
        assert s2 > s1

    def test_multiple_tiebreaks(self) -> None:
        cfg = {
            "primary_metric": "val_acc",
            "higher_is_better": True,
            "tiebreak_metrics": ["val_acc_up", "val_f1_up"],
        }
        metrics = {"val_acc": 0.80, "val_acc_up": 0.70, "val_f1_up": 0.65}
        score = build_score_tuple(metrics, cfg)
        assert score == (0.80, 0.70, 0.65)


# --------------------------------------------------------------------------- #
# candidate_beats_champion                                                     #
# --------------------------------------------------------------------------- #


class TestCandidateBeatsChampion:
    def test_no_champion(self, promo_cfg: dict) -> None:
        cand = {"val_acc": 0.80, "val_acc_up": 0.70}
        beats, reason = candidate_beats_champion(cand, None, promo_cfg)
        assert beats is True
        assert "no existing champion" in reason

    def test_candidate_wins_on_primary(self, promo_cfg: dict) -> None:
        cand = {"val_acc": 0.85, "val_acc_up": 0.70}
        champ = {"val_acc": 0.80, "val_acc_up": 0.75}
        beats, _ = candidate_beats_champion(cand, champ, promo_cfg)
        assert beats is True

    def test_champion_wins_on_primary(self, promo_cfg: dict) -> None:
        cand = {"val_acc": 0.75, "val_acc_up": 0.80}
        champ = {"val_acc": 0.80, "val_acc_up": 0.70}
        beats, _ = candidate_beats_champion(cand, champ, promo_cfg)
        assert beats is False

    def test_tiebreak_decides(self, promo_cfg: dict) -> None:
        cand = {"val_acc": 0.80, "val_acc_up": 0.75}
        champ = {"val_acc": 0.80, "val_acc_up": 0.70}
        beats, _ = candidate_beats_champion(cand, champ, promo_cfg)
        assert beats is True

    def test_candidate_missing_primary(self, promo_cfg: dict) -> None:
        cand = {"val_acc_up": 0.90}
        champ = {"val_acc": 0.80, "val_acc_up": 0.70}
        beats, reason = candidate_beats_champion(cand, champ, promo_cfg)
        assert beats is False
        assert "missing" in reason

    def test_champion_missing_primary_candidate_wins(self, promo_cfg: dict) -> None:
        cand = {"val_acc": 0.70, "val_acc_up": 0.60}
        champ = {"val_acc_up": 0.90}  # champion has no val_acc
        beats, reason = candidate_beats_champion(cand, champ, promo_cfg)
        assert beats is True
        assert "champion" in reason and "missing" in reason

    def test_exact_tie_does_not_promote(self, promo_cfg: dict) -> None:
        """Equal scores → no promotion (strictly better required)."""
        metrics = {"val_acc": 0.80, "val_acc_up": 0.70}
        beats, _ = candidate_beats_champion(metrics, metrics, promo_cfg)
        assert beats is False


# --------------------------------------------------------------------------- #
# Cascading elimination                                                        #
# --------------------------------------------------------------------------- #


@pytest.fixture
def cascading_cfg() -> dict:
    return {
        "evaluation": {
            "thresholds": [0.50, 0.60, 0.70],
            "primary_threshold": 0.60,
            "min_recall": 0.10,
            "min_signals_per_window": 5,
        },
        "walk_forward": {
            "window_size": 63,
            "step_size": 21,
            "max_std_ratio": 0.15,
            "stability_penalty": 1.5,
        },
        "ranking": {
            "tiebreak_margin": 0.01,
        },
    }


class TestCascadingCompare:
    def test_no_champion_promotes(self, cascading_cfg: dict) -> None:
        cand = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.65,
            "val_fp_severity": 0.01,
        }
        beats, reason = cascading_compare(cand, None, cascading_cfg)
        assert beats is True
        assert "no existing champion" in reason

    def test_candidate_fails_filters(self, cascading_cfg: dict) -> None:
        """With an existing champion, a filter-failing candidate is rejected."""
        cand = {
            "val_passed_all_filters": "false",
            "val_elimination_stage": "failed_stability",
            "val_stability_score": 0.80,
        }
        champ = {"val_passed_all_filters": "true", "val_stability_score": 0.60}
        beats, reason = cascading_compare(cand, champ, cascading_cfg)
        assert beats is False
        assert "failed filters" in reason

    def test_champion_failed_candidate_passed(self, cascading_cfg: dict) -> None:
        cand = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.60,
        }
        champ = {
            "val_passed_all_filters": "false",
            "val_elimination_stage": "failed_recall",
        }
        beats, reason = cascading_compare(cand, champ, cascading_cfg)
        assert beats is True
        assert "champion failed" in reason

    def test_candidate_better_score(self, cascading_cfg: dict) -> None:
        cand = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.75,
        }
        champ = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.60,
        }
        beats, _ = cascading_compare(cand, champ, cascading_cfg)
        assert beats is True

    def test_candidate_worse_score(self, cascading_cfg: dict) -> None:
        cand = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.50,
        }
        champ = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.70,
        }
        beats, _ = cascading_compare(cand, champ, cascading_cfg)
        assert beats is False

    def test_tiebreak_by_fp_severity(self, cascading_cfg: dict) -> None:
        """Within margin, prefer lower FP severity."""
        cand = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.700,
            "val_fp_severity": 0.005,  # less severe
        }
        champ = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.705,  # within 0.01 margin
            "val_fp_severity": 0.020,  # more severe
        }
        beats, reason = cascading_compare(cand, champ, cascading_cfg)
        assert beats is True
        assert "tiebreaker" in reason

    def test_tiebreak_champion_wins(self, cascading_cfg: dict) -> None:
        """Within margin, champion has better FP severity."""
        cand = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.700,
            "val_fp_severity": 0.030,
        }
        champ = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.705,
            "val_fp_severity": 0.010,
        }
        beats, _ = cascading_compare(cand, champ, cascading_cfg)
        assert beats is False

    def test_legacy_config_uses_legacy_path(self, promo_cfg: dict) -> None:
        """Without 'evaluation' key, uses legacy tuple comparison."""
        cand = {"val_acc": 0.85, "val_acc_up": 0.70}
        champ = {"val_acc": 0.80, "val_acc_up": 0.75}
        beats, _ = candidate_beats_champion(cand, champ, promo_cfg)
        assert beats is True

    def test_cascading_config_uses_cascading_path(self, cascading_cfg: dict) -> None:
        """With 'evaluation' key, uses cascading comparison."""
        cand = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.75,
        }
        beats, reason = candidate_beats_champion(cand, None, cascading_cfg)
        assert beats is True
        assert "no existing champion" in reason

    def test_cascading_no_champion_cold_start_promotes_failed_filters(
        self, cascading_cfg: dict
    ) -> None:
        """Cold-start: when no champion exists, promote even if filters failed.

        Guarantees every cluster ends up with at least one registered version.
        """
        cand = {
            "val_passed_all_filters": "false",
            "val_elimination_stage": "failed_stability",
            "val_stability_score": 0.40,
        }
        beats, reason = cascading_compare(cand, None, cascading_cfg)
        assert beats is True
        assert "fallback" in reason
        assert "failed_stability" in reason

    def test_cascading_no_champion_cold_start_missing_score(self, cascading_cfg: dict) -> None:
        """Cold-start path handles a missing stability_score gracefully."""
        cand = {"val_passed_all_filters": "false", "val_elimination_stage": "unknown"}
        beats, reason = cascading_compare(cand, None, cascading_cfg)
        assert beats is True
        assert "no existing champion" in reason

    def test_cascading_existing_champion_still_rejects_failed_filters(
        self, cascading_cfg: dict
    ) -> None:
        """With an existing champion, filter-failing candidate is rejected."""
        cand = {
            "val_passed_all_filters": "false",
            "val_elimination_stage": "failed_stability",
        }
        champ = {"val_passed_all_filters": "true", "val_stability_score": 0.60}
        beats, reason = cascading_compare(cand, champ, cascading_cfg)
        assert beats is False
        assert "failed filters" in reason

    def test_calibrated_candidate_beats_uncalibrated_champion_within_margin(
        self, cascading_cfg: dict
    ) -> None:
        """BEC-39/BEC-54: an isotonic-calibrated candidate wins over a non-calibrated champion
        when scores are within tiebreak margin.

        iso_calibration is a tiebreaker that dominates within the margin zone (BEC-54 rework).
        It does NOT override a clearly-better champion score outside the margin.
        """
        cand = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.695,  # within 0.01 margin of champion
            "isotonic_fitted": 1.0,
        }
        champ = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.700,
            # No isotonic_fitted metric → legacy pre-BEC-37 run
        }
        beats, reason = cascading_compare(cand, champ, cascading_cfg)
        assert beats is True
        assert "isotonic-calibrated" in reason
        assert "tiebreaker=iso_calibration" in reason

    def test_calibrated_candidate_does_not_override_clearly_better_champion(
        self, cascading_cfg: dict
    ) -> None:
        """BEC-54: iso_calibration does not override a champion with a clearly higher score.

        When champion score is well above the tiebreak margin, stability_score decides,
        not calibration status.
        """
        cand = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.55,
            "isotonic_fitted": 1.0,
        }
        champ = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.70,
            # No isotonic_fitted metric → legacy pre-BEC-37 run
        }
        beats, reason = cascading_compare(cand, champ, cascading_cfg)
        assert beats is False
        assert "stability_score" in reason

    def test_iso_preference_with_equal_stability_scores(self, cascading_cfg: dict) -> None:
        """BEC-50: with equal stability scores, iso-calibrated candidate beats non-calibrated.

        Verifies BEC-39 iso preference fires deterministically when no score difference
        would otherwise decide the comparison.
        """
        cand = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.65,
            "isotonic_fitted": 1.0,
        }
        champ = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.65,  # identical score
            # No isotonic_fitted → legacy pre-calibration run
        }
        beats, reason = cascading_compare(cand, champ, cascading_cfg)
        assert beats is True
        assert "tiebreaker=iso_calibration" in reason

    def test_calibrated_champion_vs_calibrated_candidate_uses_score(
        self, cascading_cfg: dict
    ) -> None:
        """When both are calibrated, comparison falls back to stability score."""
        cand = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.55,
            "isotonic_fitted": 1.0,
        }
        champ = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.70,
            "isotonic_fitted": 1.0,
        }
        beats, _ = cascading_compare(cand, champ, cascading_cfg)
        assert beats is False

    def test_uncalibrated_candidate_does_not_beat_calibrated_champion(
        self, cascading_cfg: dict
    ) -> None:
        """An uncalibrated candidate does not get special preference."""
        cand = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.55,
        }
        champ = {
            "val_passed_all_filters": "true",
            "val_stability_score": 0.70,
            "isotonic_fitted": 1.0,
        }
        beats, _ = cascading_compare(cand, champ, cascading_cfg)
        assert beats is False


# --------------------------------------------------------------------------- #
# _find_best_candidate tier fallback                                           #
# --------------------------------------------------------------------------- #


def _make_run(
    run_id: str,
    metrics: dict | None = None,
    params: dict | None = None,
    end_time: int = 0,
):
    """Build a minimal MLflow-run-like object for tier selection tests."""
    return SimpleNamespace(
        info=SimpleNamespace(run_id=run_id, end_time=end_time),
        data=SimpleNamespace(metrics=metrics or {}, params=params or {}, tags={}),
    )


def _make_client_with_checkpoints(run_ids_with_ckpt: set[str]):
    """Build a MlflowClient stub whose list_artifacts returns a .ckpt for specific runs."""

    client = MagicMock()

    def list_artifacts(run_id, path=None):
        if run_id in run_ids_with_ckpt and path is None:
            return [SimpleNamespace(path="model.ckpt", is_dir=False)]
        return []

    client.list_artifacts.side_effect = list_artifacts
    client.set_tag.return_value = None
    return client


class TestFindBestCandidateTierFallback:
    def test_tier1_prefers_calibrated_run_within_tier(self) -> None:
        """BEC-39: within tier 1, a calibrated run beats a non-calibrated run

        even if the non-calibrated run has a higher stability score.
        """
        cfg = {"evaluation": {"primary_threshold": 0.60}}
        non_calibrated_higher_score = _make_run(
            "legacy",
            metrics={
                "val_stability_score": 0.85,
                "val_precision_up": 0.70,
            },
            params={"val_passed_all_filters": "true"},
            end_time=100,
        )
        calibrated_lower_score = _make_run(
            "calibrated",
            metrics={
                "val_stability_score": 0.80,
                "val_precision_up": 0.70,
                "isotonic_fitted": 1.0,
            },
            params={"val_passed_all_filters": "true"},
            end_time=200,
        )
        client = _make_client_with_checkpoints({"legacy", "calibrated"})
        run, ckpt = _find_best_candidate(
            client,
            [non_calibrated_higher_score, calibrated_lower_score],
            cfg,
            cluster_id="C",
        )
        assert run is calibrated_lower_score
        assert ckpt == "model.ckpt"

    def test_tier1_picks_best_score_when_both_calibrated(self) -> None:
        """When both runs are calibrated, stability score still decides within tier."""
        cfg = {"evaluation": {"primary_threshold": 0.60}}
        lower_score = _make_run(
            "low",
            metrics={"val_stability_score": 0.70, "isotonic_fitted": 1.0},
            params={"val_passed_all_filters": "true"},
            end_time=100,
        )
        higher_score = _make_run(
            "high",
            metrics={"val_stability_score": 0.80, "isotonic_fitted": 1.0},
            params={"val_passed_all_filters": "true"},
            end_time=50,
        )
        client = _make_client_with_checkpoints({"low", "high"})
        run, _ = _find_best_candidate(client, [lower_score, higher_score], cfg, cluster_id="C")
        assert run is higher_score

    def test_tier1_selects_passed_filter_run(self) -> None:
        cfg = {"evaluation": {"primary_threshold": 0.60}}
        tier1_run = _make_run(
            "tier1",
            metrics={"val_stability_score": 0.80, "val_precision_up": 0.70},
            params={"val_passed_all_filters": "true"},
            end_time=100,
        )
        tier4_only_run = _make_run(
            "tier4only",
            metrics={"val_precision_up": 0.55},
            params={
                "val_passed_all_filters": "false",
                "val_elimination_stage": "unknown",
            },
            end_time=200,
        )
        client = _make_client_with_checkpoints({"tier1", "tier4only"})
        run, ckpt = _find_best_candidate(client, [tier1_run, tier4_only_run], cfg, cluster_id="C")
        assert run is tier1_run
        assert ckpt == "model.ckpt"

    def test_tier4_fallback_when_all_filters_fail(self) -> None:
        """Every run failed filters with 'unknown' stage → tier 4 still fires."""
        cfg = {"evaluation": {"primary_threshold": 0.60}}
        older = _make_run(
            "older",
            metrics={"val_precision_up": 0.45},
            params={"val_passed_all_filters": "false"},
            end_time=100,
        )
        newer = _make_run(
            "newer",
            metrics={"val_precision_up": 0.40},
            params={"val_passed_all_filters": "false"},
            end_time=500,  # more recent, should win tier-4 sort
        )
        client = _make_client_with_checkpoints({"older", "newer"})
        run, ckpt = _find_best_candidate(client, [older, newer], cfg, cluster_id="C")
        assert run is newer
        assert ckpt == "model.ckpt"

    def test_returns_none_when_no_checkpoint(self) -> None:
        cfg = {"evaluation": {"primary_threshold": 0.60}}
        run_no_ckpt = _make_run("nockpt", params={"val_passed_all_filters": "true"})
        client = _make_client_with_checkpoints(set())
        run, ckpt = _find_best_candidate(client, [run_no_ckpt], cfg, cluster_id="C")
        assert run is None
        assert ckpt is None

    def test_legacy_mode_returns_first_run_with_checkpoint(self) -> None:
        """Legacy mode (no 'evaluation' key) returns the most recent run with ckpt."""
        cfg = {"primary_metric": "val_acc"}
        first = _make_run("first", end_time=200)
        second = _make_run("second", end_time=100)
        client = _make_client_with_checkpoints({"first", "second"})
        run, ckpt = _find_best_candidate(client, [first, second], cfg, cluster_id="C")
        assert run is first
        assert ckpt == "model.ckpt"

    def test_champion_excluded_from_candidate_pool(self) -> None:
        """BEC-54: champion run is excluded so it cannot re-select itself.

        When the champion is the only tier-1 run, the next-best tier-1 run wins,
        not the champion itself (which would result in a same-run comparison and
        suppress iso_calibration tiebreakers like BEC-50).
        """
        cfg = {"evaluation": {"primary_threshold": 0.60}}
        champion = _make_run(
            "champion",
            metrics={"val_stability_score": 0.70, "val_precision_up": 0.70},
            params={"val_passed_all_filters": "true"},
            end_time=200,
        )
        other = _make_run(
            "other",
            metrics={
                "val_stability_score": 0.68,
                "val_precision_up": 0.68,
                "isotonic_fitted": 1.0,
            },
            params={"val_passed_all_filters": "true"},
            end_time=100,
        )
        client = _make_client_with_checkpoints({"champion", "other"})
        run, ckpt = _find_best_candidate(
            client,
            [champion, other],
            cfg,
            cluster_id="C",
            champion_run_id="champion",
        )
        assert run is other, "champion should be excluded; other tier-1 run should be selected"
        assert ckpt == "model.ckpt"

    def test_champion_exclusion_not_applied_in_legacy_mode(self) -> None:
        """BEC-54: champion_run_id exclusion is skipped in legacy (non-cascading) mode."""
        cfg = {"primary_metric": "val_acc"}
        champion = _make_run("champion", end_time=200)
        other = _make_run("other", end_time=100)
        client = _make_client_with_checkpoints({"champion", "other"})
        # Even passing champion_run_id, legacy mode ignores it and returns first-with-ckpt
        run, ckpt = _find_best_candidate(
            client,
            [champion, other],
            cfg,
            cluster_id="C",
            champion_run_id="champion",
        )
        assert run is champion
        assert ckpt == "model.ckpt"


# --------------------------------------------------------------------------- #
# _count_registered_champions                                                  #
# --------------------------------------------------------------------------- #


class TestCountRegisteredChampions:
    def test_returns_only_clusters_with_champion_alias(self) -> None:
        client = MagicMock()

        def get_alias(name, alias):
            if name == "trading-forecaster-A":
                return SimpleNamespace(version="1")
            raise mlflow.exceptions.MlflowException(f"no champion for {name}")

        client.get_model_version_by_alias.side_effect = get_alias

        registered = _count_registered_champions(client, ["A", "B", "C"])
        assert registered == ["A"]

    def test_all_missing_returns_empty(self) -> None:
        client = MagicMock()
        client.get_model_version_by_alias.side_effect = mlflow.exceptions.MlflowException("missing")
        registered = _count_registered_champions(client, ["A", "B"])
        assert registered == []
