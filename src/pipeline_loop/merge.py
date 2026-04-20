"""Poll PR state and classify the terminal outcome.

This module does **not** attempt to fix failing CI itself — that requires LLM
reasoning and lives in the ``pipeline-implement`` slash command. Instead,
``wait_for_merge`` polls until one of a small set of terminal states is reached
and returns a structured result so the caller can decide what to do next.

Terminal outcomes:

- ``MERGED``      — PR merged, we're done
- ``FAILED_CI``   — at least one required check failed
- ``CONFLICT``    — PR is not mergeable due to conflicts with the base branch
- ``CLOSED``      — PR closed without merging (manual action or abandon)
- ``TIMEOUT``     — nothing terminal within the configured window

The CLI wrapper can be invoked as::

    uv run python -m src.pipeline_loop.merge wait <PR_NUMBER>

and exits ``0`` for ``MERGED``, non-zero otherwise. Full status is printed as JSON
to stdout regardless.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from enum import StrEnum

from src.pipeline_loop import config


class Outcome(StrEnum):
    MERGED = "MERGED"
    FAILED_CI = "FAILED_CI"
    CONFLICT = "CONFLICT"
    CLOSED = "CLOSED"
    TIMEOUT = "TIMEOUT"


@dataclass
class PRStatus:
    outcome: Outcome
    pr_number: int
    state: str  # raw GH state (OPEN/MERGED/CLOSED)
    mergeable: str  # MERGEABLE/CONFLICTING/UNKNOWN
    failing_checks: list[str]
    checks_summary: list[dict]


def _gh_pr_view(pr_number: int) -> dict:
    """Fetch PR state via ``gh``. Raises CalledProcessError on failure."""
    cmd = [
        "gh",
        "pr",
        "view",
        str(pr_number),
        "--json",
        "state,mergeable,statusCheckRollup,isDraft",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def _classify(raw: dict, pr_number: int) -> PRStatus | None:
    """Return a terminal ``PRStatus`` or ``None`` if the PR is still in progress."""
    state = raw.get("state", "")
    mergeable = raw.get("mergeable", "")
    checks = raw.get("statusCheckRollup") or []
    failing = [c["name"] for c in checks if c.get("conclusion") == "FAILURE"]

    base = {
        "pr_number": pr_number,
        "state": state,
        "mergeable": mergeable,
        "failing_checks": failing,
        "checks_summary": checks,
    }

    if state == "MERGED":
        return PRStatus(outcome=Outcome.MERGED, **base)
    if state == "CLOSED":
        return PRStatus(outcome=Outcome.CLOSED, **base)
    if failing:
        return PRStatus(outcome=Outcome.FAILED_CI, **base)
    if mergeable == "CONFLICTING":
        return PRStatus(outcome=Outcome.CONFLICT, **base)
    return None


def wait_for_merge(
    pr_number: int,
    poll_interval: int = config.POLL_INTERVAL_SECONDS,
    timeout_minutes: int = config.PR_TIMEOUT_MINUTES,
    clock: callable = time.monotonic,
    sleep: callable = time.sleep,
) -> PRStatus:
    """Block until the PR reaches a terminal state or the timeout elapses.

    ``clock`` and ``sleep`` are injectable for tests — the default values poll
    real time via ``time.monotonic`` and ``time.sleep``.
    """
    deadline = clock() + timeout_minutes * 60
    last_raw: dict = {}
    while clock() < deadline:
        try:
            raw = _gh_pr_view(pr_number)
        except subprocess.CalledProcessError as exc:
            raw = {"error": exc.stderr}
        last_raw = raw
        terminal = _classify(raw, pr_number)
        if terminal is not None:
            return terminal
        sleep(poll_interval)

    return PRStatus(
        outcome=Outcome.TIMEOUT,
        pr_number=pr_number,
        state=last_raw.get("state", "UNKNOWN"),
        mergeable=last_raw.get("mergeable", "UNKNOWN"),
        failing_checks=[],
        checks_summary=last_raw.get("statusCheckRollup") or [],
    )


def _main() -> None:
    parser = argparse.ArgumentParser(description="Wait for a PR to reach a terminal state.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    wait = sub.add_parser("wait", help="Poll until PR is merged, failed, conflicted, or times out.")
    wait.add_argument("pr_number", type=int)
    wait.add_argument("--poll", type=int, default=config.POLL_INTERVAL_SECONDS)
    wait.add_argument("--timeout-minutes", type=int, default=config.PR_TIMEOUT_MINUTES)

    status = sub.add_parser("status", help="Single-shot classification, no polling.")
    status.add_argument("pr_number", type=int)

    args = parser.parse_args()
    if args.cmd == "wait":
        result = wait_for_merge(
            args.pr_number, poll_interval=args.poll, timeout_minutes=args.timeout_minutes
        )
    else:
        raw = _gh_pr_view(args.pr_number)
        terminal = _classify(raw, args.pr_number)
        if terminal is None:
            result = PRStatus(
                outcome=Outcome.TIMEOUT,  # sentinel for "not terminal yet"
                pr_number=args.pr_number,
                state=raw.get("state", "UNKNOWN"),
                mergeable=raw.get("mergeable", "UNKNOWN"),
                failing_checks=[
                    c["name"]
                    for c in (raw.get("statusCheckRollup") or [])
                    if c.get("conclusion") == "FAILURE"
                ],
                checks_summary=raw.get("statusCheckRollup") or [],
            )
        else:
            result = terminal

    out = asdict(result)
    out["outcome"] = result.outcome.value
    print(json.dumps(out, indent=2))
    sys.exit(0 if result.outcome == Outcome.MERGED else 1)


if __name__ == "__main__":
    _main()
