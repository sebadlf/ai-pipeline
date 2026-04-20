"""Stock-preservation audit utilities.

Per BEC-44, every symbol present in ``ohlcv_daily`` after ingestion must
survive every downstream stage (features, feature selection, normalization,
clustering, aggregation). No stage may silently drop stocks — only features.

This module provides two building blocks:

1. ``audit_symbols`` — compare expected symbols against those present in a
   DataFrame, print a ``symbols_in`` / ``symbols_out`` audit line, and (by
   default) raise ``StockDiscardedError`` when the two disagree.
2. ``StockDiscardedError`` — typed exception for the invariant breach.

The helper is intentionally side-effectful: it prints a single human-readable
line so the pipeline logs contain an auditable trail without callers having
to plumb loggers through every stage.
"""

from __future__ import annotations

from collections.abc import Iterable


class StockDiscardedError(RuntimeError):
    """Raised when a stage drops symbols that were present upstream."""


def _normalize_symbols(symbols: Iterable[str]) -> set[str]:
    return {s for s in symbols if s}


def audit_symbols(
    stage: str,
    expected: Iterable[str],
    actual: Iterable[str],
    *,
    raise_on_missing: bool = True,
) -> tuple[int, int, set[str]]:
    """Verify that ``actual`` preserves every symbol from ``expected``.

    Args:
        stage: Human-readable stage name used in the log line
            (e.g. ``"features"``, ``"clustering"``).
        expected: Symbols that entered the stage.
        actual: Symbols produced by the stage.
        raise_on_missing: When True (default), raise ``StockDiscardedError``
            if any expected symbol is missing from ``actual``. When False,
            only the audit line is printed and the missing set is returned.

    Returns:
        Tuple ``(n_in, n_out, missing)`` where ``missing`` is the set of
        expected symbols absent from ``actual``.
    """
    expected_set = _normalize_symbols(expected)
    actual_set = _normalize_symbols(actual)
    missing = expected_set - actual_set

    n_in = len(expected_set)
    n_out = len(actual_set)
    suffix = ""
    if missing:
        preview = ", ".join(sorted(missing)[:10])
        if len(missing) > 10:
            preview += f", ... (+{len(missing) - 10} more)"
        suffix = f" missing={len(missing)} [{preview}]"

    print(f"  [stock-audit] stage={stage} symbols_in={n_in} symbols_out={n_out}{suffix}")

    if missing and raise_on_missing:
        raise StockDiscardedError(
            f"Stage '{stage}' dropped {len(missing)} symbols. "
            "Per BEC-44 every ingested stock must survive to backtest/signals. "
            f"Missing (first 10): {sorted(missing)[:10]}"
        )

    return n_in, n_out, missing
