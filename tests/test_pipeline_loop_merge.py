"""Tests for src.pipeline_loop.merge PR-polling terminal classifier."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from src.pipeline_loop import merge


def _make_raw(
    state: str = "OPEN",
    mergeable: str = "MERGEABLE",
    checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "state": state,
        "mergeable": mergeable,
        "statusCheckRollup": checks or [],
        "isDraft": False,
    }


def test_classify_merged_wins_over_everything():
    raw = _make_raw(state="MERGED", checks=[{"name": "lint", "conclusion": "FAILURE"}])
    status = merge._classify(raw, pr_number=42)
    assert status is not None
    assert status.outcome is merge.Outcome.MERGED


def test_classify_closed_without_merge():
    raw = _make_raw(state="CLOSED")
    status = merge._classify(raw, pr_number=42)
    assert status is not None
    assert status.outcome is merge.Outcome.CLOSED


def test_classify_failed_ci_when_any_check_failed():
    raw = _make_raw(
        checks=[
            {"name": "lint", "conclusion": "SUCCESS"},
            {"name": "test", "conclusion": "FAILURE"},
        ]
    )
    status = merge._classify(raw, pr_number=42)
    assert status is not None
    assert status.outcome is merge.Outcome.FAILED_CI
    assert status.failing_checks == ["test"]


def test_classify_conflict_when_mergeable_conflicting_and_no_failures():
    raw = _make_raw(mergeable="CONFLICTING")
    status = merge._classify(raw, pr_number=42)
    assert status is not None
    assert status.outcome is merge.Outcome.CONFLICT


def test_classify_returns_none_when_pending():
    raw = _make_raw(mergeable="UNKNOWN", checks=[{"name": "lint", "conclusion": "PENDING"}])
    assert merge._classify(raw, pr_number=42) is None


def test_wait_for_merge_polls_until_terminal(monkeypatch: pytest.MonkeyPatch):
    """Simulate 2 pending polls then a merged response — ensure we return MERGED."""
    poll_results = [
        _make_raw(mergeable="UNKNOWN", checks=[{"name": "lint", "conclusion": "PENDING"}]),
        _make_raw(mergeable="UNKNOWN", checks=[{"name": "lint", "conclusion": "PENDING"}]),
        _make_raw(state="MERGED"),
    ]
    calls = {"n": 0}

    def fake_view(pr_number: int) -> dict[str, Any]:
        assert pr_number == 42
        raw = poll_results[calls["n"]]
        calls["n"] += 1
        return raw

    monkeypatch.setattr(merge, "_gh_pr_view", fake_view)

    # Fake clock: advances 10s per sleep call, deadline = 100s.
    current = {"t": 0.0}

    def fake_clock() -> float:
        return current["t"]

    def fake_sleep(seconds: float) -> None:
        current["t"] += seconds

    status = merge.wait_for_merge(
        42, poll_interval=10, timeout_minutes=1, clock=fake_clock, sleep=fake_sleep
    )
    assert status.outcome is merge.Outcome.MERGED
    assert calls["n"] == 3  # 2 pending + 1 terminal


def test_wait_for_merge_times_out_when_never_terminal(monkeypatch: pytest.MonkeyPatch):
    def fake_view(_: int) -> dict[str, Any]:
        return _make_raw(mergeable="UNKNOWN", checks=[{"name": "lint", "conclusion": "PENDING"}])

    monkeypatch.setattr(merge, "_gh_pr_view", fake_view)

    current = {"t": 0.0}

    def fake_clock() -> float:
        return current["t"]

    def fake_sleep(seconds: float) -> None:
        current["t"] += seconds

    status = merge.wait_for_merge(
        42, poll_interval=30, timeout_minutes=1, clock=fake_clock, sleep=fake_sleep
    )
    assert status.outcome is merge.Outcome.TIMEOUT


def test_wait_for_merge_survives_gh_errors(monkeypatch: pytest.MonkeyPatch):
    """If `gh` errors once but succeeds next poll, we should still classify correctly."""
    calls = {"n": 0}

    def fake_view(_: int) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise subprocess.CalledProcessError(returncode=1, cmd=["gh"], stderr="transient 502")
        return _make_raw(state="MERGED")

    monkeypatch.setattr(merge, "_gh_pr_view", fake_view)

    current = {"t": 0.0}

    def fake_clock() -> float:
        return current["t"]

    def fake_sleep(seconds: float) -> None:
        current["t"] += seconds

    status = merge.wait_for_merge(
        42, poll_interval=5, timeout_minutes=1, clock=fake_clock, sleep=fake_sleep
    )
    assert status.outcome is merge.Outcome.MERGED
    assert calls["n"] == 2
