"""Tests for precision-focused model evaluation."""

import datetime as dt

import numpy as np
import pytest

from src.config import PromotionEvalConfig
from src.evaluation.precision_eval import (
    compute_auc_pr,
    compute_fp_severity,
    compute_precision_at_thresholds,
    compute_walk_forward_precision,
)

# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture
def eval_config() -> PromotionEvalConfig:
    return PromotionEvalConfig(
        thresholds=[0.50, 0.60, 0.70, 0.80],
        primary_threshold=0.60,
        min_recall=0.10,
        min_signals_per_window=2,
        wf_window_size=5,
        wf_step_size=2,
        max_std_ratio=0.15,
        stability_penalty=1.5,
        tiebreak_margin=0.01,
    )


@pytest.fixture
def synthetic_data() -> tuple[np.ndarray, np.ndarray]:
    """10 samples with known prob_up and targets."""
    prob_up = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05])
    targets = np.array([1, 1, 0, 1, 0, 0, 0, 0, 0, 0])
    return prob_up, targets


# --------------------------------------------------------------------------- #
# compute_precision_at_thresholds                                              #
# --------------------------------------------------------------------------- #


class TestPrecisionAtThresholds:
    def test_basic_computation(self, synthetic_data: tuple) -> None:
        prob_up, targets = synthetic_data
        prec, recall, signals = compute_precision_at_thresholds(
            prob_up,
            targets,
            [0.50, 0.60, 0.70, 0.80],
        )
        # At threshold 0.80: predicted positive = [0.9, 0.8] → targets [1, 1] → precision=1.0
        assert prec[0.80] == 1.0
        assert signals[0.80] == 2
        assert recall[0.80] == pytest.approx(2 / 3)  # 2 TP out of 3 positives

    def test_threshold_050(self, synthetic_data: tuple) -> None:
        prob_up, targets = synthetic_data
        prec, recall, signals = compute_precision_at_thresholds(
            prob_up,
            targets,
            [0.50],
        )
        # At 0.50: predicted = [0.9, 0.8, 0.7, 0.6, 0.5] → 5 signals
        # TP = targets[0.9]=1, targets[0.8]=1, targets[0.6]=1 → 3 TP
        assert signals[0.50] == 5
        assert prec[0.50] == pytest.approx(3 / 5)
        assert recall[0.50] == pytest.approx(3 / 3)  # all 3 positives found

    def test_high_threshold_no_signals(self) -> None:
        prob_up = np.array([0.3, 0.2, 0.1])
        targets = np.array([1, 0, 0])
        prec, recall, signals = compute_precision_at_thresholds(
            prob_up,
            targets,
            [0.90],
        )
        assert signals[0.90] == 0
        assert prec[0.90] == 0.0
        assert recall[0.90] == 0.0

    def test_all_positive_targets(self) -> None:
        prob_up = np.array([0.8, 0.7, 0.6])
        targets = np.array([1, 1, 1])
        prec, _, _ = compute_precision_at_thresholds(prob_up, targets, [0.50])
        assert prec[0.50] == 1.0


# --------------------------------------------------------------------------- #
# compute_walk_forward_precision                                               #
# --------------------------------------------------------------------------- #


class TestWalkForwardPrecision:
    def test_basic_windowing(self) -> None:
        # 10 dates, window_size=5, step=2 → windows starting at [0,2,4]
        dates = np.array([dt.date(2024, 1, i + 1) for i in range(10)], dtype="datetime64[D]")
        prob_up = np.array([0.8, 0.7, 0.9, 0.6, 0.5, 0.8, 0.7, 0.9, 0.6, 0.5])
        targets = np.array([1, 1, 1, 0, 0, 1, 1, 1, 0, 0])

        precisions, mean, std, total_windows = compute_walk_forward_precision(
            prob_up,
            targets,
            dates,
            threshold=0.60,
            window_size=5,
            step_size=2,
            min_signals=2,
        )
        assert len(precisions) > 0
        assert mean > 0
        assert total_windows >= len(precisions)

    def test_empty_when_no_windows(self) -> None:
        dates = np.array([dt.date(2024, 1, 1), dt.date(2024, 1, 2)], dtype="datetime64[D]")
        prob_up = np.array([0.8, 0.7])
        targets = np.array([1, 0])

        precisions, mean, std, total_windows = compute_walk_forward_precision(
            prob_up,
            targets,
            dates,
            threshold=0.60,
            window_size=10,
            step_size=5,
            min_signals=1,
        )
        assert precisions == []
        assert mean == 0.0
        assert std == 0.0
        assert total_windows == 0

    def test_windows_below_min_signals_excluded(self) -> None:
        dates = np.array([dt.date(2024, 1, i + 1) for i in range(10)], dtype="datetime64[D]")
        # All prob_up below threshold → no signals in any window
        prob_up = np.full(10, 0.3)
        targets = np.zeros(10, dtype=int)

        precisions, mean, std, total_windows = compute_walk_forward_precision(
            prob_up,
            targets,
            dates,
            threshold=0.60,
            window_size=5,
            step_size=2,
            min_signals=1,
        )
        assert precisions == []
        assert total_windows > 0  # windows exist but none qualify


# --------------------------------------------------------------------------- #
# compute_fp_severity                                                          #
# --------------------------------------------------------------------------- #


class TestFPSeverity:
    def test_basic_fp_severity(self) -> None:
        prob_up = np.array([0.8, 0.7, 0.6])
        targets = np.array([1, 0, 0])  # index 1,2 are FP at threshold 0.5
        forward_returns = np.array([0.05, 0.01, -0.02])

        avg_fp, avg_tp, severity = compute_fp_severity(
            prob_up,
            targets,
            forward_returns,
            threshold=0.50,
            buy_threshold=0.025,
        )
        # FPs: returns [0.01, -0.02] → avg = -0.005
        assert avg_fp == pytest.approx(-0.005)
        # TP: return [0.05] → avg = 0.05
        assert avg_tp == pytest.approx(0.05)
        # severity = abs(-0.005 - 0.025) = 0.03
        assert severity == pytest.approx(0.03)

    def test_no_false_positives(self) -> None:
        prob_up = np.array([0.8, 0.7])
        targets = np.array([1, 1])
        forward_returns = np.array([0.05, 0.03])

        avg_fp, avg_tp, severity = compute_fp_severity(
            prob_up,
            targets,
            forward_returns,
            threshold=0.50,
            buy_threshold=0.025,
        )
        assert avg_fp == 0.0  # no FPs
        assert avg_tp == pytest.approx(0.04)

    def test_none_forward_returns(self) -> None:
        prob_up = np.array([0.8])
        targets = np.array([1])

        avg_fp, avg_tp, severity = compute_fp_severity(
            prob_up,
            targets,
            None,
            threshold=0.50,
            buy_threshold=0.025,
        )
        assert avg_fp == 0.0
        assert avg_tp == 0.0
        assert severity == 0.025


# --------------------------------------------------------------------------- #
# compute_auc_pr                                                               #
# --------------------------------------------------------------------------- #


class TestAucPr:
    def test_perfect_classifier(self) -> None:
        prob_up = np.array([0.9, 0.8, 0.1, 0.05])
        targets = np.array([1, 1, 0, 0])
        auc = compute_auc_pr(prob_up, targets)
        assert auc == pytest.approx(1.0)

    def test_random_classifier(self) -> None:
        rng = np.random.RandomState(42)
        prob_up = rng.rand(1000)
        targets = rng.randint(0, 2, 1000)
        auc = compute_auc_pr(prob_up, targets)
        # Random should be around the base rate
        assert 0.0 < auc < 1.0

    def test_single_class_returns_zero(self) -> None:
        prob_up = np.array([0.5, 0.6, 0.7])
        targets = np.array([0, 0, 0])
        auc = compute_auc_pr(prob_up, targets)
        assert auc == 0.0


# --------------------------------------------------------------------------- #
# PromotionEvalConfig                                                          #
# --------------------------------------------------------------------------- #


class TestPromotionEvalConfig:
    def test_from_dict_defaults(self) -> None:
        cfg = PromotionEvalConfig.from_dict({})
        assert cfg.primary_threshold == 0.65
        assert cfg.wf_window_size == 63
        assert cfg.stability_penalty == 1.5
        assert len(cfg.thresholds) == 7

    def test_from_dict_custom(self) -> None:
        cfg = PromotionEvalConfig.from_dict(
            {
                "evaluation": {"primary_threshold": 0.70, "min_recall": 0.20},
                "walk_forward": {"window_size": 42, "stability_penalty": 2.0},
                "ranking": {"tiebreak_margin": 0.02},
            }
        )
        assert cfg.primary_threshold == 0.70
        assert cfg.min_recall == 0.20
        assert cfg.wf_window_size == 42
        assert cfg.stability_penalty == 2.0
        assert cfg.tiebreak_margin == 0.02
