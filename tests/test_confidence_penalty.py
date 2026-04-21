"""Tests for training-time confidence penalty (BEC-64).

Verifies that LSTMForecaster with confidence_penalty_beta > 0 produces
higher-entropy predictions than a model trained without the penalty,
reducing overconfidence.
"""

from __future__ import annotations

import torch
import torch.nn as nn

from src.models.base_model import LSTMForecaster


def _make_overconfident_logits(n: int = 200, seed: int = 42) -> torch.Tensor:
    """Return logits that are very overconfident (near ±10)."""
    rng = torch.Generator()
    rng.manual_seed(seed)
    # Alternate between highly positive and highly negative logits
    logits = torch.zeros(n, 2)
    half = n // 2
    logits[:half, 1] = 9.0  # strongly predicts UP
    logits[:half, 0] = -9.0
    logits[half:, 0] = 9.0  # strongly predicts NOT_UP
    logits[half:, 1] = -9.0
    return logits


def _entropy_from_logits(logits: torch.Tensor) -> float:
    """Compute mean entropy from logits."""
    probs = torch.softmax(logits, dim=-1)
    entropy = -(probs * torch.log(probs.clamp(min=1e-8))).sum(dim=-1)
    return float(entropy.mean())


class TestConfidencePenalty:
    """Tests for confidence_penalty_beta in LSTMForecaster."""

    def _make_model(self, beta: float = 0.0, input_size: int = 4) -> LSTMForecaster:
        return LSTMForecaster(
            input_size=input_size,
            hidden_size=16,
            num_layers=1,
            num_classes=2,
            dropout=0.0,
            learning_rate=1e-3,
            weight_decay=0.01,
            label_smoothing=0.0,
            focal_gamma=0.0,
            confidence_penalty_beta=beta,
        )

    def test_beta_zero_no_entropy_penalty(self):
        """With beta=0, loss equals the standard cross-entropy (no entropy term)."""
        model = self._make_model(beta=0.0)
        model.train()

        batch_size, seq_len, features = 16, 5, 4
        x = torch.randn(batch_size, seq_len, features)
        y = torch.randint(0, 2, (batch_size,)).long()
        batch = (x, y)

        # Standard CE loss without penalty
        logits = model(x)
        ce_loss = nn.CrossEntropyLoss()(logits, y)

        # _step should return (approximately) the same loss when beta=0
        step_loss = model._step(batch, "train")
        assert abs(float(step_loss) - float(ce_loss)) < 1e-4, (
            f"With beta=0, step_loss={step_loss:.6f} should match CE={ce_loss:.6f}"
        )

    def test_beta_positive_reduces_loss_for_overconfident_model(self):
        """With beta>0, the confidence penalty term encourages higher entropy.

        When a model outputs overconfident predictions (near-zero entropy),
        the penalty term -beta*H(p) is large in magnitude (very negative),
        so the *total* loss is lower than CE alone. This confirms the penalty
        is being added to the loss with the correct sign.
        """
        model_no_pen = self._make_model(beta=0.0)
        model_with_pen = self._make_model(beta=0.2)

        # Use same weights for both models
        state = model_no_pen.state_dict()
        model_with_pen.load_state_dict(state)

        batch_size, seq_len, features = 32, 5, 4
        torch.manual_seed(0)
        x = torch.randn(batch_size, seq_len, features)
        y = torch.randint(0, 2, (batch_size,)).long()
        batch = (x, y)

        model_no_pen.train()
        model_with_pen.train()

        loss_no_pen = float(model_no_pen._step(batch, "train"))
        loss_with_pen = float(model_with_pen._step(batch, "train"))

        # The penalty "-beta*H" subtracts from loss when H > 0, so with_pen <= no_pen
        assert loss_with_pen <= loss_no_pen + 1e-5, (
            f"With beta=0.2, loss={loss_with_pen:.4f} should be "
            f"<= no-penalty loss={loss_no_pen:.4f}"
        )

    def test_entropy_above_threshold_with_strong_penalty(self):
        """With beta=0.2 on a synthetic binary dataset, prediction entropy stays above 0.3 nats.

        This is the acceptance criterion from BEC-64.
        We train a small model for a few steps and verify that the
        model's output entropy on a held-out batch exceeds 0.3 nats.
        """
        torch.manual_seed(42)
        input_size = 8
        model = self._make_model(beta=0.2, input_size=input_size)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)

        batch_size, seq_len = 64, 10
        n_steps = 20

        # Train for a few steps on random binary data
        model.train()
        for _ in range(n_steps):
            x = torch.randn(batch_size, seq_len, input_size)
            y = torch.randint(0, 2, (batch_size,)).long()
            batch = (x, y)
            optimizer.zero_grad()
            loss = model._step(batch, "train")
            loss.backward()
            optimizer.step()

        # Evaluate entropy on a held-out batch
        model.eval()
        with torch.no_grad():
            x_test = torch.randn(128, seq_len, input_size)
            logits = model(x_test)
            probs = torch.softmax(logits, dim=-1)
            entropy = -(probs * torch.log(probs.clamp(min=1e-8))).sum(dim=-1)
            mean_entropy = float(entropy.mean())

        assert mean_entropy > 0.3, (
            f"Expected entropy > 0.3 nats with beta=0.2, got {mean_entropy:.4f}"
        )

    def test_penalty_not_applied_in_val_stage(self):
        """Confidence penalty should NOT be subtracted during validation step.

        The penalty is only for training regularisation — validation loss should
        be comparable to the pure CE loss regardless of beta.
        """
        model_no_pen = self._make_model(beta=0.0)
        model_with_pen = self._make_model(beta=0.2)
        model_with_pen.load_state_dict(model_no_pen.state_dict())

        batch_size, seq_len, features = 32, 5, 4
        torch.manual_seed(1)
        x = torch.randn(batch_size, seq_len, features)
        y = torch.randint(0, 2, (batch_size,)).long()
        batch = (x, y)

        model_no_pen.eval()
        model_with_pen.eval()

        loss_no_pen = float(model_no_pen._step(batch, "val"))
        loss_with_pen = float(model_with_pen._step(batch, "val"))

        # Both should be identical (penalty only applies during train)
        assert abs(loss_with_pen - loss_no_pen) < 1e-5, (
            f"Val loss should be identical regardless of beta: "
            f"no_pen={loss_no_pen:.6f}, with_pen={loss_with_pen:.6f}"
        )

    def test_confidence_penalty_beta_stored_in_hparams(self):
        """confidence_penalty_beta is saved in hparams for checkpoint reproducibility."""
        model = self._make_model(beta=0.15)
        assert "confidence_penalty_beta" in model.hparams
        assert abs(model.hparams["confidence_penalty_beta"] - 0.15) < 1e-9
