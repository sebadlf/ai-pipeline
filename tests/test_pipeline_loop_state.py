"""Tests for src.pipeline_loop.state file IO helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.pipeline_loop import config, state


@pytest.fixture(autouse=True)
def _isolate_state_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect every state/verdict/log/stop path to a throwaway tmpdir for each test."""
    loop_dir = tmp_path / "vault" / "pipeline-loop"
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config, "LOOP_DIR", loop_dir)
    monkeypatch.setattr(config, "REPORTS_DIR", loop_dir / "reports")
    monkeypatch.setattr(config, "VERDICT_FILE", loop_dir / "verdict.json")
    monkeypatch.setattr(config, "LOG_FILE", loop_dir / "loop-log.md")
    monkeypatch.setattr(config, "STATE_FILE", loop_dir / "state.json")
    monkeypatch.setattr(config, "DATA_DIR", data_dir)
    monkeypatch.setattr(config, "STOP_FLAG_FILE", data_dir / ".loop-stop")
    data_dir.mkdir(parents=True, exist_ok=True)


def test_load_state_returns_defaults_when_missing():
    s = state.load_state()
    assert s.cycle_number == 1
    assert s.consecutive_abandons == 0
    assert s.abandoned_issue_ids == []
    assert s.pipeline_run_completed_at is None
    assert s.last_cleanup_at is None


def test_save_then_load_round_trip():
    original = state.LoopState(
        cycle_number=5,
        consecutive_abandons=1,
        abandoned_issue_ids=["BEC-10", "BEC-11"],
        pipeline_run_completed_at="2026-04-20T00:00:00Z",
    )
    state.save_state(original)
    loaded = state.load_state()
    assert loaded == original


def test_reset_cycle_advances_counter_and_clears_verdict():
    s = state.LoopState(cycle_number=3, pipeline_run_completed_at="2026-04-20T00:00:00Z")
    state.save_state(s)
    state.save_verdict(state.Verdict(verdict="improve", reasoning="x"))
    assert config.VERDICT_FILE.exists()

    new = state.reset_cycle(state.load_state())
    assert new.cycle_number == 4
    assert new.pipeline_run_completed_at is None
    assert not config.VERDICT_FILE.exists()


def test_record_pipeline_completed_stamps_timestamp():
    new = state.record_pipeline_completed()
    assert new.pipeline_run_completed_at is not None
    # Round-trip to confirm persistence
    reloaded = state.load_state()
    assert reloaded.pipeline_run_completed_at == new.pipeline_run_completed_at


def test_record_abandon_increments_and_dedups():
    state.record_abandon("BEC-42")
    state.record_abandon("BEC-43")
    state.record_abandon("BEC-42")  # duplicate — ID list should not grow but counter should
    s = state.load_state()
    assert s.consecutive_abandons == 3
    assert s.abandoned_issue_ids == ["BEC-42", "BEC-43"]


def test_reset_abandon_streak_clears_counter_but_keeps_history():
    state.record_abandon("BEC-42")
    state.record_abandon("BEC-43")
    state.reset_abandon_streak()
    s = state.load_state()
    assert s.consecutive_abandons == 0
    assert s.abandoned_issue_ids == ["BEC-42", "BEC-43"]  # history preserved


def test_verdict_validation_rejects_bad_values():
    with pytest.raises(ValueError):
        state.Verdict(verdict="bogus", reasoning="x")


def test_verdict_save_and_load():
    v = state.Verdict(
        verdict="improve",
        reasoning="pipeline underperforms on energy cluster",
        suggested_issues=[{"title": "tune focal_gamma", "priority": 2}],
    )
    state.save_verdict(v)
    loaded = state.load_verdict()
    assert loaded is not None
    assert loaded.verdict == "improve"
    assert loaded.suggested_issues == [{"title": "tune focal_gamma", "priority": 2}]
    assert loaded.written_at  # stamped automatically


def test_load_verdict_returns_none_when_missing():
    assert state.load_verdict() is None


def test_append_log_creates_file_and_appends():
    state.append_log("first event")
    state.append_log("second event", level="WARN")
    content = config.LOG_FILE.read_text()
    assert "# Pipeline Loop Log" in content
    assert "first event" in content
    assert "**WARN**" in content
    assert content.count("- `") == 2  # two log entries


def test_stop_flag_present_detects_file():
    assert state.stop_flag_present() is False
    config.STOP_FLAG_FILE.write_text("")
    assert state.stop_flag_present() is True
