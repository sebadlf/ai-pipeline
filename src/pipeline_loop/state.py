"""Persistent state + verdict + loop log file IO for the pipeline loop.

State lives in two JSON files under the vault:

- ``state.json`` — persistent across cycles. Tracks cycle_number, consecutive
  abandons, and the timestamp when the last pipeline run completed.
- ``verdict.json`` — ephemeral per-cycle. Written by ``pipeline-analyze``,
  consumed by ``pipeline-propose``, deleted on cycle reset.

Appending to ``loop-log.md`` is how the coordinator audits what happened.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.pipeline_loop import config


@dataclass
class LoopState:
    """Persistent loop state across cycles."""

    cycle_number: int = 1
    consecutive_abandons: int = 0
    abandoned_issue_ids: list[str] = field(default_factory=list)
    pipeline_run_completed_at: str | None = None
    last_cleanup_at: str | None = None


@dataclass
class Verdict:
    """Analysis verdict for the current cycle (ephemeral)."""

    verdict: str  # one of config.VALID_VERDICTS
    reasoning: str
    suggested_issues: list[dict[str, Any]] = field(default_factory=list)
    written_at: str = ""

    def __post_init__(self) -> None:
        if self.verdict not in config.VALID_VERDICTS:
            raise ValueError(
                f"verdict must be one of {config.VALID_VERDICTS}, got {self.verdict!r}"
            )
        if not self.written_at:
            self.written_at = _now_iso()


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dirs() -> None:
    config.LOOP_DIR.mkdir(parents=True, exist_ok=True)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> LoopState:
    """Read persistent state from disk; return defaults if file missing."""
    if not config.STATE_FILE.exists():
        return LoopState()
    data = json.loads(config.STATE_FILE.read_text())
    return LoopState(
        cycle_number=data.get("cycle_number", 1),
        consecutive_abandons=data.get("consecutive_abandons", 0),
        abandoned_issue_ids=data.get("abandoned_issue_ids", []),
        pipeline_run_completed_at=data.get("pipeline_run_completed_at"),
        last_cleanup_at=data.get("last_cleanup_at"),
    )


def save_state(state: LoopState) -> None:
    _ensure_dirs()
    config.STATE_FILE.write_text(json.dumps(asdict(state), indent=2))


def reset_cycle(state: LoopState) -> LoopState:
    """Advance to the next cycle: increment counter, clear per-cycle fields, delete verdict."""
    state.cycle_number += 1
    state.pipeline_run_completed_at = None
    if config.VERDICT_FILE.exists():
        config.VERDICT_FILE.unlink()
    save_state(state)
    return state


def record_pipeline_completed(state: LoopState | None = None) -> LoopState:
    state = state or load_state()
    state.pipeline_run_completed_at = _now_iso()
    save_state(state)
    return state


def record_cleanup(state: LoopState | None = None) -> LoopState:
    state = state or load_state()
    state.last_cleanup_at = _now_iso()
    save_state(state)
    return state


def record_abandon(issue_id: str, state: LoopState | None = None) -> LoopState:
    state = state or load_state()
    state.consecutive_abandons += 1
    if issue_id not in state.abandoned_issue_ids:
        state.abandoned_issue_ids.append(issue_id)
    save_state(state)
    return state


def reset_abandon_streak(state: LoopState | None = None) -> LoopState:
    state = state or load_state()
    state.consecutive_abandons = 0
    save_state(state)
    return state


def load_verdict() -> Verdict | None:
    """Read current-cycle verdict, or None if no analysis has been written."""
    if not config.VERDICT_FILE.exists():
        return None
    data = json.loads(config.VERDICT_FILE.read_text())
    return Verdict(
        verdict=data["verdict"],
        reasoning=data.get("reasoning", ""),
        suggested_issues=data.get("suggested_issues", []),
        written_at=data.get("written_at", ""),
    )


def save_verdict(verdict: Verdict) -> None:
    _ensure_dirs()
    config.VERDICT_FILE.write_text(json.dumps(asdict(verdict), indent=2))


def append_log(entry: str, level: str = "INFO") -> None:
    """Append a single timestamped line to ``loop-log.md`` for audit."""
    _ensure_dirs()
    if not config.LOG_FILE.exists():
        config.LOG_FILE.write_text(
            "# Pipeline Loop Log\n\n"
            "Append-only audit log. One line per event. "
            "Written by slash commands under `.claude/commands/pipeline-*.md`.\n\n"
        )
    with config.LOG_FILE.open("a") as fh:
        fh.write(f"- `{_now_iso()}` **{level}** {entry}\n")


def stop_flag_present() -> bool:
    return config.STOP_FLAG_FILE.exists()


def _main() -> None:
    parser = argparse.ArgumentParser(description="Inspect/manipulate loop state from CLI.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show", help="Print full state + verdict as JSON.")
    sub.add_parser("reset-cycle", help="Advance to next cycle (increment counter, delete verdict).")
    sub.add_parser(
        "record-pipeline-completed", help="Mark that `make pipeline` just finished successfully."
    )
    sub.add_parser("record-cleanup", help="Mark that `make cleanup` just ran.")
    abandon = sub.add_parser("record-abandon", help="Record an abandoned issue.")
    abandon.add_argument("issue_id", help="Linear issue ID, e.g. BEC-42")
    sub.add_parser("reset-abandon-streak", help="Clear consecutive abandon counter after a merge.")
    append = sub.add_parser("append-log", help="Append a line to loop-log.md.")
    append.add_argument("message")
    append.add_argument("--level", default="INFO")

    args = parser.parse_args()
    if args.cmd == "show":
        state = load_state()
        verdict = load_verdict()
        out = {
            "state": asdict(state),
            "verdict": asdict(verdict) if verdict else None,
            "stop_flag_present": stop_flag_present(),
        }
        print(json.dumps(out, indent=2))
    elif args.cmd == "reset-cycle":
        new = reset_cycle(load_state())
        print(json.dumps(asdict(new), indent=2))
    elif args.cmd == "record-pipeline-completed":
        new = record_pipeline_completed()
        print(json.dumps(asdict(new), indent=2))
    elif args.cmd == "record-cleanup":
        new = record_cleanup()
        print(json.dumps(asdict(new), indent=2))
    elif args.cmd == "record-abandon":
        new = record_abandon(args.issue_id)
        print(json.dumps(asdict(new), indent=2))
    elif args.cmd == "reset-abandon-streak":
        new = reset_abandon_streak()
        print(json.dumps(asdict(new), indent=2))
    elif args.cmd == "append-log":
        append_log(args.message, level=args.level)


if __name__ == "__main__":
    _main()
