---
description: Run `make cleanup` conditionally (MLflow run count or days-since-last-cleanup threshold).
allowed-tools: Bash, Read
---

You are executing the **cleanup** phase.

## Task

1. Check whether cleanup is actually needed: `uv run python -m src.pipeline_loop.mlflow_helpers`. Inspect `cleanup_needed` in the output. If it's `false`, print "cleanup not needed, skipping" and return.
2. If needed, run `make cleanup`. This restarts MLflow with a clean slate and compacts the DB.
3. On success: `uv run python -m src.pipeline_loop.state record-cleanup`.
4. Append to the loop log: `uv run python -m src.pipeline_loop.state append-log "cleanup total_runs_before=<X> days_since_last=<Y>"`.
5. Report back in under 50 words: whether cleanup ran, runs-before, runs-after.

## Constraints

- Do not run `make cleanup` just because you want to — honor the `cleanup_needed` gate.
- Do not delete anything outside of what `make cleanup` does.
- MLflow artifacts on disk are managed by the Docker volume; don't touch them manually.
