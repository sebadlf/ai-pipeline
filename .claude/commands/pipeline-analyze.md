---
description: Analyze pipeline outputs across ALL 7 stages, write a report to the vault, and emit a structured verdict (improve/plateau/unclear/insufficient_evidence) plus a cleanup recommendation.
allowed-tools: Bash, Read, Write, Grep, Glob
---

You are executing the **analyze** phase. Your job is a rigorous, explicit review of the last pipeline run so the coordinator knows whether to propose improvements, wait for more evidence, run a cleanup, or exit.

## Inputs to review

Walk through every stage in this order. You are **not allowed** to skip a stage: if data for a stage is missing or unreadable, record that fact in the report and treat the stage as "unclear".

### Stage 0 — Data & Features

- `data/features.parquet`: row count, symbol count, date range, NaN rate per top-20-nullable features.
- `data/features_selected.parquet` + `data/selected_features.json`: features kept vs. initial set, which filter dropped the most (null / variance / correlation / MI).
- `data/features_normalized.parquet` + `data/normalization_stats.json`: any features with mean far from 0 or std far from 1 after normalization.

### Stage 1 — Clustering

- `data/clusters.parquet`: cluster count, size distribution (look for degenerate clusters with <5 stocks or one mega-cluster).
- Was silhouette score logged anywhere we can read? If not, note that.

### Stage 2 — Training

Use MLflow reports:
- `uv run python scripts/mlflow_report.py` → summary across clusters.
- `uv run python scripts/mlflow_runs_report.py` → per-run details.

For each cluster look at: `val_precision_up`, `test_precision_up`, train/val accuracy gap (overfit signal), number of completed Optuna trials, whether ensemble of 3 was actually trained.

### Stage 3 — Promotion

Which clusters have a champion alias registered? Any that failed promotion (`failed_stability`, `failed_recall`, etc. in MLflow tags)?

### Stage 4 — Aggregation

- `data/predictions.parquet`: distribution of `prob_up` — what % of symbols above 0.60/0.65/0.70? Any normalization-drift warnings in logs?

### Stage 5 — Portfolio

- `data/portfolios.parquet`: 3 profiles × allocations. Sector concentration, number of positions vs. cap, weight range.

### Stage 6 — Backtesting

- `data/backtest_reports/<latest>.md`: Sharpe / Sortino / Calmar / Max DD per profile per regime. Flag anything worse than the prior cycle's report if one exists.

### Stage 7 — Signals

- Just note whether `make signals` has been wired into the pipeline yet; this stage may be empty.

## Evidence sufficiency check

Before picking `improve` / `plateau`, ask yourself: **do I actually have enough runs to judge whether the changes merged in previous cycles worked?**

Check `git log --oneline --since='7 days ago'` (or compare the most recent merged `pipeline-auto` PRs in Linear) against the MLflow runs for the affected clusters / stages. Emit **`insufficient_evidence`** if **any** of these holds for PRs merged since the previous cycle's verdict:

- **Too few runs**: fewer than 2 completed MLflow runs exist for the cluster(s) / stage(s) the change targets. One data point is not evidence.
- **High run-to-run variance**: `val_precision_up` or `test_precision_up` oscillate by more than ±0.05 between the last two runs without a clear trend, and one more run would break the tie.
- **First post-merge run**: a change affecting `make pipeline` end-to-end merged between the previous cycle's run and this one, and this is the first pipeline run after the merge.
- **Qualitative doubt**: you cannot honestly tell, from the runs available, whether a recent change helped — propose waiting.

When emitting `insufficient_evidence`, the report's "Verdict & reasoning" section **must** name the specific merged PR(s) / issue(s) whose impact is still unclear, and say what one more pipeline run would resolve.

Do **not** emit `insufficient_evidence` if there are no recent merged changes to evaluate (e.g., cycle 1, or a cycle with all PRs abandoned). In that case decide normally between `improve` / `plateau` / `unclear`.

## Cleanup recommendation

Independently of the verdict, decide whether MLflow needs a `make cleanup` before the next phase. Set `cleanup_recommended: true` in the verdict JSON when **any** of these qualitative signals is present:

- Many runs marked `FAILED` / `KILLED` clutter the reports and make it hard to judge signal vs. noise.
- Old or obsolete experiments (from architecture changes, renamed clusters, abandoned branches) are still registered and get in the way.
- The output of `scripts/mlflow_report.py` has grown so large it's hard to read end-to-end.
- Disk / tracking-server performance is visibly degraded in stage 2 logs.

You may consult `uv run python -m src.pipeline_loop.mlflow_helpers` to see the current `total_runs` and `days_since_last_cleanup` as **context** — but there are no hard thresholds. The decision is yours, based on whether a clean slate would make the next cycle easier to reason about. Don't recommend cleanup reflexively; only when it would improve the analysis.

If `cleanup_recommended: true`, add a short justification inline in the report (e.g., "Cleanup: 340 runs, ~120 of them FAILED from BEC-33's iteration — reports noisy").

## Verdict rules

After reviewing all 7 stages and running the evidence-sufficiency check, emit one of:

- **`improve`** — you identified at least one concrete, implementable change with a plausible story for why it would help. Attach 1-5 suggested issues (see format below).
- **`plateau`** — you reviewed every stage and cannot identify a change that is (a) concrete, (b) implementable, and (c) has a plausible mechanism of improvement. The pipeline is "done for now".
- **`unclear`** — data required to decide is missing/unreadable (e.g., MLflow server down, reports dir empty). Treat this like a transient block — the coordinator will exit and the user can investigate.
- **`insufficient_evidence`** — see the "Evidence sufficiency check" section above. Pipeline ran ok but the impact of recent merged changes can't yet be judged; one more cycle would help. **Do not** attach suggested issues in this case (`suggested_issues: []`).

You may only emit `plateau` if your reasoning explicitly mentions **each** of the 7 stages and why no change is warranted there. If you cannot do that, fall back to `unclear`.

## Output

1. Write a report to `ai-pipeline-vault/projects/ai-pipeline/pipeline-loop/reports/YYYY-MM-DD-cycle-N.md` (use today's date and the current cycle number from `uv run python -m src.pipeline_loop.state show`). Report structure:

   ```markdown
   ---
   date: YYYY-MM-DD
   cycle: N
   verdict: improve|plateau|unclear|insufficient_evidence
   cleanup_recommended: true|false
   tags: [pipeline-loop, report]
   ---

   # Pipeline Cycle Report — cycle N (YYYY-MM-DD)

   ## Summary
   <2-3 sentences>

   ## Stage-by-stage

   ### Stage 0 — Data & Features
   ...
   ### Stage 1 — Clustering
   ...
   (all 7)

   ## Verdict & reasoning
   <if insufficient_evidence, name the PRs/issues whose impact is unresolved>

   ## Cleanup recommendation
   <one line: true/false + justification if true>

   ## Suggested improvements (if verdict=improve)
   1. **<short title>** — <one paragraph: what to change, why, which stage, expected impact>
   2. ...
   ```

2. Write the structured verdict to `ai-pipeline-vault/projects/ai-pipeline/pipeline-loop/verdict.json`. Use this shape exactly:

   ```json
   {
     "verdict": "improve",
     "reasoning": "<one paragraph>",
     "suggested_issues": [
       {
         "title": "<short imperative title, ~60 chars>",
         "description": "<markdown body with Context, Proposed change, Stage affected, Expected impact, Acceptance criteria>",
         "priority": 3,
         "stage": "Stage 2 — Training"
       }
     ],
     "cleanup_recommended": false,
     "cleanup_done": false,
     "written_at": ""
   }
   ```

   Leave `written_at` empty and `cleanup_done` false; both are written/flipped by the loop itself. Prefer writing via the helper:
   `uv run python -c "import json; from src.pipeline_loop import state; state.save_verdict(state.Verdict(**json.load(open('/tmp/verdict.json'))))"` after dumping your candidate to `/tmp/verdict.json`.

3. Append to the loop log: `uv run python -m src.pipeline_loop.state append-log "analyze cycle=N verdict=<X> suggested=<K> cleanup_recommended=<true|false>"`.

4. Report back in under 120 words: verdict, one-line rationale, cleanup_recommended yes/no, number of suggested issues, path to the report.

## Constraints

- Cap suggestions at 5. If you have more ideas, keep only the top 5 by expected impact.
- Each suggested issue must name which of the 7 stages it touches.
- When verdict is `insufficient_evidence` or `unclear`, `suggested_issues` must be empty.
- Do not invoke other pipeline-* commands.
- Do not create Linear issues in this phase — only write the JSON; the `pipeline-propose` phase reads it and files them.
- Do not run `make cleanup` yourself — only set the flag; the coordinator dispatches the cleanup phase.
