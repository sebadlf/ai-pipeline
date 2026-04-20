"""MLflow introspection used by the loop coordinator.

Kept deliberately thin: just ``total_runs()`` and a helper to decide if cleanup
is due. All MLflow access goes through the tracking server URI set in
``src/keys.py`` (``http://localhost:5000`` by default).
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from src.pipeline_loop import config, state


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


def cleanup_needed() -> bool:
    runs = total_runs()
    days = days_since_last_cleanup()
    return runs > config.MLFLOW_MAX_RUNS_BEFORE_CLEANUP or (
        days is not None and days > config.MLFLOW_DAYS_SINCE_LAST_CLEANUP
    )


def _main() -> None:
    parser = argparse.ArgumentParser(description="MLflow cleanup diagnostics.")
    parser.add_argument("--json", action="store_true", help="Emit as JSON (default).")
    args = parser.parse_args()
    _ = args
    out = {
        "total_runs": total_runs(),
        "days_since_last_cleanup": days_since_last_cleanup(),
        "cleanup_needed": cleanup_needed(),
        "threshold_runs": config.MLFLOW_MAX_RUNS_BEFORE_CLEANUP,
        "threshold_days": config.MLFLOW_DAYS_SINCE_LAST_CLEANUP,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    _main()
