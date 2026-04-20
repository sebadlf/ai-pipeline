"""Integration / unit tests for the BEC-44 stock-preservation invariant.

These tests cover:

1. The ``stock_audit`` helper itself (unit).
2. ``fill_nulls`` from ``src.features.technical`` preserving symbols whose
   critical columns are all-null instead of dropping them.
3. ``compute_clustering_features`` padding short-history symbols rather than
   skipping them silently.
4. ``_run_inference_core`` (aggregation) producing a prediction row for
   every clustered symbol even when history is shorter than ``seq_len``.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import polars as pl
import pytest
import torch

from src.aggregation.consolidate import _run_inference_core
from src.features.stock_audit import StockDiscardedError, audit_symbols
from src.features.technical import fill_nulls

# ---------------------------------------------------------------------------
# stock_audit helper
# ---------------------------------------------------------------------------


def test_audit_symbols_passes_when_all_preserved(capsys):
    n_in, n_out, missing = audit_symbols("unit-stage", ["AAPL", "MSFT"], ["AAPL", "MSFT"])
    captured = capsys.readouterr().out
    assert n_in == 2
    assert n_out == 2
    assert missing == set()
    assert "stage=unit-stage" in captured
    assert "symbols_in=2" in captured
    assert "symbols_out=2" in captured


def test_audit_symbols_raises_when_symbol_dropped():
    with pytest.raises(StockDiscardedError) as exc_info:
        audit_symbols("unit-stage", ["AAPL", "MSFT"], ["AAPL"])
    assert "MSFT" in str(exc_info.value)


def test_audit_symbols_skip_raise_returns_missing(capsys):
    n_in, n_out, missing = audit_symbols(
        "unit-stage",
        ["AAPL", "MSFT"],
        ["AAPL"],
        raise_on_missing=False,
    )
    assert missing == {"MSFT"}
    assert n_in == 2
    assert n_out == 1
    captured = capsys.readouterr().out
    assert "missing=1" in captured


# ---------------------------------------------------------------------------
# technical.fill_nulls
# ---------------------------------------------------------------------------


def test_fill_nulls_preserves_symbol_with_all_null_critical_cols():
    # Training period (date < train_end) has no usable data for return_* at
    # all, so the median-fill step leaves them null. The drop_nulls step
    # would otherwise remove both symbols entirely; the BEC-44 recovery step
    # must put them back with critical columns imputed to 0.
    df = pl.DataFrame(
        {
            "symbol": ["AAPL", "SHORT"],
            "date": [dt.date(2024, 1, 3), dt.date(2024, 1, 3)],
            "return_1d": [None, None],
            "return_5d": [None, None],
            "return_20d": [None, None],
            "target": [None, None],
            "km_returnOnEquity": [0.15, 0.12],
        }
    )

    out = fill_nulls(df, train_end=dt.date(2024, 1, 2))
    symbols_out = set(out["symbol"].to_list())
    assert {"AAPL", "SHORT"}.issubset(symbols_out), "fill_nulls silently dropped a symbol"
    for sym in ("AAPL", "SHORT"):
        row = out.filter(pl.col("symbol") == sym).row(0, named=True)
        assert row["return_1d"] == 0.0
        assert row["target"] == 0


# ---------------------------------------------------------------------------
# clustering.compute_clustering_features — short-history symbol padding
# ---------------------------------------------------------------------------


def test_compute_clustering_features_pads_short_history_symbols():
    from src.features.clustering import compute_clustering_features

    # Build a synthetic OHLCV dataframe: two symbols, one with 60+ days and
    # one with 5 days (insufficient for the min_history=60 cutoff).
    dates_long = [dt.date(2023, 1, 1) + dt.timedelta(days=i) for i in range(80)]
    dates_short = [dt.date(2023, 1, 1) + dt.timedelta(days=i) for i in range(5)]

    long_rows = [
        {"symbol": "LONG", "date": d, "close": 100 + i * 0.1, "volume": 1_000_000}
        for i, d in enumerate(dates_long)
    ]
    short_rows = [
        {"symbol": "SHORT", "date": d, "close": 50 + i, "volume": 500_000}
        for i, d in enumerate(dates_short)
    ]
    # SPY benchmark
    spy_rows = [
        {"symbol": "SPY", "date": d, "close": 400 + i * 0.2, "volume": 2_000_000}
        for i, d in enumerate(dates_long)
    ]

    ohlcv_df = pl.DataFrame(long_rows + short_rows + spy_rows)
    sectors_df = pl.DataFrame(
        [
            {"symbol": "LONG", "sector": "Technology"},
            {"symbol": "SHORT", "sector": "Technology"},
        ]
    )

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeEngine:
        """Minimal stand-in for a SQLAlchemy engine that serves the four
        queries issued by compute_clustering_features (OHLCV, SPY, macro,
        sector averages) from the synthetic dataframes above."""

        def __init__(self):
            self._call = 0

        def connect(self):
            return FakeConn()

    engine = FakeEngine()

    def fake_read_database(query, conn_or_engine):
        q = str(query).lower() if not isinstance(query, str) else query.lower()
        if "from ohlcv_daily" in q and "symbol = 'spy'" in q:
            return ohlcv_df.filter(pl.col("symbol") == "SPY").select(["date", "close"])
        if "from ohlcv_daily" in q:
            return (
                ohlcv_df.filter(pl.col("symbol").is_in(["LONG", "SHORT"]))
                .select(["symbol", "date", "close", "volume"])
                .sort(["symbol", "date"])
            )
        if "from vix_daily" in q:
            return pl.DataFrame(schema={"date": pl.Date, "vix_close": pl.Float64})
        if "from treasury_rates" in q:
            return pl.DataFrame(schema={"date": pl.Date, "spread_10y_2y": pl.Float64})
        if "from sector_performance_daily" in q:
            return pl.DataFrame(schema={"sector": pl.Utf8, "avg_change": pl.Float64})
        if "from key_metrics_quarterly" in q:
            return pl.DataFrame(schema={"symbol": pl.Utf8})
        if "from financial_ratios_quarterly" in q:
            return pl.DataFrame(schema={"symbol": pl.Utf8})
        # Unknown — return empty
        return pl.DataFrame()

    with patch("src.features.clustering.pl.read_database", side_effect=fake_read_database):
        feat_df = compute_clustering_features(
            engine,
            ["LONG", "SHORT"],
            dt.date(2023, 4, 1),
            sectors_df,
        )

    out_syms = set(feat_df["symbol"].to_list())
    assert out_syms == {"LONG", "SHORT"}, (
        f"clustering features silently dropped SHORT (out_syms={out_syms})"
    )
    # SHORT should have been padded with the neutral defaults.
    short = feat_df.filter(pl.col("symbol") == "SHORT").row(0, named=True)
    assert short["rsi_14_mean"] == 50.0
    assert short["beta_60d"] == 1.0


# ---------------------------------------------------------------------------
# aggregation._run_inference_core — short-history symbol produces a prediction
# ---------------------------------------------------------------------------


@dataclass
class _StubHparams(dict):
    """Dict-with-attribute-access stand-in for LightningModule.hparams."""

    def __getattr__(self, key):
        return self[key]


class _StubModel:
    """Minimal stand-in for LSTMForecaster covering the `_run_inference_core`
    interface (hparams.get + predict_proba)."""

    def __init__(self, feature_names):
        self.hparams = {"feature_names": list(feature_names)}

    def predict_proba(self, x):  # noqa: D401 - tiny shim
        # Return a fixed [0.4, 0.6] probability so we can assert on it.
        batch_size = x.shape[0]
        return torch.tensor([[0.4, 0.6]] * batch_size, dtype=torch.float32)


def test_aggregation_pads_short_history_symbols(capsys):
    feature_cols = ["feat_a", "feat_b"]
    seq_len = 10
    # LONG has seq_len rows, SHORT has only 3.
    long_rows = [
        {
            "symbol": "LONG",
            "date": dt.date(2024, 1, 1) + dt.timedelta(days=i),
            "feat_a": float(i),
            "feat_b": float(i) * 0.5,
        }
        for i in range(seq_len + 2)
    ]
    short_rows = [
        {
            "symbol": "SHORT",
            "date": dt.date(2024, 1, 1) + dt.timedelta(days=i),
            "feat_a": float(i + 100),
            "feat_b": float(i + 100) * 0.5,
        }
        for i in range(3)
    ]
    features_df = pl.DataFrame(long_rows + short_rows)
    clusters_df = pl.DataFrame(
        [
            {"symbol": "LONG", "cluster_id": "C1"},
            {"symbol": "SHORT", "cluster_id": "C1"},
        ]
    )

    config = {"model": {"sequence_length": seq_len}}
    split_dates = SimpleNamespace()
    model = _StubModel(feature_cols)

    preds = _run_inference_core("C1", model, features_df, clusters_df, config, split_dates)
    out_syms = {p["symbol"] for p in preds}
    assert out_syms == {"LONG", "SHORT"}, (
        f"short-history symbol was silently dropped: out_syms={out_syms}"
    )
    # Both predictions use the stub model's 0.6 up-probability.
    for p in preds:
        assert p["prob_up"] == pytest.approx(0.6)


def test_aggregation_pads_zero_history_symbol():
    """Symbol with zero rows still gets a prediction (fully zero-padded)."""
    feature_cols = ["feat_a", "feat_b"]
    seq_len = 5
    # Only LONG has rows; NONE appears in clusters but not in features_df.
    long_rows = [
        {
            "symbol": "LONG",
            "date": dt.date(2024, 1, 1) + dt.timedelta(days=i),
            "feat_a": float(i),
            "feat_b": float(i) * 0.5,
        }
        for i in range(seq_len + 1)
    ]
    features_df = pl.DataFrame(long_rows)
    clusters_df = pl.DataFrame(
        [
            {"symbol": "LONG", "cluster_id": "C1"},
            {"symbol": "NONE", "cluster_id": "C1"},
        ]
    )

    config = {"model": {"sequence_length": seq_len}}
    split_dates = SimpleNamespace()
    model = _StubModel(feature_cols)

    preds = _run_inference_core("C1", model, features_df, clusters_df, config, split_dates)
    assert {p["symbol"] for p in preds} == {"LONG", "NONE"}


# Sanity: fill_nulls does not introduce NaN on recovered rows
def test_fill_nulls_recovered_rows_are_not_nan():
    # Training period is empty so medians are all None — triggers the
    # recovery path for every symbol with null critical cols.
    df = pl.DataFrame(
        {
            "symbol": ["A", "B"],
            "date": [dt.date(2024, 1, 5), dt.date(2024, 1, 5)],
            "return_1d": [0.01, None],
            "return_5d": [0.05, None],
            "return_20d": [0.10, None],
            "target": [1, None],
            "km_foo": [0.1, None],
        }
    )
    out = fill_nulls(df, train_end=dt.date(2024, 1, 4))
    # Recovered row for B must not contain NaN on critical columns
    b_rows = out.filter(pl.col("symbol") == "B")
    for c in ["return_1d", "return_5d", "return_20d", "target"]:
        assert b_rows[c].null_count() == 0
        arr = b_rows[c].to_numpy()
        assert not np.isnan(arr).any()
