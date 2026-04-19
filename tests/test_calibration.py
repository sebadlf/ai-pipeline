"""Tests for temperature calibration and adaptive thresholds."""

import numpy as np
import torch

from src.evaluation.precision_eval import compute_adaptive_threshold

# --------------------------------------------------------------------------- #
# compute_adaptive_threshold tests                                             #
# --------------------------------------------------------------------------- #


class TestAdaptiveThreshold:
    """Tests for compute_adaptive_threshold."""

    def test_returns_base_when_signal_sufficient(self):
        """If enough predictions exceed base threshold with good precision, return base."""
        rng = np.random.RandomState(42)
        n = 1000
        # Generate well-separated probabilities
        targets = rng.randint(0, 2, n)
        prob_up = np.where(targets == 1, rng.uniform(0.6, 0.9, n), rng.uniform(0.2, 0.5, n))

        result = compute_adaptive_threshold(
            prob_up,
            targets,
            base_threshold=0.65,
            min_threshold=0.50,
        )
        assert result == 0.65

    def test_adapts_down_when_no_signal_at_base(self):
        """If no predictions exceed base threshold, adapt downward."""
        rng = np.random.RandomState(42)
        n = 1000
        targets = rng.randint(0, 2, n)
        # All probabilities below 0.60 — base=0.65 impossible
        prob_up = np.where(targets == 1, rng.uniform(0.50, 0.58, n), rng.uniform(0.30, 0.48, n))

        result = compute_adaptive_threshold(
            prob_up,
            targets,
            base_threshold=0.65,
            min_threshold=0.50,
        )
        assert result < 0.65
        assert result >= 0.50

    def test_returns_min_when_no_usable_threshold(self):
        """If no threshold works, return min_threshold."""
        n = 100
        targets = np.zeros(n, dtype=int)  # all NOT_UP
        prob_up = np.full(n, 0.3)  # all very low

        result = compute_adaptive_threshold(
            prob_up,
            targets,
            base_threshold=0.65,
            min_threshold=0.50,
        )
        assert result == 0.50

    def test_empty_input(self):
        """Empty arrays return min_threshold."""
        result = compute_adaptive_threshold(
            np.array([]),
            np.array([]),
            base_threshold=0.65,
            min_threshold=0.50,
        )
        assert result == 0.50

    def test_precision_requirement(self):
        """Threshold must achieve min_precision (not just signal count)."""
        rng = np.random.RandomState(42)
        n = 1000
        targets = np.zeros(n, dtype=int)  # all NOT_UP — no UP targets
        prob_up = rng.uniform(0.45, 0.70, n)  # many above 0.50 but precision=0

        result = compute_adaptive_threshold(
            prob_up,
            targets,
            base_threshold=0.65,
            min_threshold=0.50,
            min_precision=0.50,
        )
        # Should fall to min because precision is always 0 (no true positives)
        assert result == 0.50


# --------------------------------------------------------------------------- #
# Temperature calibration bounds tests                                          #
# --------------------------------------------------------------------------- #


class TestCalibrationBounds:
    """Test that calibrate_temperature respects bounds and composite objective."""

    def test_calibration_returns_tuple(self):
        """calibrate_temperature should return (float, dict)."""
        # We test via a mock model to avoid needing a full LSTMForecaster
        from unittest.mock import MagicMock

        # Create mock logits that produce well-separated probabilities
        logits = torch.randn(100, 2)
        targets = torch.randint(0, 2, (100,))

        model = MagicMock()
        model.eval = MagicMock()
        model.return_value = logits

        # Create a simple dataloader that yields one batch
        dataloader = [(torch.randn(100, 10, 5), targets)]

        from src.training.optimize import calibrate_temperature

        temp, diagnostics = calibrate_temperature(model, dataloader)

        assert isinstance(temp, float)
        assert 0.5 <= temp <= 2.5
        assert isinstance(diagnostics, dict)
        assert "pre_cal_prob_mean" in diagnostics
        assert "post_cal_prob_mean" in diagnostics
        assert "pre_cal_pct_above_060" in diagnostics
        assert "post_cal_pct_above_060" in diagnostics
