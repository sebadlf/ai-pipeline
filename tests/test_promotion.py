"""Tests for promotion score comparison logic."""

import pytest

from src.evaluation.promote import build_score_tuple, candidate_beats_champion, cascading_compare


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
        cand = {
            "val_passed_all_filters": "false",
            "val_elimination_stage": "failed_stability",
            "val_stability_score": 0.80,
        }
        beats, reason = cascading_compare(cand, None, cascading_cfg)
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
        assert "tiebreak" in reason

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

