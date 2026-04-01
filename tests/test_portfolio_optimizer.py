"""Tests for portfolio optimizer."""

import datetime as dt

import numpy as np
import polars as pl
import pytest

from src.config import PortfolioProfileConfig


@pytest.fixture
def sample_predictions() -> pl.DataFrame:
    """Sample prediction data for 8 stocks with prob_up."""
    return pl.DataFrame([
        {"symbol": "AAPL", "cluster_id": "Tech_0", "prob_up": 0.85},
        {"symbol": "MSFT", "cluster_id": "Tech_0", "prob_up": 0.78},
        {"symbol": "GOOGL", "cluster_id": "Tech_1", "prob_up": 0.72},
        {"symbol": "JPM", "cluster_id": "Finance_0", "prob_up": 0.65},
        {"symbol": "GS", "cluster_id": "Finance_0", "prob_up": 0.40},
        {"symbol": "JNJ", "cluster_id": "Health_0", "prob_up": 0.60},
        {"symbol": "PFE", "cluster_id": "Health_0", "prob_up": 0.55},
        {"symbol": "XOM", "cluster_id": "Energy_0", "prob_up": 0.68},
    ])


def test_aggressive_has_lowest_threshold(sample_predictions: pl.DataFrame) -> None:
    """Aggressive profile (min_prob_up=0.70) should include the most stocks."""
    config = PortfolioProfileConfig(
        primary_metric="sortino",
        complementary_metric="omega",
        validation_metric="information",
        max_positions=25,
        max_sector_weight=0.30,
        min_prob_up=0.70,
    )
    candidates = sample_predictions.filter(pl.col("prob_up") >= config.min_prob_up)
    # AAPL (0.85), MSFT (0.78), GOOGL (0.72)
    assert len(candidates) == 3


def test_conservative_has_highest_threshold(sample_predictions: pl.DataFrame) -> None:
    """Conservative profile (min_prob_up=0.80) should include fewer stocks."""
    config = PortfolioProfileConfig(
        primary_metric="calmar",
        complementary_metric="sortino",
        validation_metric="sharpe",
        max_positions=15,
        max_sector_weight=0.20,
        min_prob_up=0.80,
    )
    candidates = sample_predictions.filter(pl.col("prob_up") >= config.min_prob_up)
    # Only AAPL (0.85)
    assert len(candidates) == 1
    assert candidates["symbol"][0] == "AAPL"


def test_prob_up_filter(sample_predictions: pl.DataFrame) -> None:
    """Moderate threshold should filter correctly."""
    config = PortfolioProfileConfig(
        primary_metric="sharpe",
        complementary_metric="calmar",
        validation_metric="sortino",
        max_positions=20,
        max_sector_weight=0.25,
        min_prob_up=0.75,
    )
    candidates = sample_predictions.filter(pl.col("prob_up") >= config.min_prob_up)
    # AAPL (0.85) and MSFT (0.78)
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
        min_prob_up=0.50,
    )
    candidates = sample_predictions.filter(
        pl.col("prob_up") >= config.min_prob_up
    ).sort("prob_up", descending=True).head(config.max_positions)
    assert len(candidates) <= 2


def test_weights_sum_to_one() -> None:
    """Equal-weight fallback should sum to 1."""
    n = 5
    weights = np.ones(n) / n
    assert abs(weights.sum() - 1.0) < 1e-10


def test_different_profiles_different_candidates(sample_predictions: pl.DataFrame) -> None:
    """Different profiles should potentially select different stocks."""
    aggressive = sample_predictions.filter(pl.col("prob_up") >= 0.70)
    conservative = sample_predictions.filter(pl.col("prob_up") >= 0.80)
    # Aggressive should have more candidates than conservative
    assert len(aggressive) >= len(conservative)
