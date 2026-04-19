"""Tests for prediction aggregation."""

import polars as pl
import pytest

# --------------------------------------------------------------------------- #
# Schema                                                                       #
# --------------------------------------------------------------------------- #


def test_prediction_schema() -> None:
    """Output DataFrame should have the expected schema."""
    predictions = pl.DataFrame(
        [
            {
                "symbol": "AAPL",
                "cluster_id": "Tech_0",
                "prob_up": 0.85,
                "model_run_id": None,
            },
        ]
    )

    required_cols = {"symbol", "cluster_id", "prob_up"}
    assert required_cols.issubset(set(predictions.columns))


def test_prob_up_values_are_valid() -> None:
    """All prob_up values should be in [0, 1]."""
    predictions = pl.DataFrame(
        [
            {"symbol": "AAPL", "cluster_id": "Tech_0", "prob_up": 0.85},
            {"symbol": "MSFT", "cluster_id": "Tech_0", "prob_up": 0.42},
            {"symbol": "XOM", "cluster_id": "Energy_0", "prob_up": 0.71},
        ]
    )
    assert predictions["prob_up"].min() >= 0.0
    assert predictions["prob_up"].max() <= 1.0


# --------------------------------------------------------------------------- #
# resolve_feature_cols                                                         #
# --------------------------------------------------------------------------- #


def _make_model(input_size: int, feature_names: list[str] | None = None):
    """Create a minimal LSTMForecaster for testing."""
    from src.models.base_model import LSTMForecaster

    return LSTMForecaster(
        input_size=input_size,
        hidden_size=8,
        num_layers=1,
        num_classes=2,
        feature_names=feature_names,
    )


def _make_df(cols: list[str]) -> pl.DataFrame:
    """Create a single-row DataFrame with given columns plus metadata."""
    data = {"symbol": ["AAPL"], "date": ["2024-01-01"], "target": [1]}
    for c in cols:
        data[c] = [1.0]
    return pl.DataFrame(data)


def test_resolve_feature_cols_from_checkpoint() -> None:
    """When model has feature_names, use those exactly."""
    from src.aggregation.consolidate import resolve_feature_cols

    names = ["f1", "f2", "f3"]
    model = _make_model(input_size=3, feature_names=names)
    df = _make_df(["f1", "f2", "f3", "f4", "f5"])
    config = {"feature_selection": {"enabled": False}}

    result = resolve_feature_cols(model, df, config)
    assert result == names


def test_resolve_feature_cols_missing_column_raises() -> None:
    """When model needs a column not in DataFrame, raise ValueError."""
    from src.aggregation.consolidate import resolve_feature_cols

    model = _make_model(input_size=3, feature_names=["f1", "f2", "missing"])
    df = _make_df(["f1", "f2"])
    config = {"feature_selection": {"enabled": False}}

    with pytest.raises(ValueError, match="features not in DataFrame"):
        resolve_feature_cols(model, df, config)


def test_resolve_feature_cols_no_feature_names_no_manifest_raises() -> None:
    """Without feature_names or manifest, raise ValueError requiring retrain."""
    from src.aggregation.consolidate import resolve_feature_cols

    model = _make_model(input_size=3)
    df = _make_df(["f1", "f2", "f3"])
    config = {"feature_selection": {"enabled": False}}

    with pytest.raises(ValueError, match="Retrain models"):
        resolve_feature_cols(model, df, config)
