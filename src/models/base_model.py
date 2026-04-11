"""PyTorch Lightning model definitions for trading strategies."""

from __future__ import annotations

import lightning as L
import torch
import torch.nn as nn
import torch.nn.functional as F

# Activation registry
_ACTIVATIONS: dict[str, type[nn.Module]] = {
    "gelu": nn.GELU,
    "silu": nn.SiLU,
    "mish": nn.Mish,
}


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
    """LSTM with self-attention for binary classification (UP/NOT_UP).

    Architecture: InputDropout → LSTM → MultiHeadAttention → Residual → MLP Head.

    Args:
        input_size: Number of input features per timestep.
        hidden_size: LSTM hidden dimension.
        num_layers: Number of stacked LSTM layers.
        num_classes: Number of output classes (2: NOT_UP=0, UP=1).
        dropout: Dropout rate between LSTM layers and in MLP head.
        learning_rate: Optimizer learning rate.
        weight_decay: L2 regularization strength.
        label_smoothing: Smoothing factor to prevent overconfident predictions.
        class_weights: Optional per-class weights for loss function.
        num_attention_heads: Number of attention heads (0 to disable attention).
        focal_gamma: Focal loss gamma (0 to use standard CrossEntropy).
        feature_names: Feature names stored in checkpoint for inference reproducibility.
        optimizer_name: Optimizer type ("adamw", "radam", "sgd").
        scheduler_factor: ReduceLROnPlateau factor.
        scheduler_patience: ReduceLROnPlateau patience (epochs).
        bidirectional: Whether to use bidirectional LSTM.
        head_hidden_ratio: MLP head hidden layer size as fraction of hidden_size.
        activation: Activation function in MLP head ("gelu", "silu", "mish").
        input_dropout: Dropout applied to input features before LayerNorm.
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 128,
        num_layers: int = 2,
        num_classes: int = 2,
        dropout: float = 0.3,
        learning_rate: float = 0.001,
        weight_decay: float = 0.0,
        label_smoothing: float = 0.05,
        class_weights: list[float] | None = None,
        num_attention_heads: int = 4,
        focal_gamma: float = 2.0,
        feature_names: list[str] | None = None,
        optimizer_name: str = "adamw",
        scheduler_factor: float = 0.5,
        scheduler_patience: int = 5,
        bidirectional: bool = False,
        head_hidden_ratio: float = 0.5,
        activation: str = "gelu",
        input_dropout: float = 0.0,
    ) -> None:
        super().__init__()
        self.save_hyperparameters()
        self.learning_rate = learning_rate
        self.num_classes = num_classes

        # Input regularization (data arrives pre-normalized from normalize.py)
        self.input_drop = nn.Dropout(input_dropout) if input_dropout > 0 else nn.Identity()

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
            bidirectional=bidirectional,
        )

        # Effective hidden size doubles when bidirectional
        effective_hidden = hidden_size * 2 if bidirectional else hidden_size

        # Projection for residual connection (input_size -> effective_hidden)
        self.residual_proj = nn.Linear(input_size, effective_hidden)

        # Multi-head self-attention over LSTM output sequence
        self.use_attention = num_attention_heads > 0
        if self.use_attention:
            self.attention = nn.MultiheadAttention(
                embed_dim=effective_hidden,
                num_heads=num_attention_heads,
                dropout=dropout,
                batch_first=True,
            )
            self.attn_norm = nn.LayerNorm(effective_hidden)

        # MLP classification head
        head_hidden = max(1, int(effective_hidden * head_hidden_ratio))
        act_cls = _ACTIVATIONS.get(activation, nn.GELU)
        self.head = nn.Sequential(
            nn.LayerNorm(effective_hidden),
            nn.Linear(effective_hidden, head_hidden),
            act_cls(),
            nn.Dropout(dropout),
            nn.Linear(head_hidden, num_classes),
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
        x_normed = self.input_drop(x)
        lstm_out, _ = self.lstm(x_normed)

        # Residual connection: project input to effective_hidden and add to LSTM output
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
        """Return class probabilities."""
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

        if stage in ("val", "train"):
            up_preds = preds == 1
            up_targets = y == 1
            tp = (up_preds & up_targets).float().sum()
            fp = (up_preds & ~up_targets).float().sum()
            fn = (~up_preds & up_targets).float().sum()
            denom_prec = tp + fp
            denom_rec = tp + fn
            precision_up = tp / denom_prec if denom_prec > 0 else torch.zeros(1, device=x.device).squeeze()
            recall_up = tp / denom_rec if denom_rec > 0 else torch.zeros(1, device=x.device).squeeze()
            self.log(f"{stage}_precision_up", precision_up, prog_bar=(stage == "val"))
            self.log(f"{stage}_recall_up", recall_up, prog_bar=(stage == "val"))

        if stage == "val":
            probs = torch.softmax(logits, dim=-1)
            self.log("val_mean_prob_up", probs[:, 1].mean(), prog_bar=True)

            # Per-class accuracy
            for cls_idx, cls_name in enumerate(["not_up", "up"]):
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
        optimizer_name = self.hparams.get("optimizer_name", "adamw")
        weight_decay = self.hparams.get("weight_decay", 0.0)

        if optimizer_name == "radam":
            optimizer = torch.optim.RAdam(
                self.parameters(), lr=self.learning_rate, weight_decay=weight_decay,
            )
        elif optimizer_name == "sgd":
            optimizer = torch.optim.SGD(
                self.parameters(), lr=self.learning_rate, weight_decay=weight_decay,
                momentum=0.9, nesterov=True,
            )
        elif optimizer_name == "lion":
            from lion_pytorch import Lion
            optimizer = Lion(
                self.parameters(), lr=self.learning_rate, weight_decay=weight_decay,
            )
        else:  # adamw (default)
            optimizer = torch.optim.AdamW(
                self.parameters(), lr=self.learning_rate, weight_decay=weight_decay,
            )

        factor = self.hparams.get("scheduler_factor", 0.5)
        patience = self.hparams.get("scheduler_patience", 5)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=factor, patience=patience, min_lr=1e-6,
        )
        return {
            "optimizer": optimizer,
            "lr_scheduler": {"scheduler": scheduler, "monitor": "val_loss", "interval": "epoch"},
        }
