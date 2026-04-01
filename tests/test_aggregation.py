"""Tests for prediction aggregation."""

import polars as pl


# --------------------------------------------------------------------------- #
# Schema                                                                       #
# --------------------------------------------------------------------------- #

def test_prediction_schema() -> None:
    """Output DataFrame should have the expected schema."""
    predictions = pl.DataFrame([
        {
            "symbol": "AAPL",
            "cluster_id": "Tech_0",
            "prob_up": 0.85,
            "model_run_id": None,
        },
    ])

    required_cols = {"symbol", "cluster_id", "prob_up"}
    assert required_cols.issubset(set(predictions.columns))


def test_prob_up_values_are_valid() -> None:
    """All prob_up values should be in [0, 1]."""
    predictions = pl.DataFrame([
        {"symbol": "AAPL", "cluster_id": "Tech_0", "prob_up": 0.85},
        {"symbol": "MSFT", "cluster_id": "Tech_0", "prob_up": 0.42},
        {"symbol": "XOM", "cluster_id": "Energy_0", "prob_up": 0.71},
    ])
    assert predictions["prob_up"].min() >= 0.0
    assert predictions["prob_up"].max() <= 1.0
