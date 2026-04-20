---
description: Autonomous pipeline improvement loop — detects current phase, runs it (via Agent subagent for isolated context), reschedules itself until an exit condition is reached.
allowed-tools: Bash, Read, Write, Agent, ScheduleWakeup, mcp__linear__list_issues, mcp__linear__save_issue
---

You are the **coordinator** for the autonomous pipeline improvement loop. Your job is to inspect state, pick the next phase, delegate it to a focused subagent, then reschedule yourself — or exit cleanly if we're done.

## Lifecycle overview

```
  detect state → decide phase → spawn Agent for that phase → process result
  → update state as needed → (exit OR ScheduleWakeup(60s, "/pipeline-loop"))
```

Phases: `run` → `analyze` → `propose` → `implement` (possibly many) → `reset-cycle` → `run` → ...
Plus the transverse `cleanup` phase inserted when MLflow accumulates runs.

## Step 1 — Load state

Run these and capture the output:

- `uv run python -m src.pipeline_loop.state show`
- `uv run python -m src.pipeline_loop.mlflow_helpers`
- `mcp__linear__list_issues` with `team="Becerra"`, `labels=["pipeline-auto"]`, `state=["Todo","Backlog","In Progress"]`, `limit=50`. Filter out issues that also have the `auto-blocked` label. Count the remaining as `open_auto_issues`.

## Step 2 — Check exit conditions (in order)

Exit the loop (do **not** reschedule) if any of these holds. For each exit, append a log line via `uv run python -m src.pipeline_loop.state append-log "EXIT reason=<X>" --level INFO` and then run `nohup make pipeline-loop > /tmp/pipeline-loop-prod.log 2>&1 &` to hand off to production mode. Print a short final report to the user.

1. **Stop flag**: `stop_flag_present` is `true` in state output.
2. **Budget exhausted**: `cycle_number > 20`.
3. **Consecutive abandons**: `consecutive_abandons >= 3`. This is a circuit breaker — write `EXIT reason=circuit_breaker` with `--level ERROR`. Do **not** hand off to `make pipeline-loop` in this case; the loop is paused for human review.
4. **Plateau or unclear verdict**: current verdict is `plateau` or `unclear` AND `open_auto_issues == 0`. This is the happy "done for now" exit — hand off to `make pipeline-loop`.
5. **Loop-stop label in Linear**: any open issue in the team carries the `loop-stop` label.

If none of these hold, continue.

## Step 3 — Decide next phase

In priority order (first matching rule wins):

1. MLflow `cleanup_needed == true` → phase = `cleanup`.
2. `state.pipeline_run_completed_at` is `null` → phase = `run`.
3. No `verdict.json` yet this cycle → phase = `analyze`.
4. Verdict is `improve` AND `open_auto_issues == 0` AND verdict is **not** marked `proposed: true` → phase = `propose`.
5. `open_auto_issues > 0` → phase = `implement`.
6. Verdict is `improve` AND `open_auto_issues == 0` AND verdict is `proposed: true` → cycle is complete → reset via `uv run python -m src.pipeline_loop.state reset-cycle`, then go back to step 1 (re-detect — should land on `run` next).

## Step 4 — Execute the phase via Agent

Read the corresponding command file from `.claude/commands/pipeline-<phase>.md`. Spawn a subagent with the **entire contents of that file** as the prompt. Use `subagent_type: general-purpose` (it has access to Bash, Edit, Write, etc. — everything the phase commands need). Example:

```
Agent({
  description: "Run <phase> phase",
  subagent_type: "general-purpose",
  prompt: "<contents of .claude/commands/pipeline-<phase>.md, verbatim>"
})
```

Isolated context per phase is deliberate — keeps the coordinator light and matches the "Ralph Wiggum per fase" design. **Wait for the agent to return** before continuing (foreground, not background — you need its result to decide the next step).

## Step 5 — Process the phase result

- **`run` returned success** → continue (state file already updated). If failed after retry, exit with `EXIT reason=pipeline_failed` (`--level ERROR`) and do not hand off.
- **`analyze` returned verdict `plateau`/`unclear`** → the coordinator will detect this on the next iteration and exit per step 2.4. No special handling here; just reschedule.
- **`analyze` returned verdict `improve`** → reschedule; next iteration will pick `propose`.
- **`propose` returned with K issues created** → reschedule; next iteration will pick `implement`.
- **`propose` returned with 0 issues created** (all dedup'd) → treat the cycle as complete: `reset-cycle` and reschedule.
- **`implement` returned MERGED** → reschedule; next iteration picks another issue or resets cycle if empty.
- **`implement` returned ABANDON** → state file already has the abandon recorded; reschedule. The circuit breaker in step 2.3 will catch runaway abandons.
- **`cleanup` returned success** → reschedule.

## Step 6 — Reschedule

Call `ScheduleWakeup`:

```
ScheduleWakeup({
  delaySeconds: 60,
  prompt: "/pipeline-loop",
  reason: "Continue autonomous pipeline loop — <current phase decided> just completed"
})
```

The 60-second gap is nominal; most phases take minutes to hours themselves, so the actual cadence is set by the phase work, not this timer.

**Never reschedule if any exit condition in step 2 fired.** That's the only way the loop stops.

## Step 7 — Report to the user

Print a short status (under 80 words) summarizing:

- Current cycle number and phase that just ran
- Key outcome (e.g., "3 issues created", "BEC-42 merged", "verdict=improve")
- Whether we rescheduled or exited (and exit reason if exited)
- Link to `ai-pipeline-vault/projects/ai-pipeline/pipeline-loop/loop-log.md` for audit

## Constraints

- Do not inline phase logic — always delegate via Agent. This keeps the coordinator's context small and reusable across iterations.
- Do not touch Linear issues yourself — that's `pipeline-propose` and `pipeline-implement`'s job.
- Do not run `make pipeline` or `make cleanup` yourself — same reason.
- If state files are corrupt or missing in surprising ways, exit with `EXIT reason=state_corruption` (`--level ERROR`) and do not hand off. The user investigates manually.
- If Linear MCP is unavailable (tool error), treat `open_auto_issues` as unknown and exit with `EXIT reason=linear_unavailable` (`--level ERROR`).
