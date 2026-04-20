"""Tests for ``src.pipeline_loop.model_selection.pick_model``."""

from __future__ import annotations

from src.pipeline_loop.model_selection import pick_model


def test_pick_model_analyze_always_opus():
    assert pick_model("analyze") == "opus"


def test_pick_model_propose_always_opus():
    assert pick_model("propose") == "opus"


def test_pick_model_run_always_sonnet():
    assert pick_model("run") == "sonnet"


def test_pick_model_cleanup_always_sonnet():
    assert pick_model("cleanup") == "sonnet"


def test_pick_model_implement_default_sonnet():
    assert pick_model("implement", issue_priority=3, issue_labels=[]) == "sonnet"
    assert pick_model("implement", issue_priority=2, issue_labels=["pipeline-auto"]) == "sonnet"
    assert pick_model("implement", issue_priority=4, issue_labels=None) == "sonnet"


def test_pick_model_implement_urgent_forces_opus():
    assert pick_model("implement", issue_priority=1, issue_labels=[]) == "opus"
    assert pick_model("implement", issue_priority=1, issue_labels=["pipeline-auto"]) == "opus"


def test_pick_model_implement_force_opus_label():
    assert pick_model("implement", issue_priority=3, issue_labels=["model=Opus"]) == "opus"
    assert (
        pick_model("implement", issue_priority=4, issue_labels=["pipeline-auto", "model=Opus"])
        == "opus"
    )


def test_pick_model_implement_both_exceptions():
    assert pick_model("implement", issue_priority=1, issue_labels=["model=Opus"]) == "opus"


def test_pick_model_unknown_phase_falls_back_to_sonnet():
    """Safety: unknown phase should never accidentally spend Opus."""
    assert pick_model("bogus") == "sonnet"


def test_pick_model_implement_label_is_case_sensitive():
    """``model=Opus`` is the exact label; lowercase variants don't count."""
    assert pick_model("implement", issue_priority=3, issue_labels=["model=opus"]) == "sonnet"
    assert pick_model("implement", issue_priority=3, issue_labels=["MODEL=OPUS"]) == "sonnet"
