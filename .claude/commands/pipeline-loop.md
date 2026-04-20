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

Phases: `run` → `analyze` → (optional `cleanup` if verdict asks for it) → `propose` → `implement` (possibly many) → `reset-cycle` → `run` → ...
When `analyze` emits `insufficient_evidence`, the loop skips `propose`/`implement`, runs `cleanup` only if requested, and resets the cycle to collect another pipeline run.

## Step 1 — Load state

Run these and capture the output:

- `uv run python -m src.pipeline_loop.state show`
- `mcp__linear__list_issues` with `team="Becerra"`, `labels=["pipeline-auto"]`, `state=["Todo","Backlog","In Progress"]`, `limit=50`. Filter out issues that also have the `auto-blocked` label. Count the remaining as `open_auto_issues`.

## Step 2 — Check exit conditions (in order)

Exit the loop (do **not** reschedule) if any of these holds. For each exit, append a log line via `uv run python -m src.pipeline_loop.state append-log "EXIT reason=<X>" --level INFO` and then run `nohup make pipeline-loop > /tmp/pipeline-loop-prod.log 2>&1 &` to hand off to production mode. Print a short final report to the user.

1. **Stop flag**: `stop_flag_present` is `true` in state output.
2. **Budget exhausted**: `cycle_number > 20`.
3. **Consecutive abandons**: `consecutive_abandons >= 3`. This is a circuit breaker — write `EXIT reason=circuit_breaker` with `--level ERROR`. Do **not** hand off to `make pipeline-loop` in this case; the loop is paused for human review.
4. **Insufficient-evidence exhausted**: `consecutive_insufficient_evidence >= 3`. The analyst has asked for "one more cycle" too many times in a row — write `EXIT reason=insufficient_data_exhausted` with `--level ERROR`. Do **not** hand off; a human should look at why evidence isn't accumulating.
5. **Plateau or unclear verdict**: current verdict is `plateau` or `unclear` AND `open_auto_issues == 0`. This is the happy "done for now" exit — hand off to `make pipeline-loop`.
6. **Loop-stop label in Linear**: any open issue in the team carries the `loop-stop` label.

If none of these hold, continue.

## Step 3 — Decide next phase

In priority order (first matching rule wins):

1. `state.pipeline_run_completed_at` is `null` → phase = `run`.
2. No `verdict.json` yet this cycle → phase = `analyze`.
3. Verdict has `cleanup_recommended: true` AND `cleanup_done: false` AND verdict is **not** `plateau`/`unclear` → phase = `cleanup`. (Runs after analyze, before anything else the verdict triggers — applies whether the verdict is `improve` or `insufficient_evidence`.)
4. Verdict is `insufficient_evidence` → record the streak via `uv run python -m src.pipeline_loop.state record-insufficient-evidence`, append a log line (`analyze-wait cycle=N consecutive=<M>`), then run `uv run python -m src.pipeline_loop.state reset-cycle` (this clears the verdict and `pipeline_run_completed_at` for the next cycle) and go back to step 1 — next iteration should land on `run`.
5. Verdict is `improve` AND `open_auto_issues == 0` AND verdict is **not** marked `proposed: true` → phase = `propose`.
6. `open_auto_issues > 0` → phase = `implement`.
7. Verdict is `improve` AND `open_auto_issues == 0` AND verdict is `proposed: true` → cycle is complete → reset via `uv run python -m src.pipeline_loop.state reset-cycle`, then go back to step 1 (re-detect — should land on `run` next).

### Step 3b — If phase is `implement`, peek the top issue

When (and only when) the decided phase is `implement`, fetch the top-priority open issue **once here** so we can pick the right model and hand the metadata to the sub-agent (which will then skip its own fetch):

1. Call `mcp__linear__list_issues` with exactly these parameters:
   - `team="Becerra"`
   - `labels=["pipeline-auto"]`
   - `state=["Todo","Backlog"]`
   - `orderBy="priority"`
   - `limit=50`
2. Filter out any result that also carries the `auto-blocked` label.
3. If the filtered list is empty, treat the situation as "propose returned 0" — run `uv run python -m src.pipeline_loop.state reset-cycle` and go back to step 1 (do **not** spawn `implement`).
4. Otherwise take the first result as `top_issue`. Capture `top_issue.id` (e.g., `BEC-50`), `top_issue.title`, `top_issue.priority.value` (integer 1-4 or `None`), `top_issue.labels` (list of strings), and `top_issue.gitBranchName`.

## Step 4 — Execute the phase via Agent

Pick the model for this spawn via the `pick_model` helper. For `implement`, pass the issue metadata captured in Step 3b; for every other phase, pass only the phase name:

```
uv run python -c "from src.pipeline_loop.model_selection import pick_model; print(pick_model('<phase>'))"
# or, for implement:
uv run python -c "from src.pipeline_loop.model_selection import pick_model; print(pick_model('implement', <priority_or_None>, <labels_list>))"
```

Never hardcode `"opus"` / `"sonnet"` in the coordinator — always go through `pick_model`.

Read the corresponding command file from `.claude/commands/pipeline-<phase>.md`. Spawn a subagent with the **entire contents of that file** as the prompt, passing the chosen model. Use `subagent_type: general-purpose` (it has access to Bash, Edit, Write, etc. — everything the phase commands need).

For the `implement` phase, **prepend** a short markdown block to the prompt with the metadata captured in Step 3b so the sub-agent can skip its own Linear fetch:

```
Agent({
  description: "Run implement phase",
  subagent_type: "general-purpose",
  model: "<result of pick_model('implement', priority, labels)>",
  prompt: """> **Coordinator pre-selected issue:**
> - id: <top_issue.id>
> - title: <top_issue.title>
> - priority: <top_issue.priority.value>
> - labels: <comma-separated labels>
> - gitBranchName: <top_issue.gitBranchName>

<contents of .claude/commands/pipeline-implement.md, verbatim>
"""
})
```

For every other phase (`run`, `analyze`, `cleanup`, `propose`), no metadata block — just the file contents:

```
Agent({
  description: "Run <phase> phase",
  subagent_type: "general-purpose",
  model: "<result of pick_model('<phase>')>",
  prompt: "<contents of .claude/commands/pipeline-<phase>.md, verbatim>"
})
```

Isolated context per phase is deliberate — keeps the coordinator light and matches the "Ralph Wiggum per fase" design. **Wait for the agent to return** before continuing (foreground, not background — you need its result to decide the next step).

Immediately after spawning (before waiting, or just after the Agent call returns — either is fine, as long as it happens on every spawn), log the spawn with the model and — for `implement` — the issue:

```
uv run python -m src.pipeline_loop.state append-log "spawn phase=<phase> cycle=<N> model=<opus|sonnet>"
# or, for implement:
uv run python -m src.pipeline_loop.state append-log "spawn phase=implement cycle=<N> model=<opus|sonnet> issue=<BEC-NN> priority=<P>"
```

## Step 5 — Process the phase result

- **`run` returned success** → continue (state file already updated). If failed after retry, exit with `EXIT reason=pipeline_failed` (`--level ERROR`) and do not hand off.
- **`analyze` returned verdict `plateau`/`unclear`** → call `uv run python -m src.pipeline_loop.state reset-insufficient-streak` (safety: any non-insufficient verdict zeroes the counter). The coordinator will detect plateau/unclear on the next iteration and exit per step 2.5.
- **`analyze` returned verdict `improve`** → call `reset-insufficient-streak`, then reschedule; next iteration will pick `cleanup` (if recommended) or `propose`.
- **`analyze` returned verdict `insufficient_evidence`** → do **not** call `reset-insufficient-streak` (we want the streak to build). Reschedule; next iteration handles it via step 3 rule 3 (cleanup if asked) and then rule 4 (reset-cycle + re-run).
- **`cleanup` returned success** → reschedule; next iteration picks the next applicable phase (verdict determines what comes next).
- **`propose` returned with K issues created** → reschedule; next iteration will pick `implement`.
- **`propose` returned with 0 issues created** (all dedup'd) → treat the cycle as complete: `reset-cycle` and reschedule.
- **`implement` returned MERGED** → reschedule; next iteration picks another issue or resets cycle if empty.
- **`implement` returned ABANDON** → state file already has the abandon recorded; reschedule. The circuit breaker in step 2.3 will catch runaway abandons.

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
- Key outcome (e.g., "3 issues created", "BEC-42 merged", "verdict=improve", "verdict=insufficient_evidence — rerunning pipeline")
- Whether we rescheduled or exited (and exit reason if exited)
- Link to `ai-pipeline-vault/projects/ai-pipeline/pipeline-loop/loop-log.md` for audit

## Constraints

- Do not inline phase logic — always delegate via Agent. This keeps the coordinator's context small and reusable across iterations.
- Do not touch Linear issues yourself — that's `pipeline-propose` and `pipeline-implement`'s job.
- Do not run `make pipeline` or `make cleanup` yourself — same reason.
- Do not decide on your own whether cleanup is needed — that decision lives in `pipeline-analyze` and is communicated via `verdict.cleanup_recommended`.
- If state files are corrupt or missing in surprising ways, exit with `EXIT reason=state_corruption` (`--level ERROR`) and do not hand off. The user investigates manually.
- If Linear MCP is unavailable (tool error), treat `open_auto_issues` as unknown and exit with `EXIT reason=linear_unavailable` (`--level ERROR`).
