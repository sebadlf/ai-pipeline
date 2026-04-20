---
description: Implement the top-priority open pipeline-auto issue in its own PR, wait for merge, and recover from CI failures.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, mcp__linear__list_issues, mcp__linear__get_issue, mcp__linear__save_issue, mcp__linear__save_comment
---

You are executing the **implement** phase. One issue, one PR, one merge. Then return.

## Pick the next issue

> **Note**: when the coordinator spawns you, it may already include a
> block at the top of this prompt with the chosen issue's metadata
> (id, title, priority, labels, gitBranchName). If that block is present,
> use those values and skip the `mcp__linear__list_issues` call in step 1.
> If the block is absent (e.g., you were invoked manually via
> `/pipeline-implement`), fetch the issue as described below.

1. List open issues: `mcp__linear__list_issues` with `team="Becerra"`, `labels=["pipeline-auto"]`, `state=["Todo","Backlog"]`, `orderBy=priority`. Exclude anything with label `auto-blocked`.
2. Pick the first one. If the list is empty, return immediately — the coordinator will reset the cycle.
3. Fetch full detail via `mcp__linear__get_issue` to get `gitBranchName`.

## Implement

1. Make sure you're on fresh `main`:
   ```
   git checkout main
   git pull origin main
   ```
2. Create the branch using the exact `gitBranchName` returned by Linear (this is what auto-links PR to issue).
3. Read the issue description carefully. If the change is vague or the scope isn't clear, **do not guess**: comment on the issue via `mcp__linear__save_comment` explaining what's unclear, add label `auto-blocked`, and return. The coordinator will count this as an abandon.
4. Implement the change. Keep scope tight — only what the issue asks for. Write or update tests where applicable.
5. Run `uv run ruff check . && uv run ruff format --check . && uv run pytest` locally. If anything fails, fix before pushing.
6. Commit with a conventional-style message ending in `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`. Include the issue ID (e.g., `BEC-42`) in the body.
7. Push the branch. Open a PR with `gh pr create` — title = issue title, body must include the Linear issue ID so it auto-links. Body template:
   ```
   ## Summary
   Closes BEC-XX.
   <1-3 bullets describing the change>

   ## Test plan
   - [x] ruff check + format
   - [x] pytest
   - [ ] CI green
   ```

## Wait for merge (active error management)

Now poll until the PR reaches a terminal state. Use:

```
uv run python -m src.pipeline_loop.merge wait <PR_NUMBER>
```

The command exits 0 on MERGED and non-zero otherwise, with full JSON on stdout. Parse the JSON and branch on `outcome`:

### outcome=MERGED

1. Delete the remote and local branches: `git push origin --delete <branch>` then `git checkout main && git branch -D <branch>`.
2. `git pull origin main`.
3. `uv run python -m src.pipeline_loop.state reset-abandon-streak`
4. Append to loop log: `... append-log "implement merged BEC-XX pr=<N> cycle=<cycle>"`.
5. Return success with the PR number.

### outcome=FAILED_CI

Attempt to fix, up to **3 times total** (counting this as attempt 1, 2, 3):

1. Fetch failing check logs:
   - `gh pr checks <PR_NUMBER>` to see which checks failed.
   - For each failing check, `gh run view <RUN_ID> --log-failed` to get the error.
2. Diagnose: ruff violation? test failure? type error? something else?
3. Fix in code, commit with message `fix: address CI failure (attempt N/3)`, push.
4. Wait for merge again via `uv run python -m src.pipeline_loop.merge wait <PR_NUMBER>`.
5. If FAILED_CI again and attempts < 3 → loop (back to step 1).
6. If attempts exhausted → **abandon** (see below).

### outcome=CONFLICT

1. `git fetch origin main` and try `git merge origin/main`.
2. If the merge is clean, commit the merge and push. Go back to waiting.
3. If the merge has conflicts, try one-shot resolution: read the conflict markers, resolve if obvious (e.g., same section edited), commit, push. Go back to waiting.
4. If resolution requires judgment beyond "take both / pick one obviously right side" → **abandon**.

### outcome=TIMEOUT or CLOSED

**Abandon.**

### outcome=CLOSED (without merge)

If the PR got closed by someone (e.g., manual intervention) — treat it as abandon but don't re-open.

## Abandon flow

When abandoning a PR:

1. Comment on the PR explaining the reason:
   `gh pr comment <PR_NUMBER> --body "Automated abandon after <N> fix attempts / conflict / timeout. See loop log for details."`
2. Close the PR: `gh pr close <PR_NUMBER>`.
3. Delete the branch: `git push origin --delete <branch>`, then local.
4. On Linear: add label `auto-blocked` to the issue and save a comment explaining the failure. Use `mcp__linear__save_issue` with `labels=[<existing labels>, "auto-blocked"]` and `mcp__linear__save_comment`.
5. Record the abandon: `uv run python -m src.pipeline_loop.state record-abandon BEC-XX`.
6. Append to the loop log: `... append-log "implement abandoned BEC-XX reason=<outcome> attempts=<N>" --level WARN`.
7. Return failure with the outcome.

## Constraints

- Exactly one issue per invocation — do not start a second one even if the first succeeds quickly.
- Never force-push, never `git reset --hard` on main, never skip CI hooks.
- Never merge the PR yourself — rely on `auto-merge.yml` (CI green → auto-merge).
- If a fix requires changes to files **outside** `src/` or `tests/` (e.g., `pyproject.toml`, CI workflows, docker-compose) and the issue didn't explicitly scope them — abandon with a note.
- Report back in under 100 words: issue ID, PR number, final outcome, attempts used.
