"""Report top 5 runs per MLflow experiment, sorted by experiment name and latest run.

Usage:
    uv run python scripts/mlflow_runs_report.py
    uv run python scripts/mlflow_runs_report.py --format json -o data/mlflow_runs_report.json
    MLFLOW_TRACKING_URI=http://192.168.68.64:5000 uv run python scripts/mlflow_runs_report.py
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from mlflow.tracking import MlflowClient

from src.keys import MLFLOW_TRACKING_URI

# Metrics to report for each run
REPORT_METRICS: dict[str, str] = {
    "val_precision_up": "max",
    "val_recall_up": "max",
    "val_f1_up": "max",
    "val_acc": "max",
    "val_loss": "min",
    "test_precision_up": "max",
    "test_recall_up": "max",
    "test_acc": "max",
    "test_loss": "min",
}

# Non per-cluster-training experiments (noise for this report)
_EXCLUDED_EXPERIMENTS = frozenset(
    {
        "Default",
        "clustering",
        "aggregation",
        "backtesting",
        "portfolio-optimization",
    }
)


@dataclass
class RunInfo:
    run_id: str
    status: str
    start_time_iso: str | None
    start_time_ms: int | None
    metrics: dict[str, float]
    params: dict[str, str]


@dataclass
class ExperimentRuns:
    name: str
    experiment_id: str
    runs: list[RunInfo]


def _ms_to_iso(ms: int | None) -> str | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC).isoformat()


def _get_top_runs(
    client: MlflowClient,
    experiment_id: str,
    name: str,
    top_n: int = 5,
) -> ExperimentRuns:
    """Get top N runs for an experiment, sorted by start time (latest first)."""
    runs = client.search_runs(
        experiment_ids=[experiment_id],
        max_results=top_n,
        order_by=["start_time DESC"],
    )

    run_infos = []
    for r in runs:
        metrics = {
            k: float(v) for k, v in r.data.metrics.items() if k in REPORT_METRICS and v is not None
        }

        # Get key hyperparameters
        params = {
            "learning_rate": r.data.params.get("learning_rate", "—"),
            "hidden_size": r.data.params.get("hidden_size", "—"),
            "dropout": r.data.params.get("dropout", "—"),
            "sequence_length": r.data.params.get("sequence_length", "—"),
        }

        run_infos.append(
            RunInfo(
                run_id=r.info.run_id,
                status=r.info.status,
                start_time_iso=_ms_to_iso(r.info.start_time),
                start_time_ms=r.info.start_time,
                metrics=metrics,
                params=params,
            )
        )

    return ExperimentRuns(
        name=name,
        experiment_id=experiment_id,
        runs=run_infos,
    )


def build_runs_report(
    tracking_uri: str,
    *,
    top_n: int = 5,
    name_contains: str | None,
) -> dict[str, Any]:
    """Build report of top N runs per experiment."""
    client = MlflowClient(tracking_uri)
    experiments = client.search_experiments()

    # Filter experiments
    filtered = [
        e
        for e in experiments
        if e.name not in _EXCLUDED_EXPERIMENTS
        and (not name_contains or name_contains.lower() in e.name.lower())
    ]

    # Sort by experiment name
    filtered.sort(key=lambda e: e.name.lower())

    # Get top runs for each experiment
    experiment_runs = [_get_top_runs(client, e.experiment_id, e.name, top_n) for e in filtered]

    # Filter out experiments with no runs
    experiment_runs = [er for er in experiment_runs if er.runs]

    return {
        "tracking_uri": tracking_uri,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "filter_name_contains": name_contains,
        "top_n": top_n,
        "experiments": [asdict(er) for er in experiment_runs],
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
        out.append("|" + "|".join(" " + row[i].ljust(w[i]) + " " for i in range(len(row))) + "|")
    return "\n".join(out)


def report_to_markdown(data: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# MLflow Top Runs Report")
    lines.append("")
    lines.append(f"- **Tracking URI**: `{data['tracking_uri']}`")
    lines.append(f"- **Generated**: `{data['generated_at']}`")
    lines.append(f"- **Top N**: {data['top_n']} runs per experiment")
    if data.get("filter_name_contains"):
        lines.append(f"- **Filter**: name contains `{data['filter_name_contains']}`")
    lines.append("")

    def _fmt(m: dict[str, float], key: str) -> str:
        v = m.get(key)
        return f"{v:.4f}" if v is not None else "—"

    for exp in data["experiments"]:
        exp_name = exp["name"]
        exp_id = exp["experiment_id"]

        lines.append(f"## {exp_name}")
        lines.append("")
        lines.append(f"*Experiment ID: `{exp_id}`*")
        lines.append("")

        if not exp["runs"]:
            lines.append("_No runs found._")
            lines.append("")
            continue

        run_rows: list[list[str]] = []
        for run in exp["runs"]:
            m = run["metrics"]
            p = run["params"]
            start = run["start_time_iso"][:19] if run["start_time_iso"] else "—"

            run_rows.append(
                [
                    run["run_id"][:12],
                    run["status"],
                    start,
                    _fmt(m, "val_precision_up"),
                    _fmt(m, "val_recall_up"),
                    _fmt(m, "val_acc"),
                    _fmt(m, "val_loss"),
                    _fmt(m, "test_precision_up"),
                    _fmt(m, "test_recall_up"),
                    str(p.get("learning_rate", "—"))[:8],
                    str(p.get("hidden_size", "—")),
                ]
            )

        lines.append(
            _markdown_table(
                run_rows,
                [
                    "run id",
                    "status",
                    "start time",
                    "val_p↑",
                    "val_r↑",
                    "val_acc",
                    "val_loss",
                    "test_p↑",
                    "test_r↑",
                    "lr",
                    "hidden",
                ],
            )
        )
        lines.append("")

    if not data["experiments"]:
        lines.append("_No experiments with runs found._")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("**Legend:**")
    lines.append("- `val_p↑` = val_precision_up, `val_r↑` = val_recall_up")
    lines.append("- `test_p↑` = test_precision_up, `test_r↑` = test_recall_up")
    lines.append("- `lr` = learning_rate, `hidden` = hidden_size")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="MLflow top runs per experiment")
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
        "--top-n",
        type=int,
        default=5,
        help="Number of top runs to show per experiment",
    )
    parser.add_argument(
        "--name-contains",
        default=None,
        help="Only include experiments whose name contains this substring (case-insensitive)",
    )
    args = parser.parse_args()

    uri = args.tracking_uri or MLFLOW_TRACKING_URI

    try:
        data = build_runs_report(uri, top_n=args.top_n, name_contains=args.name_contains)
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
