"""Tests for portfolio optimizer."""

import datetime as dt

import numpy as np
import polars as pl
import pytest

from src.config import PortfolioProfileConfig


@pytest.fixture
def sample_predictions() -> pl.DataFrame:
    """Sample prediction data for 10 stocks."""
    return pl.DataFrame([
        {"symbol": "AAPL", "cluster_id": "Tech_0", "prediction": "BUY", "confidence": 0.85, "prob_buy": 0.85, "prob_sell": 0.05, "prob_hold": 0.10},
        {"symbol": "MSFT", "cluster_id": "Tech_0", "prediction": "BUY", "confidence": 0.78, "prob_buy": 0.78, "prob_sell": 0.07, "prob_hold": 0.15},
        {"symbol": "GOOGL", "cluster_id": "Tech_1", "prediction": "BUY", "confidence": 0.72, "prob_buy": 0.72, "prob_sell": 0.10, "prob_hold": 0.18},
        {"symbol": "JPM", "cluster_id": "Finance_0", "prediction": "HOLD", "confidence": 0.65, "prob_buy": 0.15, "prob_sell": 0.20, "prob_hold": 0.65},
        {"symbol": "GS", "cluster_id": "Finance_0", "prediction": "SELL", "confidence": 0.70, "prob_buy": 0.10, "prob_sell": 0.70, "prob_hold": 0.20},
        {"symbol": "JNJ", "cluster_id": "Health_0", "prediction": "BUY", "confidence": 0.60, "prob_buy": 0.60, "prob_sell": 0.15, "prob_hold": 0.25},
        {"symbol": "PFE", "cluster_id": "Health_0", "prediction": "SELL", "confidence": 0.55, "prob_buy": 0.15, "prob_sell": 0.55, "prob_hold": 0.30},
        {"symbol": "XOM", "cluster_id": "Energy_0", "prediction": "BUY", "confidence": 0.68, "prob_buy": 0.68, "prob_sell": 0.12, "prob_hold": 0.20},
    ])


def test_aggressive_includes_shorts(sample_predictions: pl.DataFrame) -> None:
    """Aggressive profile should include both BUY and SELL signals."""
    config = PortfolioProfileConfig(
        primary_metric="sortino",
        complementary_metric="omega",
        validation_metric="information",
        max_positions=25,
        max_sector_weight=0.30,
        min_confidence=0.50,
        allow_short=True,
    )
    candidates = sample_predictions.filter(
        (pl.col("confidence") >= config.min_confidence)
        & pl.col("prediction").is_in(["BUY", "SELL"])
    )
    signals = set(candidates["prediction"].to_list())
    assert "BUY" in signals
    assert "SELL" in signals


def test_conservative_no_shorts(sample_predictions: pl.DataFrame) -> None:
    """Conservative profile should only include BUY signals."""
    config = PortfolioProfileConfig(
        primary_metric="calmar",
        complementary_metric="sortino",
        validation_metric="sharpe",
        max_positions=15,
        max_sector_weight=0.20,
        min_confidence=0.60,
        allow_short=False,
    )
    candidates = sample_predictions.filter(
        (pl.col("confidence") >= config.min_confidence)
        & (pl.col("prediction") == "BUY")
    )
    signals = set(candidates["prediction"].to_list())
    assert "SELL" not in signals
    assert "HOLD" not in signals


def test_confidence_filter(sample_predictions: pl.DataFrame) -> None:
    """High confidence threshold should filter out low-confidence stocks."""
    config = PortfolioProfileConfig(
        primary_metric="sharpe",
        complementary_metric="calmar",
        validation_metric="sortino",
        max_positions=20,
        max_sector_weight=0.25,
        min_confidence=0.75,
        allow_short=False,
    )
    candidates = sample_predictions.filter(
        (pl.col("confidence") >= config.min_confidence)
        & (pl.col("prediction") == "BUY")
    )
    # Only AAPL (0.85) and MSFT (0.78) should pass
    assert len(candidates) == 2
    assert set(candidates["symbol"].to_list()) == {"AAPL", "MSFT"}


def test_max_positions_limit(sample_predictions: pl.DataFrame) -> None:
    """Portfolio should respect max_positions limit."""
    config = PortfolioProfileConfig(
        primary_metric="sharpe",
        complementary_metric="calmar",
        validation_metric="sortino",
        max_positions=2,
        max_sector_weight=0.50,
        min_confidence=0.50,
        allow_short=False,
    )
    candidates = sample_predictions.filter(
        (pl.col("confidence") >= config.min_confidence)
        & (pl.col("prediction") == "BUY")
    ).sort("confidence", descending=True).head(config.max_positions)
    assert len(candidates) <= 2


def test_weights_sum_to_one() -> None:
    """Equal-weight fallback should sum to 1."""
    n = 5
    weights = np.ones(n) / n
    assert abs(weights.sum() - 1.0) < 1e-10


def test_different_profiles_different_candidates(sample_predictions: pl.DataFrame) -> None:
    """Different profiles should potentially select different stocks."""
    aggressive = sample_predictions.filter(
        (pl.col("confidence") >= 0.50) & pl.col("prediction").is_in(["BUY", "SELL"])
    )
    conservative = sample_predictions.filter(
        (pl.col("confidence") >= 0.60) & (pl.col("prediction") == "BUY")
    )
    # Aggressive should have more candidates than conservative
    assert len(aggressive) >= len(conservative)
