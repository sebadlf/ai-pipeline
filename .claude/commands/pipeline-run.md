---
description: Run `make pipeline` end-to-end, capture outcome, record completion in loop state. With 1 infra retry.
allowed-tools: Bash, Read
---

You are executing the **run** phase of the autonomous pipeline loop.

## Task

1. Run `make pipeline` with a generous timeout (the pipeline can take multiple hours). Capture the exit code and the last ~100 lines of stderr/stdout.
2. If exit code is non-zero:
   - Wait 10 minutes (treat this as transient infra failure), then retry **once**.
   - If the retry also fails: do **not** create a Linear issue for it. Append a clear error line to the loop log via `uv run python -m src.pipeline_loop.state append-log "make pipeline failed twice: <short error>" --level ERROR`, and stop. The coordinator will read this and pause the loop.
3. If `make pipeline` succeeds: run `uv run python -m src.pipeline_loop.state record-pipeline-completed` to stamp `pipeline_run_completed_at`.
4. Append a success log entry: `uv run python -m src.pipeline_loop.state append-log "pipeline run completed cycle=<cycle_number>"`.
5. Report back in under 80 words: exit code, retry count used, artifact sizes (`ls -lh data/*.parquet` one-liner), next suggested phase (should be `analyze`).

## Constraints

- Never commit anything in this phase — it only runs the pipeline and updates state files.
- Do not invoke other pipeline-* commands; just finish and return.
- If PIPELINE_ENV is `dev` that's fine — the pipeline command respects the env var.
