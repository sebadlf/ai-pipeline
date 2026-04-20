"""MLflow introspection used by the loop coordinator.

Kept deliberately thin: ``total_runs()`` and ``days_since_last_cleanup()``
expose objective signals about MLflow state. They are **informational only** —
the decision to run ``make cleanup`` lives in the ``analyze`` phase (which sets
``cleanup_recommended`` on the verdict). All MLflow access goes through the
tracking server URI set in ``src/keys.py`` (``http://localhost:5000`` by
default).
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from src.pipeline_loop import state


def total_runs() -> int:
    """Count all runs across all experiments on the tracking server.

    Returns 0 on connection failure — the caller treats that as "nothing to clean".
    """
    try:
        import mlflow
        from mlflow.tracking import MlflowClient

        from src.keys import MLFLOW_TRACKING_URI

        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        client = MlflowClient()
        total = 0
        for exp in client.search_experiments():
            runs = client.search_runs([exp.experiment_id], max_results=1000)
            total += len(runs)
        return total
    except Exception:
        return 0


def days_since_last_cleanup() -> int | None:
    """Days since the last recorded ``make cleanup``, or None if never recorded."""
    ts = state.load_state().last_cleanup_at
    if not ts:
        return None
    last = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    now = datetime.now(UTC)
    return (now - last).days


def _main() -> None:
    parser = argparse.ArgumentParser(description="MLflow cleanup diagnostics (informational).")
    parser.add_argument("--json", action="store_true", help="Emit as JSON (default).")
    args = parser.parse_args()
    _ = args
    out = {
        "total_runs": total_runs(),
        "days_since_last_cleanup": days_since_last_cleanup(),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    _main()
