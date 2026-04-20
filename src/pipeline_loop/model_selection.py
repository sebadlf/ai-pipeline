"""Model selection for pipeline-loop phase sub-agents.

The coordinator calls ``pick_model`` right before spawning each sub-agent
via the ``Agent`` tool. The result is passed as the ``model`` parameter.

Kept as a separate module (rather than a helper in ``state.py``) because
it is a stateless decision: no filesystem, no DB, no MLflow. Just a lookup
plus two override rules for the ``implement`` phase.
"""

from __future__ import annotations

from src.pipeline_loop import config


def pick_model(
    phase: str,
    issue_priority: int | None = None,
    issue_labels: list[str] | None = None,
) -> str:
    """Return ``"opus"`` or ``"sonnet"`` for the given phase.

    Args:
        phase: one of ``run``, ``analyze``, ``cleanup``, ``propose``, ``implement``.
        issue_priority: Linear issue priority (1=Urgent … 4=Low). Only
            consulted when ``phase == "implement"``. Pass ``None`` for other phases.
        issue_labels: Linear issue label strings. Only consulted when
            ``phase == "implement"``. Pass ``None`` for other phases.

    Returns:
        ``"opus"`` when the phase or the issue override demands it,
        ``"sonnet"`` otherwise.
    """
    if phase == "implement":
        if issue_priority == 1:
            return "opus"
        if issue_labels and config.LABEL_FORCE_OPUS in issue_labels:
            return "opus"
    return config.PHASE_MODEL_DEFAULTS.get(phase, "sonnet")
