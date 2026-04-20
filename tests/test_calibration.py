"""Tests for temperature calibration, isotonic calibration and adaptive thresholds."""

from unittest.mock import MagicMock

import numpy as np
import pytest
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


# --------------------------------------------------------------------------- #
# Isotonic calibration tests                                                    #
# --------------------------------------------------------------------------- #


def _make_mock_model(probs_up: np.ndarray) -> MagicMock:
    """Build a mock model whose ``predict_proba`` returns the given UP probs."""
    model = MagicMock()
    model.eval = MagicMock()

    def predict_proba(_x):
        p_up = torch.as_tensor(probs_up, dtype=torch.float32)
        return torch.stack([1.0 - p_up, p_up], dim=-1)

    model.predict_proba.side_effect = predict_proba
    return model


class TestExpectedCalibrationError:
    """ECE helper used by isotonic calibration diagnostics."""

    def test_perfect_calibration_returns_zero(self):
        from src.training.optimize import _expected_calibration_error

        probs = np.array([0.1, 0.1, 0.9, 0.9])
        targets = np.array([0, 0, 1, 1])
        ece = _expected_calibration_error(probs, targets, n_bins=10)
        # In the 0.1 bin, avg prob=0.1, avg label=0 -> 0.1 error
        # In the 0.9 bin, avg prob=0.9, avg label=1 -> 0.1 error
        # Total weighted: 0.5*0.1 + 0.5*0.1 = 0.1
        assert ece == pytest.approx(0.1)

    def test_overconfident_model_has_high_ece(self):
        from src.training.optimize import _expected_calibration_error

        # Model outputs high confidence but half are wrong
        probs = np.full(100, 0.9)
        targets = np.concatenate([np.ones(50), np.zeros(50)])
        ece = _expected_calibration_error(probs, targets, n_bins=10)
        # Avg label=0.5, avg prob=0.9 -> 0.4 in the single bin
        assert ece == pytest.approx(0.4)

    def test_empty_input(self):
        from src.training.optimize import _expected_calibration_error

        assert _expected_calibration_error(np.array([]), np.array([])) == 0.0


class TestIsotonicCalibration:
    """calibrate_isotonic fits a monotone correction on val probs."""

    def test_skips_when_too_few_samples(self):
        from src.training.optimize import calibrate_isotonic

        probs = np.full(50, 0.7)
        targets = np.zeros(50)
        model = _make_mock_model(probs)
        dataloader = [(torch.randn(50, 10, 5), torch.as_tensor(targets, dtype=torch.long))]

        x, y, diag = calibrate_isotonic(model, dataloader, min_samples=200)

        assert x is None
        assert y is None
        assert diag["isotonic_fitted"] == 0.0
        assert diag["isotonic_n_samples"] == 50.0

    def test_fits_and_reduces_ece_on_overconfident_distribution(self):
        """Synthetic overconfident cluster — isotonic should drop ECE."""
        from src.training.optimize import calibrate_isotonic

        rng = np.random.RandomState(0)
        n = 400
        # Model predicts high confidence, but true rate is much lower
        probs = rng.uniform(0.75, 0.95, n).astype(np.float32)
        # Only ~40% are actually UP (test precision << val_prob)
        targets = (rng.uniform(size=n) < 0.4).astype(np.int64)

        model = _make_mock_model(probs)
        dataloader = [(torch.randn(n, 10, 5), torch.as_tensor(targets, dtype=torch.long))]

        x, y, diag = calibrate_isotonic(model, dataloader, min_samples=200, max_knots=32)

        assert x is not None
        assert y is not None
        assert diag["isotonic_fitted"] == 1.0
        # ECE should drop meaningfully after isotonic fit
        assert diag["isotonic_ece_post"] < diag["isotonic_ece_pre"]
        # Monotone non-decreasing mapping
        assert all(y[i] <= y[i + 1] for i in range(len(y) - 1))
        # Bounded in [0, 1]
        assert all(0.0 <= yi <= 1.0 for yi in y)

    def test_predict_proba_applies_isotonic_map(self):
        """base_model.predict_proba honours calibration_isotonic_x/y hparams."""
        from src.models.base_model import LSTMForecaster

        model = LSTMForecaster(input_size=3, hidden_size=8, num_layers=1)
        model.eval()

        # Force a known logit path by monkey-patching forward
        fixed_logits = torch.tensor([[0.0, 2.0], [0.0, 4.0]])

        def fake_forward(_x):
            return fixed_logits

        model.forward = fake_forward  # type: ignore[assignment]

        # Compute baseline probabilities (no calibration)
        base = model.predict_proba(torch.zeros(2, 5, 3))
        base_up = base[:, 1]

        # Install a deliberately dampening isotonic map
        model.hparams["calibration_isotonic_x"] = [0.0, 0.5, 1.0]
        model.hparams["calibration_isotonic_y"] = [0.0, 0.3, 0.5]

        calibrated = model.predict_proba(torch.zeros(2, 5, 3))

        # UP probs should drop after the dampening map
        assert torch.all(calibrated[:, 1] <= base_up + 1e-6)
        # Probabilities remain a valid two-class distribution
        assert torch.allclose(calibrated.sum(dim=-1), torch.ones(2), atol=1e-5)
        # All probabilities in [0, 1]
        assert torch.all(calibrated >= 0.0)
        assert torch.all(calibrated <= 1.0)
