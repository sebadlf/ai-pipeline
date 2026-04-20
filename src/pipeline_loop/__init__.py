"""Autonomous pipeline improvement loop — deterministic helpers.

Python layer handles only I/O and pollable state (files, MLflow, PR polling).
Decision logic lives in the slash commands under `.claude/commands/pipeline-*.md`,
which use the LLM + Linear MCP to reason over state.
"""
