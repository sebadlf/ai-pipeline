"""Tests for precision-focused model evaluation."""

import datetime as dt
from unittest.mock import MagicMock

import numpy as np
import pytest
import torch

from src.config import PromotionEvalConfig
from src.evaluation.precision_eval import (
    compute_adaptive_threshold,
    compute_auc_pr,
    compute_fp_severity,
    compute_percentile_recall,
    compute_precision_at_thresholds,
    compute_top_k_recall,
    compute_walk_forward_precision,
    evaluate_model,
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


# --------------------------------------------------------------------------- #
# compute_adaptive_threshold                                                    #
# --------------------------------------------------------------------------- #


class TestComputeAdaptiveThreshold:
    def test_returns_base_when_sufficient_signals(self) -> None:
        """When base threshold already has >=5% signal rate, return it unchanged."""
        # 20% of samples are >=0.65 → sufficient, and precision is good
        prob_up = np.array([0.9, 0.8, 0.7, 0.66, 0.3, 0.2, 0.1, 0.1, 0.1, 0.1])
        targets = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0])
        threshold = compute_adaptive_threshold(
            prob_up,
            targets,
            base_threshold=0.65,
            min_threshold=0.50,
            min_signal_pct=0.05,
            min_precision=0.50,
        )
        assert threshold == 0.65

    def test_falls_back_when_no_signals_at_base(self) -> None:
        """When zero signals at base threshold, find a lower usable one."""
        # All probs between 0.50-0.59 — none reach 0.65
        prob_up = np.array([0.58, 0.57, 0.56, 0.55, 0.54, 0.53, 0.52, 0.51, 0.50, 0.50])
        targets = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
        threshold = compute_adaptive_threshold(
            prob_up,
            targets,
            base_threshold=0.65,
            min_threshold=0.50,
            min_signal_pct=0.05,
            min_precision=0.50,
        )
        # Should fall back below base_threshold since nothing reaches 0.65
        assert threshold < 0.65
        assert threshold >= 0.50

    def test_returns_min_threshold_when_no_viable_threshold(self) -> None:
        """Returns min_threshold as floor when nothing viable is found."""
        prob_up = np.array([0.1, 0.2, 0.3])
        targets = np.array([0, 0, 0])
        threshold = compute_adaptive_threshold(
            prob_up,
            targets,
            base_threshold=0.65,
            min_threshold=0.50,
            min_signal_pct=0.05,
            min_precision=0.50,
        )
        assert threshold == 0.50

    def test_returns_min_threshold_on_empty_input(self) -> None:
        threshold = compute_adaptive_threshold(
            np.array([]),
            np.array([]),
            base_threshold=0.65,
            min_threshold=0.50,
        )
        assert threshold == 0.50

    def test_low_signal_pct_triggers_fallback_finds_lower_threshold(self) -> None:
        """When signal rate <5% at base, adaptive search finds a workable lower threshold.

        This is the core BEC-51 scenario: post-isotonic-calibration models that compress
        probabilities below the nominal primary threshold.
        """
        rng = np.random.RandomState(7)
        # Simulate calibrated model: most probs 0.50-0.63, very few above 0.65
        compressed = rng.uniform(0.50, 0.63, 95)  # 95 samples below threshold
        above = rng.uniform(0.65, 0.70, 5)  # 5 samples at 0.65-0.70 (only 5%)
        prob_up = np.concatenate([above, compressed])
        targets = np.concatenate([np.ones(5), rng.randint(0, 2, 95)])

        # At 0.65: 5/100 = 5%, exactly the boundary — stays at 0.65
        threshold_at_boundary = compute_adaptive_threshold(
            prob_up,
            targets,
            base_threshold=0.65,
            min_threshold=0.50,
            min_signal_pct=0.05,
            min_precision=0.50,
        )
        # With exactly 5% signals at 0.65, it stays at 0.65 (meets the floor)
        assert threshold_at_boundary == 0.65

        # Now with only 1 sample above 0.65 (1%), triggers fallback
        prob_up2 = np.concatenate([rng.uniform(0.65, 0.70, 1), rng.uniform(0.50, 0.63, 99)])
        targets2 = np.concatenate([[1], rng.randint(0, 2, 99)])
        threshold_below_floor = compute_adaptive_threshold(
            prob_up2,
            targets2,
            base_threshold=0.65,
            min_threshold=0.50,
            min_signal_pct=0.05,
            min_precision=0.50,
        )
        # Should search down and find a threshold with >=5% signals
        assert threshold_below_floor < 0.65
        assert threshold_below_floor >= 0.50


# --------------------------------------------------------------------------- #
# Adaptive threshold in evaluate_model (BEC-51)                               #
# --------------------------------------------------------------------------- #


class TestEvaluateModelAdaptiveThreshold:
    """Verify that evaluate_model uses adaptive threshold when signal rate <5%.

    We test the internal logic by checking that _ADAPTIVE_MIN_SIGNAL_PCT = 0.05
    is the boundary: models with <5% signal rate at primary trigger the adaptive
    search, while models with >=5% do not.
    """

    def _make_mock_model(self, prob_up: np.ndarray):
        """Return a lightweight mock that emits fixed prob_up values from val pass."""
        model = MagicMock()
        model.eval = MagicMock()

        # Build a single-batch dataloader-like object
        n = len(prob_up)
        probs_tensor = torch.zeros(n, 2)
        probs_tensor[:, 1] = torch.tensor(prob_up, dtype=torch.float32)
        probs_tensor[:, 0] = 1 - probs_tensor[:, 1]
        targets_tensor = torch.zeros(n, dtype=torch.long)

        model.predict_proba = MagicMock(return_value=probs_tensor)

        # A minimal iterable that yields one (x, y) batch
        batch = (torch.zeros(n, 10, 5), targets_tensor)
        dataloader = [batch]

        return model, dataloader

    def test_adaptive_threshold_fires_when_signal_pct_below_5pct(self) -> None:
        """BEC-51: signal rate <5% at primary → adaptive threshold is used."""
        # 100 samples, only 2 above 0.65 (2% < 5%)
        rng = np.random.RandomState(42)
        prob_up = np.concatenate(
            [
                np.array([0.67, 0.66]),  # 2 above primary (2%)
                rng.uniform(0.50, 0.64, 98),  # 98 below primary
            ]
        )
        model, dataloader = self._make_mock_model(prob_up)

        eval_config = PromotionEvalConfig(
            thresholds=[0.50, 0.55, 0.60, 0.65],
            primary_threshold=0.65,
            min_recall=0.10,
            min_signals_per_window=3,
            wf_window_size=5,
            wf_step_size=2,
            max_std_ratio=0.50,
            stability_penalty=1.0,
            tiebreak_margin=0.01,
        )
        sample_dates = np.array(
            [dt.date(2024, 1, 1) + dt.timedelta(days=i) for i in range(100)],
            dtype="datetime64[D]",
        )

        result = evaluate_model(
            model=model,
            val_dataloader=dataloader,
            eval_config=eval_config,
            sample_dates=sample_dates,
            adaptive_threshold=True,
        )
        # effective_threshold should have been lowered below 0.65
        assert result.effective_threshold < 0.65

    def test_adaptive_threshold_does_not_fire_when_signal_pct_above_5pct(self) -> None:
        """When signal rate >=5% at primary, effective_threshold stays at primary."""
        # 100 samples, 10 above 0.65 (10% >= 5%)
        rng = np.random.RandomState(42)
        prob_up = np.concatenate(
            [
                rng.uniform(0.65, 0.90, 10),  # 10 above primary (10%)
                rng.uniform(0.30, 0.64, 90),  # 90 below
            ]
        )
        model, dataloader = self._make_mock_model(prob_up)

        eval_config = PromotionEvalConfig(
            thresholds=[0.50, 0.55, 0.60, 0.65],
            primary_threshold=0.65,
            min_recall=0.10,
            min_signals_per_window=3,
            wf_window_size=5,
            wf_step_size=2,
            max_std_ratio=0.50,
            stability_penalty=1.0,
            tiebreak_margin=0.01,
        )
        sample_dates = np.array(
            [dt.date(2024, 1, 1) + dt.timedelta(days=i) for i in range(100)],
            dtype="datetime64[D]",
        )

        result = evaluate_model(
            model=model,
            val_dataloader=dataloader,
            eval_config=eval_config,
            sample_dates=sample_dates,
            adaptive_threshold=True,
        )
        # effective_threshold should remain at the primary (0.65)
        assert result.effective_threshold == pytest.approx(0.65)


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

    def test_from_dict_deprecated_alias_min_recall_at_primary_threshold(self) -> None:
        """BEC-66: old key maps to min_recall with a deprecation warning."""
        cfg = PromotionEvalConfig.from_dict(
            {"evaluation": {"min_recall_at_primary_threshold": 0.15}}
        )
        assert cfg.min_recall == 0.15

    def test_from_dict_new_key_wins_over_deprecated_alias(self) -> None:
        """BEC-66: when both keys present, min_recall takes precedence."""
        cfg = PromotionEvalConfig.from_dict(
            {
                "evaluation": {
                    "min_recall": 0.12,
                    "min_recall_at_primary_threshold": 0.30,
                }
            }
        )
        assert cfg.min_recall == 0.12


# --------------------------------------------------------------------------- #
# Threshold-aware min_recall filter (BEC-57)                                  #
# --------------------------------------------------------------------------- #


class TestThresholdAwareMinRecall:
    """Verify that the min_recall filter scales proportionally when the adaptive
    threshold lowers effective_threshold below primary_threshold (BEC-57)."""

    def _make_mock_model(self, prob_up: np.ndarray):
        """Return a lightweight mock that emits fixed prob_up values."""
        model = MagicMock()
        model.eval = MagicMock()

        n = len(prob_up)
        probs_tensor = torch.zeros(n, 2)
        probs_tensor[:, 1] = torch.tensor(prob_up, dtype=torch.float32)
        probs_tensor[:, 0] = 1 - probs_tensor[:, 1]
        targets_tensor = torch.zeros(n, dtype=torch.long)

        model.predict_proba = MagicMock(return_value=probs_tensor)
        batch = (torch.zeros(n, 10, 5), targets_tensor)
        dataloader = [batch]
        return model, dataloader

    def test_adjusted_min_recall_proportional_to_threshold_ratio(self) -> None:
        """adjusted_min_recall = min_recall * (effective_threshold / primary_threshold)."""
        rng = np.random.RandomState(0)
        # Build compressed-distribution model: only 1% above 0.65, bulk at 0.50-0.60
        prob_up = np.concatenate([rng.uniform(0.65, 0.70, 1), rng.uniform(0.50, 0.60, 99)])
        model, dataloader = self._make_mock_model(prob_up)

        eval_config = PromotionEvalConfig(
            thresholds=[0.50, 0.55, 0.60, 0.65],
            primary_threshold=0.65,
            min_recall=0.10,
            min_signals_per_window=2,
            wf_window_size=5,
            wf_step_size=2,
            max_std_ratio=0.50,
            stability_penalty=1.0,
            tiebreak_margin=0.01,
            recall_metric="absolute_threshold",  # BEC-57 legacy mode
        )
        sample_dates = np.array(
            [dt.date(2024, 1, 1) + dt.timedelta(days=i) for i in range(100)],
            dtype="datetime64[D]",
        )

        result = evaluate_model(
            model=model,
            val_dataloader=dataloader,
            eval_config=eval_config,
            sample_dates=sample_dates,
            adaptive_threshold=True,
        )
        # Adaptive threshold should have fired (only 1% above 0.65)
        assert result.effective_threshold < 0.65
        # adjusted_min_recall must be proportionally scaled
        expected = eval_config.min_recall * (
            result.effective_threshold / eval_config.primary_threshold
        )
        assert result.adjusted_min_recall == pytest.approx(expected)

    def test_adjusted_min_recall_unchanged_when_no_adaptive_threshold(self) -> None:
        """When effective_threshold == primary_threshold, adjusted_min_recall is unchanged."""
        rng = np.random.RandomState(1)
        # 20% of samples above 0.65 → adaptive threshold stays at 0.65
        prob_up = np.concatenate([rng.uniform(0.65, 0.90, 20), rng.uniform(0.30, 0.64, 80)])
        model, dataloader = self._make_mock_model(prob_up)

        eval_config = PromotionEvalConfig(
            thresholds=[0.50, 0.55, 0.60, 0.65],
            primary_threshold=0.65,
            min_recall=0.10,
            min_signals_per_window=2,
            wf_window_size=5,
            wf_step_size=2,
            max_std_ratio=0.50,
            stability_penalty=1.0,
            tiebreak_margin=0.01,
            recall_metric="absolute_threshold",  # BEC-57 legacy mode
        )
        sample_dates = np.array(
            [dt.date(2024, 1, 1) + dt.timedelta(days=i) for i in range(100)],
            dtype="datetime64[D]",
        )

        result = evaluate_model(
            model=model,
            val_dataloader=dataloader,
            eval_config=eval_config,
            sample_dates=sample_dates,
            adaptive_threshold=True,
        )
        assert result.effective_threshold == pytest.approx(0.65)
        assert result.adjusted_min_recall == pytest.approx(0.10)

    def test_lowered_threshold_allows_borderline_recall_to_pass(self) -> None:
        """BEC-57 scenario: recall=0.08 at effective_threshold=0.50 should pass
        when adjusted_min_recall = 0.10 * (0.50/0.65) ≈ 0.077."""
        # 100 samples: 50 above threshold=0.50, of which 4 are true UP (targets=1)
        # Base rate: 50 positives in dataset → recall = 4/50 = 0.08
        n = 100
        n_positive = 50
        prob_up = np.concatenate(
            [
                np.full(50, 0.55),  # signals above 0.50 (below 0.65)
                np.full(50, 0.40),  # below threshold
            ]
        )
        targets = np.zeros(n, dtype=int)
        targets[:4] = 1  # 4 true positives out of 50 positives in dataset
        # Fill remaining positives at positions 60-109 (below threshold)
        targets[50 : 50 + (n_positive - 4)] = 1

        model = MagicMock()
        model.eval = MagicMock()
        probs_tensor = torch.zeros(n, 2)
        probs_tensor[:, 1] = torch.tensor(prob_up, dtype=torch.float32)
        probs_tensor[:, 0] = 1 - probs_tensor[:, 1]
        targets_tensor = torch.tensor(targets, dtype=torch.long)
        model.predict_proba = MagicMock(return_value=probs_tensor)
        dataloader = [(torch.zeros(n, 10, 5), targets_tensor)]

        eval_config = PromotionEvalConfig(
            thresholds=[0.50, 0.55, 0.60, 0.65],
            primary_threshold=0.65,
            min_recall=0.10,
            min_signals_per_window=2,
            wf_window_size=5,
            wf_step_size=2,
            max_std_ratio=0.99,  # permissive stability to isolate recall filter
            stability_penalty=0.0,
            tiebreak_margin=0.01,
            max_val_test_gap=1.0,  # disable generalization filter
            recall_metric="absolute_threshold",  # BEC-57 legacy mode
        )
        sample_dates = np.array(
            [dt.date(2024, 1, 1) + dt.timedelta(days=i) for i in range(n)],
            dtype="datetime64[D]",
        )

        result = evaluate_model(
            model=model,
            val_dataloader=dataloader,
            eval_config=eval_config,
            sample_dates=sample_dates,
            adaptive_threshold=True,
        )
        # effective_threshold must have been lowered (only ~0% signals at 0.65)
        assert result.effective_threshold < 0.65
        # adjusted_min_recall < 0.10 (scaled proportionally)
        assert result.adjusted_min_recall < 0.10
        # recall at effective_threshold = 4/50 = 0.08, which should now exceed
        # the adjusted floor and NOT trigger failed_recall
        assert result.recall_at_primary == pytest.approx(4 / 50)
        assert result.elimination_stage != "failed_recall", (
            f"expected recall filter to pass but got stage={result.elimination_stage}, "
            f"recall={result.recall_at_primary:.4f}, "
            f"adjusted_min_recall={result.adjusted_min_recall:.4f}"
        )


# --------------------------------------------------------------------------- #
# compute_top_k_recall and compute_percentile_recall (BEC-62)                 #
# --------------------------------------------------------------------------- #


class TestTopKRecall:
    def test_basic_top_k_recall(self) -> None:
        """Top-3 out of 10 predictions; 2 true UPs in top set → recall = 2/3."""
        prob_up = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05])
        targets = np.array([1, 1, 0, 0, 0, 0, 0, 0, 1, 0])  # 3 positives
        # k = max(1, round(0.30 * 10)) = 3 → top-3 by prob: idx 0,1,2 → targets 1,1,0 → 2 TPs
        recall = compute_top_k_recall(prob_up, targets, k_fraction=0.30)
        assert recall == pytest.approx(2 / 3)

    def test_all_positives_in_top_k(self) -> None:
        """When all UP labels land in the top-K set, recall = 1.0."""
        prob_up = np.array([0.9, 0.8, 0.1, 0.05])
        targets = np.array([1, 1, 0, 0])
        recall = compute_top_k_recall(prob_up, targets, k_fraction=0.50)
        assert recall == pytest.approx(1.0)

    def test_no_positives_returns_zero(self) -> None:
        prob_up = np.array([0.9, 0.8, 0.7])
        targets = np.array([0, 0, 0])
        assert compute_top_k_recall(prob_up, targets) == 0.0

    def test_empty_arrays_return_zero(self) -> None:
        assert compute_top_k_recall(np.array([]), np.array([])) == 0.0

    def test_nonzero_when_absolute_recall_is_zero(self) -> None:
        """Core BEC-62 scenario: absolute-threshold recall=0 but top-K recall > 0.

        Construct a case where all probs are below a hard threshold (e.g. 0.65),
        making absolute recall = 0.00, but the top-K set contains UP labels,
        so top-K recall = 0.30.
        """
        # 10 samples, all probs compressed to [0.50, 0.60] — never reach 0.65
        prob_up = np.array([0.60, 0.58, 0.56, 0.54, 0.52, 0.50, 0.50, 0.50, 0.50, 0.50])
        targets = np.array([1, 1, 1, 0, 0, 0, 0, 0, 0, 0])  # 3 UPs

        # Absolute-threshold recall at 0.65: 0 signals → recall = 0.0
        _, recall_abs, _ = compute_precision_at_thresholds(prob_up, targets, [0.65])
        assert recall_abs[0.65] == pytest.approx(0.0)

        # Top-K recall at k=30%: top-3 predictions = [0.60, 0.58, 0.56] → targets [1,1,1]
        recall_topk = compute_top_k_recall(prob_up, targets, k_fraction=0.30)
        assert recall_topk == pytest.approx(1.0)  # all 3 UPs are in top-3

    def test_filter_accepts_candidate_with_top_k_recall_above_min(self) -> None:
        """BEC-62 acceptance criterion: top-K recall > min_recall allows promotion
        even when absolute-threshold recall is 0.00."""
        n = 100
        # All probs below the minimum adaptive threshold (0.50) so that
        # absolute-threshold recall is definitively 0.00 regardless of adaptive search.
        rng = np.random.RandomState(42)
        prob_up = rng.uniform(0.40, 0.49, n)
        # 10 UPs all in the top-10% by probability
        sorted_idx = np.argsort(prob_up)[::-1]
        targets = np.zeros(n, dtype=int)
        targets[sorted_idx[:10]] = 1  # top-10 predictions are true UPs

        model = MagicMock()
        model.eval = MagicMock()
        probs_tensor = torch.zeros(n, 2)
        probs_tensor[:, 1] = torch.tensor(prob_up, dtype=torch.float32)
        probs_tensor[:, 0] = 1 - probs_tensor[:, 1]
        targets_tensor = torch.tensor(targets, dtype=torch.long)
        model.predict_proba = MagicMock(return_value=probs_tensor)
        dataloader = [(torch.zeros(n, 10, 5), targets_tensor)]

        eval_config = PromotionEvalConfig(
            thresholds=[0.50, 0.55, 0.60, 0.65],
            primary_threshold=0.65,
            min_recall=0.10,  # 10% recall floor
            min_signals_per_window=2,
            wf_window_size=5,
            wf_step_size=2,
            max_std_ratio=0.99,  # permissive to isolate recall filter
            stability_penalty=0.0,
            tiebreak_margin=0.01,
            max_val_test_gap=1.0,  # disable generalization filter
            recall_metric="top_k",
            recall_top_k_fraction=0.10,  # top-10% = 10 predictions = 10 UPs → recall=1.0
        )
        sample_dates = np.array(
            [dt.date(2024, 1, 1) + dt.timedelta(days=i) for i in range(n)],
            dtype="datetime64[D]",
        )

        result = evaluate_model(
            model=model,
            val_dataloader=dataloader,
            eval_config=eval_config,
            sample_dates=sample_dates,
            adaptive_threshold=True,
        )

        # Absolute recall at 0.65 must be 0
        assert result.recall_at_primary == pytest.approx(0.0)
        # rank_recall (top-K) must be high
        assert result.rank_recall > 0.10
        # Filter 2 must NOT trigger failed_recall
        assert result.elimination_stage != "failed_recall", (
            f"Top-K recall={result.rank_recall:.3f} should have cleared the filter "
            f"but elimination_stage={result.elimination_stage}"
        )


class TestPercentileRecall:
    def test_basic_percentile_recall(self) -> None:
        """Predictions above p80 contain 2 out of 3 UPs → recall ≈ 0.67."""
        prob_up = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
        targets = np.array([1, 1, 0, 1, 0])  # 3 UPs
        # p80 cutoff: np.quantile([0.5,0.6,0.7,0.8,0.9], 0.8) = 0.82
        # above 0.82: only 0.9 → 1 TP → recall = 1/3
        recall = compute_percentile_recall(prob_up, targets, percentile=0.80)
        assert recall == pytest.approx(1 / 3)

    def test_no_positives_returns_zero(self) -> None:
        prob_up = np.array([0.9, 0.8, 0.7])
        targets = np.array([0, 0, 0])
        assert compute_percentile_recall(prob_up, targets) == 0.0

    def test_empty_arrays_return_zero(self) -> None:
        assert compute_percentile_recall(np.array([]), np.array([])) == 0.0

    def test_nonzero_when_absolute_recall_is_zero(self) -> None:
        """Percentile recall > 0 even when all probs are below hard threshold."""
        prob_up = np.array([0.60, 0.58, 0.56, 0.54, 0.52, 0.50, 0.50, 0.50, 0.50, 0.50])
        targets = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])  # 2 UPs

        # Absolute recall at 0.65: 0.0
        _, recall_abs, _ = compute_precision_at_thresholds(prob_up, targets, [0.65])
        assert recall_abs[0.65] == pytest.approx(0.0)

        # Percentile recall at p80: should be > 0 because the UPs have highest probs
        recall_pct = compute_percentile_recall(prob_up, targets, percentile=0.80)
        assert recall_pct > 0.0
