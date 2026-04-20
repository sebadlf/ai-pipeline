"""MLflow targeted housekeeping — orphan and error-run cleanup.

Performs two targeted operations without destroying experiment history:

1. **Orphaned-RUNNING sweep**: Finds RUNNING runs older than ``--stale-hours``
   (default 1 hour) and transitions them to FAILED, adding a descriptive tag so
   the cause is traceable.

2. **Error-run tagging**: Finds runs whose name ends with ``-error`` or that
   carry the tag ``error_phase``, and stamps them with
   ``housekeeping=error_archive``.  This lets ``mlflow_report.py`` filter them
   out of the main table without deleting their tracebacks.

Nothing is deleted.

Usage:
    uv run python -m src.pipeline_loop.mlflow_housekeeping
    uv run python -m src.pipeline_loop.mlflow_housekeeping --stale-hours 2
    uv run python -m src.pipeline_loop.mlflow_housekeeping --dry-run
"""

from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime
from typing import Any

import mlflow
from mlflow.tracking import MlflowClient

from src.keys import MLFLOW_TRACKING_URI

# Tag applied to error runs so mlflow_report.py can filter them.
HOUSEKEEPING_TAG = "housekeeping"
ERROR_ARCHIVE_VALUE = "error_archive"

# Tag applied to orphaned runs that have been force-failed.
ORPHAN_TAG_KEY = "housekeeping.orphan_reason"
ORPHAN_TAG_VALUE = "run_exceeded_stale_threshold_force_failed"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _all_experiment_ids(client: MlflowClient) -> list[str]:
    """Return all active experiment IDs."""
    return [e.experiment_id for e in client.search_experiments()]


def sweep_orphaned_running(
    client: MlflowClient,
    *,
    stale_hours: float = 1.0,
    dry_run: bool = False,
) -> list[str]:
    """Transition RUNNING runs older than *stale_hours* to FAILED.

    Args:
        client: MLflow tracking client.
        stale_hours: Runs RUNNING for longer than this many hours are considered
            orphaned.
        dry_run: When True, report what would be changed without modifying MLflow.

    Returns:
        List of run IDs that were (or would be) transitioned.
    """
    cutoff_ms = int((_now_ms()) - stale_hours * 3600 * 1000)
    affected: list[str] = []

    exp_ids = _all_experiment_ids(client)
    if not exp_ids:
        return affected

    # Search for RUNNING runs — MLflow supports status filter in search_runs.
    runs = client.search_runs(
        experiment_ids=exp_ids,
        filter_string="attributes.status = 'RUNNING'",
        max_results=1000,
    )

    for run in runs:
        start_ms = run.info.start_time
        if start_ms is None or start_ms > cutoff_ms:
            continue  # started recently — not orphaned

        run_id = run.info.run_id
        exp_name = run.info.experiment_id
        start_iso = datetime.fromtimestamp(start_ms / 1000, tz=UTC).isoformat()
        affected.append(run_id)

        if dry_run:
            print(
                f"  [DRY RUN] Would FAIL orphaned run {run_id} "
                f"(experiment={exp_name}, started={start_iso})"
            )
        else:
            client.set_terminated(run_id, status="FAILED")
            client.set_tag(run_id, ORPHAN_TAG_KEY, ORPHAN_TAG_VALUE)
            client.set_tag(
                run_id,
                "housekeeping.force_failed_at",
                datetime.now(tz=UTC).isoformat(),
            )
            print(
                f"  Transitioned orphaned run to FAILED: {run_id} "
                f"(experiment={exp_name}, started={start_iso})"
            )

    return affected


def tag_error_runs(
    client: MlflowClient,
    *,
    dry_run: bool = False,
) -> list[str]:
    """Tag error runs with ``housekeeping=error_archive``.

    A run is considered an error run if:
    - Its ``mlflow.runName`` tag ends with ``-error``, OR
    - It carries the ``error_phase`` tag.

    Args:
        client: MLflow tracking client.
        dry_run: When True, report what would be changed without modifying MLflow.

    Returns:
        List of run IDs that were (or would be) tagged.
    """
    affected: list[str] = []
    exp_ids = _all_experiment_ids(client)
    if not exp_ids:
        return affected

    # Two queries: name-based and tag-based.
    queries: list[str] = [
        "tags.`mlflow.runName` LIKE '%-error'",
        "tags.`error_phase` != ''",
    ]

    seen: set[str] = set()
    for query in queries:
        try:
            runs = client.search_runs(
                experiment_ids=exp_ids,
                filter_string=query,
                max_results=5000,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  Warning: query '{query}' failed: {exc}")
            continue

        for run in runs:
            run_id = run.info.run_id
            if run_id in seen:
                continue
            seen.add(run_id)

            existing = run.data.tags.get(HOUSEKEEPING_TAG)
            if existing == ERROR_ARCHIVE_VALUE:
                continue  # already tagged

            affected.append(run_id)
            run_name = run.data.tags.get("mlflow.runName", "<unnamed>")

            if dry_run:
                print(
                    f"  [DRY RUN] Would tag error run {run_id} "
                    f"(name={run_name}) with {HOUSEKEEPING_TAG}={ERROR_ARCHIVE_VALUE}"
                )
            else:
                client.set_tag(run_id, HOUSEKEEPING_TAG, ERROR_ARCHIVE_VALUE)
                client.set_tag(
                    run_id,
                    "housekeeping.archived_at",
                    datetime.now(tz=UTC).isoformat(),
                )
                print(
                    f"  Tagged error run {run_id} (name={run_name}) "
                    f"with {HOUSEKEEPING_TAG}={ERROR_ARCHIVE_VALUE}"
                )

    return affected


def run_housekeeping(
    tracking_uri: str,
    *,
    stale_hours: float = 1.0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the full housekeeping sweep.

    Args:
        tracking_uri: MLflow tracking server URI.
        stale_hours: Hours a RUNNING run must be alive before it's force-failed.
        dry_run: When True, only report intended actions.

    Returns:
        Summary dict with keys ``orphaned_runs`` and ``error_runs``.
    """
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri)

    print(f"1/2  Orphaned-RUNNING sweep (stale_hours={stale_hours})")
    orphaned = sweep_orphaned_running(client, stale_hours=stale_hours, dry_run=dry_run)
    if not orphaned:
        print("  No orphaned RUNNING runs found.")

    print("\n2/2  Error-run tagging")
    error_runs = tag_error_runs(client, dry_run=dry_run)
    if not error_runs:
        print("  No untagged error runs found.")

    summary = {
        "orphaned_runs": orphaned,
        "error_runs": error_runs,
        "dry_run": dry_run,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="MLflow targeted housekeeping")
    parser.add_argument(
        "--stale-hours",
        type=float,
        default=1.0,
        help="Hours a RUNNING run must be alive to be force-failed (default: 1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying MLflow",
    )
    parser.add_argument(
        "--tracking-uri",
        default=None,
        help="Override MLFLOW_TRACKING_URI",
    )
    args = parser.parse_args()

    uri = args.tracking_uri or MLFLOW_TRACKING_URI
    print("=== MLflow Housekeeping ===\n")
    summary = run_housekeeping(uri, stale_hours=args.stale_hours, dry_run=args.dry_run)

    print(
        f"\nDone. orphaned={len(summary['orphaned_runs'])} "
        f"error_tagged={len(summary['error_runs'])}" + (" [DRY RUN]" if args.dry_run else "")
    )


if __name__ == "__main__":
    main()
