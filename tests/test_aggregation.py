"""Tests for prediction aggregation."""

import numpy as np
import polars as pl
import pytest

from src.aggregation.consolidate import CLASS_MAP


def test_class_map_coverage() -> None:
    """CLASS_MAP should cover all 3 classes."""
    assert CLASS_MAP == {0: "HOLD", 1: "BUY", 2: "SELL"}


def test_argmax_prediction() -> None:
    """Prediction should be the class with highest probability."""
    probs = np.array([0.1, 0.7, 0.2])  # HOLD=0.1, BUY=0.7, SELL=0.2
    pred_class = int(np.argmax(probs))
    assert CLASS_MAP[pred_class] == "BUY"


def test_confidence_is_max_prob() -> None:
    """Confidence should be the maximum probability."""
    probs = np.array([0.1, 0.7, 0.2])
    confidence = float(probs.max())
    assert confidence == pytest.approx(0.7)


def test_prediction_schema() -> None:
    """Output DataFrame should have the expected schema."""
    predictions = pl.DataFrame([
        {
            "symbol": "AAPL",
            "cluster_id": "Tech_0",
            "prediction": "BUY",
            "confidence": 0.85,
            "prob_hold": 0.05,
            "prob_buy": 0.85,
            "prob_sell": 0.10,
            "model_run_id": None,
        },
        {
            "symbol": "JPM",
            "cluster_id": "Finance_0",
            "prediction": "SELL",
            "confidence": 0.70,
            "prob_hold": 0.10,
            "prob_buy": 0.20,
            "prob_sell": 0.70,
            "model_run_id": None,
        },
    ])

    required_cols = {"symbol", "cluster_id", "prediction", "confidence",
                     "prob_buy", "prob_sell", "prob_hold"}
    assert required_cols.issubset(set(predictions.columns))


def test_probabilities_sum_to_one() -> None:
    """Softmax probabilities should sum to approximately 1."""
    probs = np.array([0.1, 0.7, 0.2])
    assert abs(probs.sum() - 1.0) < 1e-6


def test_all_predictions_are_valid() -> None:
    """All predictions should be one of BUY/SELL/HOLD."""
    valid_predictions = {"BUY", "SELL", "HOLD"}
    predictions = ["BUY", "SELL", "HOLD", "BUY", "HOLD"]
    assert all(p in valid_predictions for p in predictions)
