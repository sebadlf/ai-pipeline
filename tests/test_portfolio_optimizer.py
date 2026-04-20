"""Tests for portfolio optimizer."""

import datetime as dt

import numpy as np
import polars as pl
import pytest

from src.config import PortfolioProfileConfig
from src.portfolio.optimizer import _enforce_sector_cap, optimize_portfolio


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


def _profile_sector_weights(
    allocation: pl.DataFrame,
    sectors_df: pl.DataFrame,
) -> dict[str, float]:
    """Helper: total weight per sector for a single profile allocation."""
    merged = allocation.join(sectors_df, on="symbol", how="left").with_columns(
        pl.col("sector").fill_null("Unknown")
    )
    grouped = merged.group_by("sector").agg(pl.col("weight").sum().alias("total_weight"))
    return {row["sector"]: float(row["total_weight"]) for row in grouped.iter_rows(named=True)}


def _dominant_sector_predictions(
    dominant_sector: str,
    n_dominant: int = 25,
    n_other: int = 25,
    base_prob: float = 0.95,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Build predictions + sectors_df where ``n_dominant`` of the highest-prob_up
    candidates share one sector (50% of the high-prob universe)."""
    rows = []
    sector_rows = []
    # Dominant sector — highest prob_up stocks
    for i in range(n_dominant):
        sym = f"D{i:02d}"
        rows.append(
            {
                "symbol": sym,
                "cluster_id": f"{dominant_sector}_0",
                "prob_up": base_prob - i * 0.0005,
            }
        )
        sector_rows.append({"symbol": sym, "sector": dominant_sector})
    # Mix of other sectors at slightly lower prob_up
    other_sectors = [
        "Technology",
        "FinancialServices",
        "Healthcare",
        "Energy",
        "ConsumerDefensive",
        "RealEstate",
        "Utilities",
        "Industrials",
    ]
    per_sector = max(1, n_other // len(other_sectors))
    idx = 0
    for sec in other_sectors:
        for _j in range(per_sector):
            if idx >= n_other:
                break
            sym = f"O{idx:02d}"
            rows.append(
                {
                    "symbol": sym,
                    "cluster_id": f"{sec}_0",
                    "prob_up": 0.85 - idx * 0.001,
                }
            )
            sector_rows.append({"symbol": sym, "sector": sec})
            idx += 1
    return pl.DataFrame(rows), pl.DataFrame(sector_rows)


@pytest.mark.parametrize(
    ("profile_name", "max_positions", "max_sector_weight", "min_prob_up"),
    [
        ("aggressive", 25, 0.30, 0.60),
        ("moderate", 20, 0.25, 0.65),
        ("conservative", 15, 0.20, 0.70),
    ],
)
def test_profile_sector_cap_is_hard_invariant(
    profile_name: str,
    max_positions: int,
    max_sector_weight: float,
    min_prob_up: float,
) -> None:
    """With a dominant sector holding 50% of high-prob_up candidates, the optimizer
    must not allocate more than ``max_sector_weight`` to any single sector (BEC-40)."""
    predictions, sectors_df = _dominant_sector_predictions(
        dominant_sector="ConsumerCyclical",
        n_dominant=25,
        n_other=25,
    )

    profile_config = PortfolioProfileConfig(
        primary_metric="sharpe",
        complementary_metric="calmar",
        validation_metric="sortino",
        max_positions=max_positions,
        max_sector_weight=max_sector_weight,
        min_prob_up=min_prob_up,
    )
    constraints = {"max_single_position": 0.10, "min_single_position": 0.01}
    returns_df = _build_returns_df([r["symbol"] for r in predictions.iter_rows(named=True)])

    allocation = optimize_portfolio(
        predictions=predictions,
        returns_df=returns_df,
        profile_config=profile_config,
        constraints=constraints,
        benchmark_returns=None,
        sectors_df=sectors_df,
    )

    assert not allocation.is_empty(), f"{profile_name} produced an empty allocation"
    # Weights sum to 1
    assert abs(float(allocation["weight"].sum()) - 1.0) < 1e-6
    # No sector exceeds its cap (with small numerical tolerance)
    sector_totals = _profile_sector_weights(allocation, sectors_df)
    for sector, total in sector_totals.items():
        assert total <= max_sector_weight + 1e-6, (
            f"{profile_name} allocates {total:.4f} to {sector}, exceeds cap {max_sector_weight}"
        )


def test_sector_cap_holds_in_equal_weight_fallback() -> None:
    """When returns are insufficient and the optimizer falls back to equal-weight,
    the projection step must still enforce the per-profile sector cap (BEC-40)."""
    # Dominant sector has 10 candidates + 5 other sectors with 4 each — enough
    # total symbols/sector coverage so the candidate pool is feasible under
    # (max_positions=15, max_single_position=0.10, max_sector_weight=0.20).
    rows = [
        {"symbol": f"D{i:02d}", "cluster_id": "ConsumerCyclical_0", "prob_up": 0.95 - i * 0.001}
        for i in range(10)
    ]
    other_sectors = ["Technology", "Healthcare", "Energy", "RealEstate", "Utilities"]
    for s_idx, sec in enumerate(other_sectors):
        for j in range(4):
            rows.append(
                {
                    "symbol": f"{sec[:2].upper()}{s_idx}{j}",
                    "cluster_id": f"{sec}_0",
                    "prob_up": 0.88 - s_idx * 0.005 - j * 0.001,
                }
            )
    predictions = pl.DataFrame(rows)
    sector_rows = [{"symbol": f"D{i:02d}", "sector": "ConsumerCyclical"} for i in range(10)]
    for s_idx, sec in enumerate(other_sectors):
        for j in range(4):
            sector_rows.append({"symbol": f"{sec[:2].upper()}{s_idx}{j}", "sector": sec})
    sectors_df = pl.DataFrame(sector_rows)

    profile_config = PortfolioProfileConfig(
        primary_metric="calmar",
        complementary_metric="sortino",
        validation_metric="sharpe",
        max_positions=15,
        max_sector_weight=0.20,
        min_prob_up=0.70,
    )
    constraints = {"max_single_position": 0.10, "min_single_position": 0.01}

    # Empty returns_df -> optimizer must hit the "not enough data" fallback branch
    empty_returns = pl.DataFrame(
        schema={"date": pl.Date, "symbol": pl.Utf8, "daily_return": pl.Float64}
    )

    allocation = optimize_portfolio(
        predictions=predictions,
        returns_df=empty_returns,
        profile_config=profile_config,
        constraints=constraints,
        benchmark_returns=None,
        sectors_df=sectors_df,
    )

    assert not allocation.is_empty()
    assert abs(float(allocation["weight"].sum()) - 1.0) < 1e-6
    sector_totals = _profile_sector_weights(allocation, sectors_df)
    assert sector_totals["ConsumerCyclical"] <= 0.20 + 1e-6, (
        f"ConsumerCyclical exceeded 0.20 cap in equal-weight fallback: "
        f"got {sector_totals['ConsumerCyclical']:.4f}"
    )


def test_enforce_sector_cap_is_idempotent_when_already_feasible() -> None:
    """If weights already satisfy the cap, projection should leave them (numerically) unchanged."""
    symbols = ["A", "B", "C", "D"]
    sector_map = {"A": "Tech", "B": "Tech", "C": "Finance", "D": "Health"}
    weights = np.array([0.15, 0.10, 0.40, 0.35])  # Tech=0.25, all <= 0.50 cap
    out = _enforce_sector_cap(
        weights=weights,
        symbols=symbols,
        sector_map=sector_map,
        max_sector_weight=0.50,
        min_pos=0.01,
        max_pos=0.50,
    )
    np.testing.assert_allclose(out, weights, atol=1e-8)


def test_enforce_sector_cap_redistributes_excess() -> None:
    """Weights over-concentrated in one sector should be redistributed to others."""
    symbols = ["A", "B", "C", "D"]
    sector_map = {"A": "Tech", "B": "Tech", "C": "Finance", "D": "Health"}
    # Tech=0.70 — must be scaled down to 0.40 cap; C/D must absorb the excess
    weights = np.array([0.35, 0.35, 0.15, 0.15])
    out = _enforce_sector_cap(
        weights=weights,
        symbols=symbols,
        sector_map=sector_map,
        max_sector_weight=0.40,
        min_pos=0.05,
        max_pos=0.50,
    )
    assert abs(out.sum() - 1.0) < 1e-6
    tech_total = out[0] + out[1]
    assert tech_total <= 0.40 + 1e-6
    # Finance and Health should have grown
    assert out[2] > 0.15
    assert out[3] > 0.15


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
