"""Tests for promotion score comparison and guard logic."""

import pytest

from src.evaluation.promote import build_score_tuple, candidate_beats_champion


# --------------------------------------------------------------------------- #
# Default promotion config for tests                                           #
# --------------------------------------------------------------------------- #

@pytest.fixture
def promo_cfg() -> dict:
    return {
        "primary_metric": "val_trade_sortino",
        "higher_is_better": True,
        "tiebreak_metrics": ["val_trade_sharpe", "val_trade_calmar"],
        "min_val_trade_num_trades": 1,
        "max_val_trade_max_drawdown": -0.80,
        "legacy_fallback_to_val_acc": True,
    }


# --------------------------------------------------------------------------- #
# build_score_tuple                                                            #
# --------------------------------------------------------------------------- #

class TestBuildScoreTuple:
    def test_basic_score(self, promo_cfg: dict) -> None:
        metrics = {
            "val_trade_sortino": 1.5,
            "val_trade_sharpe": 1.2,
            "val_trade_calmar": 0.8,
            "val_trade_num_trades": 5,
            "val_trade_max_drawdown": -0.15,
        }
        score = build_score_tuple(metrics, promo_cfg)
        assert score == (1.5, 1.2, 0.8)

    def test_missing_primary_with_legacy_fallback(self, promo_cfg: dict) -> None:
        metrics = {"val_acc": 0.72}
        score = build_score_tuple(metrics, promo_cfg)
        assert score == (0.72,)

    def test_missing_primary_no_fallback(self, promo_cfg: dict) -> None:
        promo_cfg["legacy_fallback_to_val_acc"] = False
        metrics = {"val_acc": 0.72}
        score = build_score_tuple(metrics, promo_cfg)
        assert score is None

    def test_missing_primary_no_val_acc(self, promo_cfg: dict) -> None:
        metrics = {"some_other": 1.0}
        score = build_score_tuple(metrics, promo_cfg)
        assert score is None

    def test_guard_min_trades_fails(self, promo_cfg: dict) -> None:
        metrics = {
            "val_trade_sortino": 2.0,
            "val_trade_num_trades": 0,
            "val_trade_max_drawdown": -0.10,
        }
        score = build_score_tuple(metrics, promo_cfg)
        assert score is None

    def test_guard_max_drawdown_fails(self, promo_cfg: dict) -> None:
        metrics = {
            "val_trade_sortino": 2.0,
            "val_trade_num_trades": 5,
            "val_trade_max_drawdown": -0.85,  # worse than -0.80 limit
        }
        score = build_score_tuple(metrics, promo_cfg)
        assert score is None

    def test_guard_drawdown_exactly_at_limit(self, promo_cfg: dict) -> None:
        metrics = {
            "val_trade_sortino": 2.0,
            "val_trade_num_trades": 5,
            "val_trade_max_drawdown": -0.80,  # exactly at limit — passes
        }
        score = build_score_tuple(metrics, promo_cfg)
        assert score is not None

    def test_missing_tiebreak_uses_neg_inf(self, promo_cfg: dict) -> None:
        metrics = {
            "val_trade_sortino": 1.0,
            "val_trade_num_trades": 3,
            "val_trade_max_drawdown": -0.10,
            # sharpe and calmar missing
        }
        score = build_score_tuple(metrics, promo_cfg)
        assert score is not None
        assert score[0] == 1.0
        assert score[1] == float("-inf")
        assert score[2] == float("-inf")

    def test_higher_is_better_false(self) -> None:
        cfg = {
            "primary_metric": "val_trade_max_drawdown",
            "higher_is_better": False,
            "tiebreak_metrics": [],
            "legacy_fallback_to_val_acc": False,
        }
        # lower drawdown = better when higher_is_better=False → sign flipped
        m1 = {"val_trade_max_drawdown": -0.10}
        m2 = {"val_trade_max_drawdown": -0.20}
        s1 = build_score_tuple(m1, cfg)
        s2 = build_score_tuple(m2, cfg)
        assert s1 is not None and s2 is not None
        # -0.10 flipped to 0.10, -0.20 flipped to 0.20 — so m2 scores higher
        assert s2 > s1


# --------------------------------------------------------------------------- #
# candidate_beats_champion                                                     #
# --------------------------------------------------------------------------- #

class TestCandidateBeatsChampion:
    def test_no_champion(self, promo_cfg: dict) -> None:
        cand = {
            "val_trade_sortino": 1.0,
            "val_trade_num_trades": 3,
            "val_trade_max_drawdown": -0.10,
        }
        beats, reason = candidate_beats_champion(cand, None, promo_cfg)
        assert beats is True
        assert "no existing champion" in reason

    def test_candidate_wins(self, promo_cfg: dict) -> None:
        cand = {
            "val_trade_sortino": 2.0,
            "val_trade_sharpe": 1.5,
            "val_trade_calmar": 1.0,
            "val_trade_num_trades": 5,
            "val_trade_max_drawdown": -0.10,
        }
        champ = {
            "val_trade_sortino": 1.5,
            "val_trade_sharpe": 1.2,
            "val_trade_calmar": 0.8,
            "val_trade_num_trades": 5,
            "val_trade_max_drawdown": -0.10,
        }
        beats, reason = candidate_beats_champion(cand, champ, promo_cfg)
        assert beats is True

    def test_champion_wins(self, promo_cfg: dict) -> None:
        cand = {
            "val_trade_sortino": 1.0,
            "val_trade_sharpe": 1.0,
            "val_trade_calmar": 0.5,
            "val_trade_num_trades": 5,
            "val_trade_max_drawdown": -0.10,
        }
        champ = {
            "val_trade_sortino": 1.5,
            "val_trade_sharpe": 1.2,
            "val_trade_calmar": 0.8,
            "val_trade_num_trades": 5,
            "val_trade_max_drawdown": -0.10,
        }
        beats, reason = candidate_beats_champion(cand, champ, promo_cfg)
        assert beats is False

    def test_tiebreak_decides(self, promo_cfg: dict) -> None:
        base = {
            "val_trade_sortino": 1.5,
            "val_trade_num_trades": 5,
            "val_trade_max_drawdown": -0.10,
        }
        cand = {**base, "val_trade_sharpe": 1.5, "val_trade_calmar": 1.0}
        champ = {**base, "val_trade_sharpe": 1.2, "val_trade_calmar": 0.8}
        beats, _ = candidate_beats_champion(cand, champ, promo_cfg)
        assert beats is True

    def test_candidate_fails_guard(self, promo_cfg: dict) -> None:
        cand = {
            "val_trade_sortino": 5.0,
            "val_trade_num_trades": 0,  # fails guard
            "val_trade_max_drawdown": -0.05,
        }
        champ = {
            "val_trade_sortino": 1.0,
            "val_trade_num_trades": 5,
            "val_trade_max_drawdown": -0.10,
        }
        beats, reason = candidate_beats_champion(cand, champ, promo_cfg)
        assert beats is False
        assert "guard" in reason or "missing" in reason

    def test_champion_fails_guard_candidate_wins(self, promo_cfg: dict) -> None:
        cand = {
            "val_trade_sortino": 1.0,
            "val_trade_num_trades": 3,
            "val_trade_max_drawdown": -0.10,
        }
        champ = {
            "val_trade_sortino": 5.0,
            "val_trade_num_trades": 0,  # champion fails guard
            "val_trade_max_drawdown": -0.05,
        }
        beats, reason = candidate_beats_champion(cand, champ, promo_cfg)
        assert beats is True
        assert "champion failed" in reason

    def test_legacy_candidate_vs_legacy_champion(self, promo_cfg: dict) -> None:
        """Both runs only have val_acc (legacy)."""
        cand = {"val_acc": 0.75}
        champ = {"val_acc": 0.70}
        beats, _ = candidate_beats_champion(cand, champ, promo_cfg)
        assert beats is True

    def test_exact_tie_does_not_promote(self, promo_cfg: dict) -> None:
        """Equal scores → no promotion (strictly better required)."""
        metrics = {
            "val_trade_sortino": 1.5,
            "val_trade_sharpe": 1.2,
            "val_trade_calmar": 0.8,
            "val_trade_num_trades": 5,
            "val_trade_max_drawdown": -0.10,
        }
        beats, _ = candidate_beats_champion(metrics, metrics, promo_cfg)
        assert beats is False
