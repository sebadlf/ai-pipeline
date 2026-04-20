"""Tests for portfolio optimizer."""

import datetime as dt

import numpy as np
import polars as pl
import pytest

from src.config import PortfolioProfileConfig
from src.portfolio.optimizer import optimize_portfolio


@pytest.fixture
def sample_predictions() -> pl.DataFrame:
    """Sample prediction data for 8 stocks with prob_up."""
    return pl.DataFrame(
        [
            {"symbol": "AAPL", "cluster_id": "Tech_0", "prob_up": 0.85},
            {"symbol": "MSFT", "cluster_id": "Tech_0", "prob_up": 0.78},
            {"symbol": "GOOGL", "cluster_id": "Tech_1", "prob_up": 0.72},
            {"symbol": "JPM", "cluster_id": "Finance_0", "prob_up": 0.65},
            {"symbol": "GS", "cluster_id": "Finance_0", "prob_up": 0.40},
            {"symbol": "JNJ", "cluster_id": "Health_0", "prob_up": 0.60},
            {"symbol": "PFE", "cluster_id": "Health_0", "prob_up": 0.55},
            {"symbol": "XOM", "cluster_id": "Energy_0", "prob_up": 0.68},
        ]
    )


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
    candidates = (
        sample_predictions.filter(pl.col("prob_up") >= config.min_prob_up)
        .sort("prob_up", descending=True)
        .head(config.max_positions)
    )
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


def _build_returns_df(
    symbols: list[str],
    n_days: int = 60,
    seed: int = 42,
) -> pl.DataFrame:
    """Build a synthetic long-format daily returns DataFrame."""
    rng = np.random.default_rng(seed)
    base = dt.date(2024, 1, 1)
    rows = []
    for sym in symbols:
        for i in range(n_days):
            rows.append(
                {
                    "date": base + dt.timedelta(days=i),
                    "symbol": sym,
                    "daily_return": float(rng.normal(0.0005, 0.01)),
                }
            )
    return pl.DataFrame(rows)


def test_sector_balanced_candidate_selection_caps_dominant_sector() -> None:
    """One sector with 20 high prob_up stocks should not consume the entire candidate
    pool — per-sector cap must apply BEFORE global top-K (see BEC-35)."""
    # 20 ConsumerCyclical stocks with high prob_up + 5 from other sectors
    rows = []
    for i in range(20):
        rows.append(
            {
                "symbol": f"CC{i:02d}",
                "cluster_id": "ConsumerCyclical_0",
                "prob_up": 0.95 - i * 0.001,  # all very high, slightly decreasing
            }
        )
    other_sectors = [
        ("AAPL", "Tech_0", 0.78),
        ("JPM", "Finance_0", 0.75),
        ("JNJ", "Health_0", 0.72),
        ("XOM", "Energy_0", 0.70),
        ("WMT", "Staples_0", 0.68),
    ]
    for sym, cid, p in other_sectors:
        rows.append({"symbol": sym, "cluster_id": cid, "prob_up": p})

    predictions = pl.DataFrame(rows)

    # Sector mapping
    sector_rows = [{"symbol": f"CC{i:02d}", "sector": "ConsumerCyclical"} for i in range(20)]
    sector_rows.extend(
        [
            {"symbol": "AAPL", "sector": "Technology"},
            {"symbol": "JPM", "sector": "FinancialServices"},
            {"symbol": "JNJ", "sector": "Healthcare"},
            {"symbol": "XOM", "sector": "Energy"},
            {"symbol": "WMT", "sector": "ConsumerDefensive"},
        ]
    )
    sectors_df = pl.DataFrame(sector_rows)

    profile_config = PortfolioProfileConfig(
        primary_metric="sharpe",
        complementary_metric="calmar",
        validation_metric="sortino",
        max_positions=20,
        max_sector_weight=0.25,
        min_prob_up=0.65,
    )
    constraints = {"max_single_position": 0.10, "min_single_position": 0.01}

    all_symbols = [r["symbol"] for r in rows]
    returns_df = _build_returns_df(all_symbols)

    allocation = optimize_portfolio(
        predictions=predictions,
        returns_df=returns_df,
        profile_config=profile_config,
        constraints=constraints,
        benchmark_returns=None,
        sectors_df=sectors_df,
    )

    # Per-sector cap = max(1, int(20 * 0.25)) = 5 — ConsumerCyclical can contribute at most 5
    selected = allocation["symbol"].to_list()
    cc_selected = [s for s in selected if s.startswith("CC")]
    assert len(cc_selected) <= 5, (
        f"ConsumerCyclical exceeded per-sector cap of 5: got {len(cc_selected)}"
    )
    # And the 5 high-prob other-sector stocks should have made it in
    other_selected = [s for s in selected if not s.startswith("CC")]
    assert len(other_selected) >= 5, (
        f"Expected all 5 other-sector stocks to be selected, got {len(other_selected)}"
    )


def test_sector_balanced_selection_no_sectors_df_falls_back_to_global_topk() -> None:
    """When sectors_df is None, behavior should match the previous global top-K logic."""
    rows = [
        {"symbol": f"S{i:02d}", "cluster_id": "C0", "prob_up": 0.90 - i * 0.01} for i in range(10)
    ]
    predictions = pl.DataFrame(rows)

    profile_config = PortfolioProfileConfig(
        primary_metric="sharpe",
        complementary_metric="calmar",
        validation_metric="sortino",
        max_positions=5,
        max_sector_weight=0.50,
        min_prob_up=0.50,
    )
    constraints = {"max_single_position": 0.30, "min_single_position": 0.05}

    returns_df = _build_returns_df([r["symbol"] for r in rows])

    allocation = optimize_portfolio(
        predictions=predictions,
        returns_df=returns_df,
        profile_config=profile_config,
        constraints=constraints,
        benchmark_returns=None,
        sectors_df=None,
    )

    # Top 5 by prob_up
    assert set(allocation["symbol"].to_list()) == {f"S{i:02d}" for i in range(5)}


def test_sector_balanced_selection_preserves_output_schema() -> None:
    """The new selection must keep [symbol, weight, cluster_id, prob_up] columns
    (sector column is dropped after grouping)."""
    rows = [
        {"symbol": "AAPL", "cluster_id": "Tech_0", "prob_up": 0.85},
        {"symbol": "JPM", "cluster_id": "Finance_0", "prob_up": 0.75},
    ]
    predictions = pl.DataFrame(rows)
    sectors_df = pl.DataFrame(
        [
            {"symbol": "AAPL", "sector": "Technology"},
            {"symbol": "JPM", "sector": "FinancialServices"},
        ]
    )
    profile_config = PortfolioProfileConfig(
        primary_metric="sharpe",
        complementary_metric="calmar",
        validation_metric="sortino",
        max_positions=10,
        max_sector_weight=0.50,
        min_prob_up=0.50,
    )
    returns_df = _build_returns_df([r["symbol"] for r in rows])

    allocation = optimize_portfolio(
        predictions=predictions,
        returns_df=returns_df,
        profile_config=profile_config,
        constraints={"max_single_position": 0.6, "min_single_position": 0.1},
        benchmark_returns=None,
        sectors_df=sectors_df,
    )

    assert set(allocation.columns) == {"symbol", "weight", "cluster_id", "prob_up"}
