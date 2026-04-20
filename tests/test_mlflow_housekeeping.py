"""Unit tests for src.pipeline_loop.mlflow_housekeeping.

Uses unittest.mock to avoid any real MLflow / network calls.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from src.pipeline_loop.mlflow_housekeeping import (
    ERROR_ARCHIVE_VALUE,
    HOUSEKEEPING_TAG,
    ORPHAN_TAG_KEY,
    ORPHAN_TAG_VALUE,
    sweep_orphaned_running,
    tag_error_runs,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(
    run_id: str,
    status: str = "RUNNING",
    start_time_ms: int | None = None,
    tags: dict[str, str] | None = None,
    run_name: str | None = None,
) -> MagicMock:
    """Build a minimal mock MLflow Run object."""
    run = MagicMock()
    run.info.run_id = run_id
    run.info.status = status
    run.info.start_time = start_time_ms
    run.info.experiment_id = "1"

    _tags: dict[str, str] = tags or {}
    if run_name is not None:
        _tags["mlflow.runName"] = run_name
    run.data.tags = _tags
    return run


def _make_client(
    exp_ids: list[str] | None = None,
    runs_by_query: dict[str, list[MagicMock]] | None = None,
) -> MagicMock:
    """Build a mock MlflowClient."""
    client = MagicMock()
    # search_experiments
    exp_mocks = [MagicMock(experiment_id=eid) for eid in (exp_ids or ["1"])]
    client.search_experiments.return_value = exp_mocks

    # search_runs — route by filter_string when runs_by_query provided
    if runs_by_query is not None:

        def _search_runs(experiment_ids, filter_string="", **kwargs):  # noqa: ARG001
            return runs_by_query.get(filter_string, [])

        client.search_runs.side_effect = _search_runs
    else:
        client.search_runs.return_value = []

    return client


# ---------------------------------------------------------------------------
# sweep_orphaned_running
# ---------------------------------------------------------------------------


class TestSweepOrphanedRunning:
    def test_no_running_runs(self):
        client = _make_client(runs_by_query={"attributes.status = 'RUNNING'": []})
        result = sweep_orphaned_running(client, stale_hours=1.0)
        assert result == []
        client.set_terminated.assert_not_called()

    def test_recent_run_not_affected(self):
        """A RUNNING run started 10 minutes ago should not be force-failed."""
        recent_ms = int(time.time() * 1000) - 10 * 60 * 1000  # 10 min ago
        run = _make_run("abc123", start_time_ms=recent_ms)
        client = _make_client(runs_by_query={"attributes.status = 'RUNNING'": [run]})
        result = sweep_orphaned_running(client, stale_hours=1.0)
        assert result == []
        client.set_terminated.assert_not_called()

    def test_stale_run_is_failed(self):
        """A RUNNING run started 2 hours ago should be transitioned to FAILED."""
        stale_ms = int(time.time() * 1000) - 2 * 3600 * 1000  # 2 hours ago
        run = _make_run("stale-run-1", start_time_ms=stale_ms)
        client = _make_client(runs_by_query={"attributes.status = 'RUNNING'": [run]})
        result = sweep_orphaned_running(client, stale_hours=1.0)
        assert result == ["stale-run-1"]
        client.set_terminated.assert_called_once_with("stale-run-1", status="FAILED")
        # Orphan tag must be set
        tag_calls = {c.args[1]: c.args[2] for c in client.set_tag.call_args_list}
        assert tag_calls[ORPHAN_TAG_KEY] == ORPHAN_TAG_VALUE

    def test_dry_run_does_not_modify(self):
        """In dry-run mode, no MLflow mutations should occur."""
        stale_ms = int(time.time() * 1000) - 2 * 3600 * 1000
        run = _make_run("stale-2", start_time_ms=stale_ms)
        client = _make_client(runs_by_query={"attributes.status = 'RUNNING'": [run]})
        result = sweep_orphaned_running(client, stale_hours=1.0, dry_run=True)
        assert result == ["stale-2"]
        client.set_terminated.assert_not_called()
        client.set_tag.assert_not_called()

    def test_run_with_none_start_time_skipped(self):
        """Runs with no start_time should not be processed."""
        run = _make_run("no-time", start_time_ms=None)
        client = _make_client(runs_by_query={"attributes.status = 'RUNNING'": [run]})
        result = sweep_orphaned_running(client, stale_hours=1.0)
        assert result == []
        client.set_terminated.assert_not_called()

    def test_multiple_stale_runs(self):
        """All stale RUNNING runs are transitioned."""
        stale_ms = int(time.time() * 1000) - 3 * 3600 * 1000
        runs = [_make_run(f"stale-{i}", start_time_ms=stale_ms) for i in range(3)]
        client = _make_client(runs_by_query={"attributes.status = 'RUNNING'": runs})
        result = sweep_orphaned_running(client, stale_hours=1.0)
        assert len(result) == 3
        assert client.set_terminated.call_count == 3


# ---------------------------------------------------------------------------
# tag_error_runs
# ---------------------------------------------------------------------------


class TestTagErrorRuns:
    def test_no_error_runs(self):
        client = _make_client(
            runs_by_query={
                "tags.`mlflow.runName` LIKE '%-error'": [],
                "tags.`error_phase` != ''": [],
            }
        )
        result = tag_error_runs(client)
        assert result == []
        client.set_tag.assert_not_called()

    def test_name_based_error_run_tagged(self):
        run = _make_run("err-1", run_name="cluster-X-error", tags={})
        client = _make_client(
            runs_by_query={
                "tags.`mlflow.runName` LIKE '%-error'": [run],
                "tags.`error_phase` != ''": [],
            }
        )
        result = tag_error_runs(client)
        assert result == ["err-1"]
        tag_calls = {c.args[1]: c.args[2] for c in client.set_tag.call_args_list}
        assert tag_calls[HOUSEKEEPING_TAG] == ERROR_ARCHIVE_VALUE

    def test_error_phase_based_run_tagged(self):
        run = _make_run("err-2", run_name="some-run", tags={"error_phase": "training"})
        client = _make_client(
            runs_by_query={
                "tags.`mlflow.runName` LIKE '%-error'": [],
                "tags.`error_phase` != ''": [run],
            }
        )
        result = tag_error_runs(client)
        assert result == ["err-2"]

    def test_already_tagged_run_skipped(self):
        """Runs already carrying housekeeping=error_archive should not be re-tagged."""
        run = _make_run(
            "err-3",
            run_name="cluster-Y-error",
            tags={"housekeeping": "error_archive"},
        )
        client = _make_client(
            runs_by_query={
                "tags.`mlflow.runName` LIKE '%-error'": [run],
                "tags.`error_phase` != ''": [],
            }
        )
        result = tag_error_runs(client)
        assert result == []
        client.set_tag.assert_not_called()

    def test_deduplication_across_queries(self):
        """A run matching both queries should only be tagged once."""
        run = _make_run(
            "err-4",
            run_name="cluster-Z-error",
            tags={"error_phase": "aggregation"},
        )
        client = _make_client(
            runs_by_query={
                "tags.`mlflow.runName` LIKE '%-error'": [run],
                "tags.`error_phase` != ''": [run],
            }
        )
        result = tag_error_runs(client)
        assert result == ["err-4"]
        # set_tag called exactly twice: housekeeping + archived_at
        assert client.set_tag.call_count == 2

    def test_dry_run_does_not_modify(self):
        run = _make_run("err-5", run_name="cluster-A-error", tags={})
        client = _make_client(
            runs_by_query={
                "tags.`mlflow.runName` LIKE '%-error'": [run],
                "tags.`error_phase` != ''": [],
            }
        )
        result = tag_error_runs(client, dry_run=True)
        assert result == ["err-5"]
        client.set_tag.assert_not_called()
