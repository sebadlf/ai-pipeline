---
description: Run `make cleanup` when the analyze phase recommended it (verdict.cleanup_recommended=true).
allowed-tools: Bash, Read
---

You are executing the **cleanup** phase.

The coordinator only dispatches you when `verdict.cleanup_recommended == true` and `verdict.cleanup_done == false`. That decision was made by `pipeline-analyze` based on qualitative signals (noisy FAILED runs, obsolete experiments, bloated reports, etc.) — you don't need to re-evaluate it.

## Task

1. Run `make cleanup`. This restarts MLflow with a clean slate and compacts the DB.
2. On success:
   - `uv run python -m src.pipeline_loop.state record-cleanup` (stamps `last_cleanup_at`).
   - `uv run python -m src.pipeline_loop.state mark-cleanup-done` (flips `cleanup_done: true` on the current verdict so the coordinator doesn't re-dispatch you).
3. Append to the loop log: `uv run python -m src.pipeline_loop.state append-log "cleanup runs_before=<X> runs_after=<Y>"`. Get the `runs_before`/`runs_after` counts from `uv run python -m src.pipeline_loop.mlflow_helpers` before and after the cleanup.
4. Report back in under 50 words: runs-before, runs-after, confirmation that `cleanup_done` was set.

## Constraints

- Do not second-guess the coordinator: if you were invoked, cleanup is warranted. Just run it.
- Do not delete anything outside of what `make cleanup` does.
- MLflow artifacts on disk are managed by the Docker volume; don't touch them manually.
- If `make cleanup` fails, do **not** mark `cleanup_done` — leave the flag false so the coordinator surfaces the issue. Return an error report instead.
