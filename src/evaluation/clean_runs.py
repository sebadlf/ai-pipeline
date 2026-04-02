"""Delete MLflow runs that lack precision evaluation metrics.

Removes legacy training runs that were created before the precision-focused
evaluation system was added. Also deletes all registered model versions
and aliases so promotion starts fresh.

Usage:
    uv run python -m src.evaluation.clean_runs
    uv run python -m src.evaluation.clean_runs --dry-run
"""

from __future__ import annotations

import argparse

import mlflow
from mlflow.tracking import MlflowClient

from src.keys import MLFLOW_TRACKING_URI


def clean_legacy_runs(dry_run: bool = False) -> None:
    """Delete all runs that lack val_passed_all_filters param."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient()

    experiments = client.search_experiments()
    total_deleted = 0
    total_kept = 0

    for exp in experiments:
        if exp.name == "Default":
            continue

        runs = client.search_runs(
            experiment_ids=[exp.experiment_id],
            max_results=1000,
        )

        for run in runs:
            has_eval = "val_passed_all_filters" in run.data.params

            if not has_eval:
                if dry_run:
                    print(f"  [DRY RUN] Would delete: {exp.name} / {run.info.run_id[:12]}")
                else:
                    client.delete_run(run.info.run_id)
                    print(f"  Deleted: {exp.name} / {run.info.run_id[:12]}")
                total_deleted += 1
            else:
                total_kept += 1

    print(f"\n{'Would delete' if dry_run else 'Deleted'}: {total_deleted} legacy runs")
    print(f"Kept: {total_kept} runs with precision eval")


def clean_registered_models(dry_run: bool = False) -> None:
    """Delete all registered models so promotion starts fresh."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient()

    models = client.search_registered_models()
    for model in models:
        if dry_run:
            print(f"  [DRY RUN] Would delete model: {model.name}")
        else:
            client.delete_registered_model(model.name)
            print(f"  Deleted model: {model.name}")

    print(f"\n{'Would delete' if dry_run else 'Deleted'}: {len(models)} registered models")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean legacy MLflow runs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    args = parser.parse_args()

    print("=== Cleaning legacy runs (no precision eval metrics) ===")
    clean_legacy_runs(dry_run=args.dry_run)

    print("\n=== Cleaning registered models ===")
    clean_registered_models(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
