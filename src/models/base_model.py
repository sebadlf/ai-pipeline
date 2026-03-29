"""PyTorch Lightning model definitions for trading strategies."""

from __future__ import annotations

import lightning as L
import torch
import torch.nn as nn


class LSTMForecaster(L.LightningModule):
    """LSTM-based time series forecaster with regularization for calibrated outputs.

    Args:
        input_size: Number of input features per timestep.
        hidden_size: LSTM hidden dimension.
        num_layers: Number of stacked LSTM layers.
        dropout: Dropout rate between LSTM layers.
        learning_rate: Optimizer learning rate.
        weight_decay: L2 regularization strength.
        label_smoothing: Smoothing factor to prevent overconfident predictions.
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 128,
        num_layers: int = 2,
        dropout: float = 0.3,
        learning_rate: float = 0.001,
        weight_decay: float = 0.0,
        label_smoothing: float = 0.05,
    ) -> None:
        super().__init__()
        self.save_hyperparameters()
        self.learning_rate = learning_rate
        self.label_smoothing = label_smoothing

        self.input_norm = nn.LayerNorm(input_size)

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )

        self.head = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, 1),
        )

        self.loss_fn = nn.BCEWithLogitsLoss()

    def _smooth_labels(self, y: torch.Tensor) -> torch.Tensor:
        """Apply label smoothing: 0 -> eps, 1 -> 1-eps."""
        eps = self.label_smoothing
        return y * (1 - 2 * eps) + eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input tensor of shape (batch, seq_len, features).

        Returns:
            Logits of shape (batch, 1).
        """
        x = self.input_norm(x)
        lstm_out, _ = self.lstm(x)
        last_hidden = lstm_out[:, -1, :]
        return self.head(last_hidden)

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Return probability of positive class (price up >= threshold)."""
        return torch.sigmoid(self(x)).squeeze(-1)

    def _step(self, batch: tuple[torch.Tensor, torch.Tensor], stage: str) -> torch.Tensor:
        x, y = batch
        logits = self(x).squeeze(-1)

        if stage == "train":
            loss = self.loss_fn(logits, self._smooth_labels(y))
        else:
            loss = self.loss_fn(logits, y)

        probs = torch.sigmoid(logits)
        preds = (probs >= 0.5).float()
        acc = (preds == y).float().mean()

        self.log(f"{stage}_loss", loss, prog_bar=True)
        self.log(f"{stage}_acc", acc, prog_bar=True)

        if stage == "val":
            self.log("val_mean_prob", probs.mean(), prog_bar=True)

        return loss

    def training_step(self, batch: tuple[torch.Tensor, torch.Tensor], batch_idx: int) -> torch.Tensor:
        return self._step(batch, "train")

    def validation_step(self, batch: tuple[torch.Tensor, torch.Tensor], batch_idx: int) -> torch.Tensor:
        return self._step(batch, "val")

    def test_step(self, batch: tuple[torch.Tensor, torch.Tensor], batch_idx: int) -> torch.Tensor:
        return self._step(batch, "test")

    def configure_optimizers(self) -> dict:
        optimizer = torch.optim.AdamW(
            self.parameters(),
            lr=self.learning_rate,
            weight_decay=self.hparams.get("weight_decay", 0.0),
        )
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="max", factor=0.5, patience=5, min_lr=1e-6
        )
        return {
            "optimizer": optimizer,
            "lr_scheduler": {"scheduler": scheduler, "monitor": "val_acc"},
        }
