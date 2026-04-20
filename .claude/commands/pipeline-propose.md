---
description: Read the current cycle's verdict and create up to 5 Linear issues, with dedup against currently-open pipeline-auto issues.
allowed-tools: Bash, Read, Write, mcp__linear__list_issues, mcp__linear__save_issue, mcp__linear__list_issue_labels
---

You are executing the **propose** phase.

## Preconditions (verify first)

1. Load the verdict: `cat ai-pipeline-vault/projects/ai-pipeline/pipeline-loop/verdict.json`.
2. If verdict is not `improve` or `suggested_issues` is empty, abort immediately — print a short explanation and return. The coordinator should never have sent you here, but refuse gracefully if it did.
3. Load current loop state: `uv run python -m src.pipeline_loop.state show`.

## Dedup against open issues

1. Query Linear for open issues with label `pipeline-auto` in team `Becerra`:

   Use `mcp__linear__list_issues` with `team="Becerra"`, `labels=["pipeline-auto"]`, `state="Todo"` (and also `"In Progress"`, `"Backlog"`). Collect their titles.

2. For each candidate in `suggested_issues`, compute a simple dedup key: lowercase the title, collapse whitespace. Skip any candidate whose key matches an existing title (exact match or substring match ≥80% — use your judgment, err on the side of *not* creating duplicates).

3. Cap the total at 5 new issues per cycle. If the dedup left you with more than 5, keep the top 5 by `priority` (lower number = higher priority) and break ties by order in the verdict.

## Create the issues

For each remaining candidate, call `mcp__linear__save_issue` with:

- `team="Becerra"`
- `title=<candidate.title>`
- `description=<candidate.description>` — preserve the markdown body exactly as the analyzer wrote it. Do **not** escape newlines.
- `priority=<candidate.priority>` (default 3 if missing)
- `labels=["pipeline-auto", <existing label per stage when obvious: "tech-debt" / "feature" / "infra">]` — pick one tag based on the nature of the change. `pipeline-auto` is mandatory; the second is optional but recommended.
- `project="AI Pipeline"`
- `assignee="sebadlf"` (or `"me"` — same user)

Record each created issue ID. If creation fails for any candidate, log the error but continue with the others.

## Finalize

1. Append to the loop log:
   `uv run python -m src.pipeline_loop.state append-log "propose cycle=N created=<K> skipped_dedup=<M>"`
2. Delete the verdict file so the next cycle can write a new one only after the next analysis. But first record the fact that propose ran by leaving a marker so the coordinator knows propose already happened this cycle.

   The simplest way: overwrite `verdict.json` to mark it consumed:
   ```
   uv run python -c "
   import json
   from src.pipeline_loop import config
   path = config.VERDICT_FILE
   data = json.loads(path.read_text())
   data['proposed'] = True
   path.write_text(json.dumps(data, indent=2))
   "
   ```

3. Report back in under 80 words: number of issues created, their IDs, number skipped due to dedup.

## Constraints

- Never exceed 5 new issues per cycle.
- Do not modify pre-existing issues (created by a human).
- Do not touch GitHub in this phase — just Linear.
