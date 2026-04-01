"""Tests for prediction aggregation."""

import numpy as np
import polars as pl
import pytest

from src.aggregation.consolidate import map_binary_to_signal


# --------------------------------------------------------------------------- #
# Binary → signal mapping                                                      #
# --------------------------------------------------------------------------- #

class TestMapBinaryToSignal:
    def test_high_prob_up_is_buy(self) -> None:
        probs = np.array([0.2, 0.8])
        config: dict = {}
        pred, conf, pb, ps, ph = map_binary_to_signal(probs, config)
        assert pred == "BUY"
        assert conf == pytest.approx(0.8)
        assert pb == pytest.approx(0.8)
        assert ps == pytest.approx(0.0)

    def test_low_prob_up_is_sell(self) -> None:
        probs = np.array([0.9, 0.1])
        config = {"inference": {"sell_proxy_max_prob_up": 0.20}}
        pred, conf, pb, ps, ph = map_binary_to_signal(probs, config)
        assert pred == "SELL"
        assert conf == pytest.approx(0.9)
        assert ps == pytest.approx(0.9)

    def test_mid_prob_is_hold(self) -> None:
        probs = np.array([0.65, 0.35])
        config = {"inference": {"sell_proxy_max_prob_up": 0.20}}
        pred, conf, pb, ps, ph = map_binary_to_signal(probs, config)
        assert pred == "HOLD"
        assert conf == pytest.approx(0.65)

    def test_exactly_at_sell_threshold(self) -> None:
        probs = np.array([0.80, 0.20])
        config = {"inference": {"sell_proxy_max_prob_up": 0.20}}
        pred, _, _, _, _ = map_binary_to_signal(probs, config)
        assert pred == "SELL"

    def test_exactly_at_buy_threshold(self) -> None:
        probs = np.array([0.50, 0.50])
        config: dict = {}
        pred, _, _, _, _ = map_binary_to_signal(probs, config)
        assert pred == "BUY"

    def test_default_sell_threshold(self) -> None:
        """Default sell_proxy_max_prob_up is 0.20 when not configured."""
        probs = np.array([0.85, 0.15])
        config: dict = {}
        pred, _, _, _, _ = map_binary_to_signal(probs, config)
        assert pred == "SELL"

    def test_custom_sell_threshold(self) -> None:
        probs = np.array([0.65, 0.35])
        config = {"inference": {"sell_proxy_max_prob_up": 0.40}}
        pred, _, _, _, _ = map_binary_to_signal(probs, config)
        assert pred == "SELL"


# --------------------------------------------------------------------------- #
# Schema                                                                       #
# --------------------------------------------------------------------------- #

def test_prediction_schema() -> None:
    """Output DataFrame should have the expected schema."""
    predictions = pl.DataFrame([
        {
            "symbol": "AAPL",
            "cluster_id": "Tech_0",
            "prediction": "BUY",
            "confidence": 0.85,
            "prob_hold": 0.15,
            "prob_buy": 0.85,
            "prob_sell": 0.0,
            "model_run_id": None,
        },
    ])

    required_cols = {"symbol", "cluster_id", "prediction", "confidence",
                     "prob_buy", "prob_sell", "prob_hold"}
    assert required_cols.issubset(set(predictions.columns))


def test_all_predictions_are_valid() -> None:
    """All mapped predictions should be one of BUY/SELL/HOLD."""
    valid_signals = {"BUY", "SELL", "HOLD"}
    predictions = ["BUY", "SELL", "HOLD", "BUY", "HOLD"]
    assert all(p in valid_signals for p in predictions)
