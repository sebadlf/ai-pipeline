"""PyTorch Lightning model definitions for trading strategies."""

from __future__ import annotations

import lightning as L
import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalLoss(nn.Module):
    """Focal Loss for handling class imbalance.

    Down-weights well-classified examples, focusing training on hard negatives.
    Combined with class weights for double imbalance correction.

    Args:
        gamma: Focusing parameter. Higher = more focus on hard examples.
        weight: Per-class weights tensor.
        label_smoothing: Label smoothing factor.
    """

    def __init__(
        self,
        gamma: float = 2.0,
        weight: torch.Tensor | None = None,
        label_smoothing: float = 0.0,
    ) -> None:
        super().__init__()
        self.gamma = gamma
        self.register_buffer("weight", weight)
        self.label_smoothing = label_smoothing

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce_loss = F.cross_entropy(
            logits, targets, weight=self.weight, reduction="none",
            label_smoothing=self.label_smoothing,
        )
        pt = torch.exp(-ce_loss)
        focal_loss = ((1 - pt) ** self.gamma) * ce_loss
        return focal_loss.mean()


class LSTMForecaster(L.LightningModule):
    """LSTM with self-attention for ternary classification (BUY/SELL/HOLD).

    Architecture: LayerNorm → LSTM → MultiHeadAttention → Residual → MLP Head.

    Args:
        input_size: Number of input features per timestep.
        hidden_size: LSTM hidden dimension.
        num_layers: Number of stacked LSTM layers.
        num_classes: Number of output classes (3: HOLD=0, BUY=1, SELL=2).
        dropout: Dropout rate between LSTM layers.
        learning_rate: Optimizer learning rate.
        weight_decay: L2 regularization strength.
        label_smoothing: Smoothing factor to prevent overconfident predictions.
        class_weights: Optional per-class weights for loss function.
        num_attention_heads: Number of attention heads (0 to disable attention).
        focal_gamma: Focal loss gamma (0 to use standard CrossEntropy).
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 128,
        num_layers: int = 2,
        num_classes: int = 3,
        dropout: float = 0.3,
        learning_rate: float = 0.001,
        weight_decay: float = 0.0,
        label_smoothing: float = 0.05,
        class_weights: list[float] | None = None,
        num_attention_heads: int = 4,
        focal_gamma: float = 2.0,
    ) -> None:
        super().__init__()
        self.save_hyperparameters()
        self.learning_rate = learning_rate
        self.num_classes = num_classes

        self.input_norm = nn.LayerNorm(input_size)

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )

        # Projection for residual connection (input_size -> hidden_size)
        self.residual_proj = nn.Linear(input_size, hidden_size)

        # Multi-head self-attention over LSTM output sequence
        self.use_attention = num_attention_heads > 0
        if self.use_attention:
            self.attention = nn.MultiheadAttention(
                embed_dim=hidden_size,
                num_heads=num_attention_heads,
                dropout=dropout,
                batch_first=True,
            )
            self.attn_norm = nn.LayerNorm(hidden_size)

        self.head = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, num_classes),
        )

        # Loss: Focal Loss with class weights (handles imbalance)
        weight_tensor = torch.tensor(class_weights, dtype=torch.float32) if class_weights else None
        if focal_gamma > 0:
            self.loss_fn = FocalLoss(
                gamma=focal_gamma, weight=weight_tensor,
                label_smoothing=label_smoothing,
            )
        else:
            self.loss_fn = nn.CrossEntropyLoss(
                weight=weight_tensor, label_smoothing=label_smoothing,
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input tensor of shape (batch, seq_len, features).

        Returns:
            Logits of shape (batch, num_classes).
        """
        x_normed = self.input_norm(x)
        lstm_out, _ = self.lstm(x_normed)

        # Residual connection: project input to hidden_size and add to LSTM output
        residual = self.residual_proj(x_normed)
        lstm_out = lstm_out + residual

        if self.use_attention:
            # Self-attention over temporal dimension
            attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
            lstm_out = self.attn_norm(lstm_out + attn_out)

        # Use last timestep for classification
        last_hidden = lstm_out[:, -1, :]
        return self.head(last_hidden)

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Return class probabilities [prob_hold, prob_buy, prob_sell]."""
        return torch.softmax(self(x), dim=-1)

    def _step(self, batch: tuple[torch.Tensor, torch.Tensor], stage: str) -> torch.Tensor:
        x, y = batch
        y = y.long()
        logits = self(x)
        loss = self.loss_fn(logits, y)

        preds = logits.argmax(dim=-1)
        acc = (preds == y).float().mean()

        self.log(f"{stage}_loss", loss, prog_bar=True)
        self.log(f"{stage}_acc", acc, prog_bar=True)

        if stage == "val":
            probs = torch.softmax(logits, dim=-1)
            self.log("val_mean_prob_buy", probs[:, 1].mean(), prog_bar=True)
            self.log("val_mean_prob_sell", probs[:, 2].mean(), prog_bar=True)

            # Per-class accuracy
            for cls_idx, cls_name in enumerate(["hold", "buy", "sell"]):
                mask = y == cls_idx
                if mask.sum() > 0:
                    cls_acc = (preds[mask] == y[mask]).float().mean()
                    self.log(f"val_acc_{cls_name}", cls_acc)

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
        scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
            optimizer, T_0=20, T_mult=2, eta_min=1e-6,
        )
        return {
            "optimizer": optimizer,
            "lr_scheduler": {"scheduler": scheduler, "interval": "epoch"},
        }
