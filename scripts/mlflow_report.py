"""Summarize MLflow experiments, runs, and model registry.

Reads MLFLOW_TRACKING_URI from the environment (via .env / src.keys) unless
--tracking-uri is set.

Usage:
    uv run python scripts/mlflow_report.py
    uv run python scripts/mlflow_report.py --format json -o data/mlflow_report.json
    MLFLOW_TRACKING_URI=http://192.168.68.64:5000 uv run python scripts/mlflow_report.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from mlflow.tracking import MlflowClient

from src.keys import MLFLOW_TRACKING_URI

# Metrics logged by LSTMForecaster (train/val/test) + precision_eval + optimize.py.
# Direction: "min" for loss, "max" for accuracy / precision / recall / stability.
REPORT_METRICS: dict[str, str] = {
    # Training
    "train_acc": "max",
    "train_loss": "min",
    "train_precision_up": "max",
    "train_recall_up": "max",
    # Validation
    "val_acc": "max",
    "val_loss": "min",
    "val_precision_up": "max",
    "val_recall_up": "max",
    "val_mean_prob_up": "max",
    # Test
    "test_acc": "max",
    "test_loss": "min",
    "test_precision_up": "max",
    "test_recall_up": "max",
    "test_f1_up": "max",
    # Promotion / walk-forward stability
    "val_stability_score": "max",
    "val_auc_pr": "max",
    "val_wf_precision_mean": "max",
    "val_wf_precision_std": "min",
    "val_fp_severity": "min",
    # Training dynamics
    "stopped_epoch": "min",
    "dataset_train_samples": "max",
}

# Params to include in detailed per-run view.
REPORT_PARAMS: tuple[str, ...] = (
    "early_stop_trigger",
    "val_elimination_stage",
    "val_passed_all_filters",
    "optuna_trial_number",
)

# Non per-cluster-training experiments (noise for this report).
_EXCLUDED_EXPERIMENTS = frozenset({
    "Default",
    "clustering",
    "aggregation",
    "backtesting",
    "portfolio-optimization",
})


def _experiment_display_name(name: str) -> str:
    """Strip pipeline prefix for compact table column (full name stays in MLflow)."""
    return name.removeprefix("cluster/")


@dataclass
class LatestRunInfo:
    run_id: str
    status: str
    start_time_iso: str | None
    start_time_ms: int | None


@dataclass
class ExperimentSummary:
    name: str
    experiment_id: str
    run_count: int
    status_counts: dict[str, int]
    best_metrics: dict[str, float]
    latest_run: LatestRunInfo | None
    promotion_counts: dict[str, int] | None = None


def _ms_to_iso(ms: int | None) -> str | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC).isoformat()


def _summarize_experiment(
    client: MlflowClient,
    experiment_id: str,
    name: str,
    max_runs: int,
) -> ExperimentSummary:
    runs = client.search_runs(
        experiment_ids=[experiment_id],
        max_results=max_runs,
        order_by=["start_time DESC"],
    )
    status_counts: dict[str, int] = defaultdict(int)
    best_metrics: dict[str, float] = {}
    promotion_counts: dict[str, int] = {"passed": 0, "failed": 0}
    latest: LatestRunInfo | None = None

    for r in runs:
        status_counts[r.info.status] += 1
        if latest is None:
            latest = LatestRunInfo(
                run_id=r.info.run_id,
                status=r.info.status,
                start_time_iso=_ms_to_iso(r.info.start_time),
                start_time_ms=r.info.start_time,
            )
        if r.info.status != "FINISHED":
            continue

        # Count promotion results
        passed_str = r.data.params.get("val_passed_all_filters")
        if passed_str == "true":
            promotion_counts["passed"] += 1
        elif passed_str == "false":
            promotion_counts["failed"] += 1

        for key, direction in REPORT_METRICS.items():
            v = r.data.metrics.get(key)
            if v is None:
                continue
            fv = float(v)
            if key not in best_metrics:
                best_metrics[key] = fv
            elif direction == "min":
                best_metrics[key] = min(best_metrics[key], fv)
            else:
                best_metrics[key] = max(best_metrics[key], fv)

    return ExperimentSummary(
        name=name,
        experiment_id=experiment_id,
        run_count=len(runs),
        status_counts=dict(status_counts),
        best_metrics=best_metrics,
        latest_run=latest,
        promotion_counts=promotion_counts,
    )


def _registered_models(client: MlflowClient, max_models: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        models = client.search_registered_models(max_results=max_models)
    except Exception as e:  # noqa: BLE001 — surface registry errors in report
        return [{"error": str(e)}]
    for m in models:
        versions: list[dict[str, Any]] = []
        for v in m.latest_versions:
            versions.append(
                {
                    "version": v.version,
                    "stage": v.current_stage,
                    "aliases": list(v.aliases) if v.aliases else [],
                    "run_id": v.run_id,
                }
            )
        out.append({"name": m.name, "latest_versions": versions})
    return out


def build_report(
    tracking_uri: str,
    *,
    max_runs: int,
    name_contains: str | None,
) -> dict[str, Any]:
    client = MlflowClient(tracking_uri)
    experiments = client.search_experiments()

    filtered = [
        e
        for e in experiments
        if e.name not in _EXCLUDED_EXPERIMENTS
        and (not name_contains or name_contains.lower() in e.name.lower())
    ]

    summaries = [
        _summarize_experiment(client, e.experiment_id, e.name, max_runs)
        for e in filtered
    ]

    summaries.sort(key=lambda s: _experiment_display_name(s.name).lower())

    return {
        "tracking_uri": tracking_uri,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "filter_name_contains": name_contains,
        "best_metric_direction": REPORT_METRICS,
        "experiments": [asdict(s) for s in summaries],
        "registered_models": _registered_models(client, max_models=500),
    }


def _markdown_table(rows: list[list[str]], headers: list[str]) -> str:
    w = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            w[i] = max(w[i], len(cell))
    sep = "|" + "|".join(" " + headers[i].ljust(w[i]) + " " for i in range(len(headers))) + "|"
    line = "|" + "|".join("-" * (w[i] + 2) for i in range(len(headers))) + "|"
    out = [sep, line]
    for row in rows:
        out.append(
            "|" + "|".join(" " + row[i].ljust(w[i]) + " " for i in range(len(row))) + "|"
        )
    return "\n".join(out)


def report_to_markdown(data: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# MLflow report")
    lines.append("")
    lines.append(f"- **Tracking URI**: `{data['tracking_uri']}`")
    lines.append(f"- **Generated**: `{data['generated_at']}`")
    if data.get("filter_name_contains"):
        lines.append(f"- **Filter**: name contains `{data['filter_name_contains']}`")
    lines.append("")

    def _fmt(m: dict[str, float], key: str) -> str:
        v = m.get(key)
        return f"{v:.4f}" if v is not None else "—"

    # -- Table 1: Training metrics --
    exp_rows: list[list[str]] = []
    for e in data["experiments"]:
        sc = e["status_counts"]
        status_str = "/".join(f"{k}:{sc[k]}" for k in sorted(sc.keys()))
        bm = e["best_metrics"]
        lr = e.get("latest_run") or {}
        latest = (
            f"{lr.get('status', '—')} @ {lr.get('start_time_iso', '—')[:19]}"
            if lr
            else "—"
        )
        exp_rows.append(
            [
                _experiment_display_name(e["name"]),
                str(e["run_count"]),
                status_str,
                _fmt(bm, "val_acc"),
                _fmt(bm, "val_loss"),
                _fmt(bm, "val_precision_up"),
                _fmt(bm, "val_recall_up"),
                _fmt(bm, "test_acc"),
                _fmt(bm, "test_precision_up"),
                _fmt(bm, "test_recall_up"),
                _fmt(bm, "test_f1_up"),
                latest,
            ]
        )

    lines.append("## Experiments — Training Metrics")
    lines.append("")
    lines.append(
        "Per experiment: **best** metric across all **FINISHED** runs "
        "(min loss, max accuracy / precision / recall). "
        "Rows ordered alphabetically by experiment name."
    )
    lines.append("")
    lines.append(
        _markdown_table(
            exp_rows,
            [
                "experiment",
                "runs",
                "status",
                "val_acc",
                "val_loss",
                "val_p↑",
                "val_r↑",
                "te_acc",
                "te_p↑",
                "te_r↑",
                "te_f1↑",
                "latest run",
            ],
        )
    )
    lines.append("")

    # -- Table 2: Promotion / stability metrics --
    promo_rows: list[list[str]] = []
    for e in data["experiments"]:
        bm = e["best_metrics"]
        pc = e.get("promotion_counts", {})
        passed = pc.get("passed", 0)
        failed = pc.get("failed", 0)
        total_eval = passed + failed
        promo_rate = f"{passed}/{total_eval}" if total_eval > 0 else "—"
        promo_rows.append(
            [
                _experiment_display_name(e["name"]),
                promo_rate,
                _fmt(bm, "val_stability_score"),
                _fmt(bm, "val_auc_pr"),
                _fmt(bm, "val_wf_precision_mean"),
                _fmt(bm, "val_wf_precision_std"),
                _fmt(bm, "val_fp_severity"),
                _fmt(bm, "stopped_epoch"),
                _fmt(bm, "dataset_train_samples"),
            ]
        )

    lines.append("## Experiments — Promotion & Diagnostics")
    lines.append("")
    lines.append(
        _markdown_table(
            promo_rows,
            [
                "experiment",
                "promoted",
                "stability",
                "auc_pr",
                "wf_p_mean",
                "wf_p_std",
                "fp_sev",
                "min_epoch",
                "train_n",
            ],
        )
    )
    lines.append("")
    lines.append(
        "_promoted = passed/total evaluated. stability = best val_stability_score. "
        "wf = walk-forward precision. fp_sev = false-positive severity (lower = better). "
        "min_epoch = earliest stopped_epoch._"
    )
    lines.append("")

    reg = data["registered_models"]
    lines.append("## Model registry")
    lines.append("")
    if reg and isinstance(reg[0], dict) and "error" in reg[0]:
        lines.append(f"_Error listing models: {reg[0]['error']}_")
    elif not reg:
        lines.append("_No registered models._")
    else:
        for m in reg:
            lines.append(f"- **{m['name']}**")
            for v in m.get("latest_versions", []):
                lines.append(
                    f"  - v{v['version']} stage={v['stage']} aliases={v['aliases']}"
                )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="MLflow experiments / runs summary")
    parser.add_argument(
        "--tracking-uri",
        default=None,
        help="Override MLFLOW_TRACKING_URI (default from env / .env)",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output file path, or - for stdout",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=10_000,
        help="Max runs fetched per experiment",
    )
    parser.add_argument(
        "--name-contains",
        default=None,
        help="Only include experiments whose name contains this substring (case-insensitive)",
    )
    args = parser.parse_args()

    uri = args.tracking_uri or MLFLOW_TRACKING_URI

    try:
        data = build_report(uri, max_runs=args.max_runs, name_contains=args.name_contains)
    except Exception as e:
        print(f"Failed to reach MLflow at {uri}: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    if args.format == "json":
        text = json.dumps(data, indent=2)
    else:
        text = report_to_markdown(data)

    if args.output == "-":
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
            if not text.endswith("\n"):
                f.write("\n")
        print(f"Wrote {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
