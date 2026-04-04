"""Full pipeline cleanup: MLflow experiments, checkpoints, and artifacts.

Deletes all MLflow experiments (and their runs), registered models,
local checkpoints, MLflow artifact storage, and pipeline output parquets.

Usage:
    uv run python -m src.evaluation.clean_runs
    uv run python -m src.evaluation.clean_runs --dry-run
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import mlflow
from mlflow.tracking import MlflowClient

from src.keys import MLFLOW_TRACKING_URI

CLEANUP_PARQUETS = [
    "data/clusters.parquet",
    "data/predictions.parquet",
    "data/portfolios.parquet",
]


def cleanup_all(dry_run: bool = False) -> None:
    """Delete all MLflow state, checkpoints, and pipeline outputs."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient()

    # 1. Delete all registered models
    models = client.search_registered_models()
    for model in models:
        if dry_run:
            print(f"  [DRY RUN] Would delete model: {model.name}")
        else:
            client.delete_registered_model(model.name)
            print(f"  Deleted model: {model.name}")
    print(f"{'Would delete' if dry_run else 'Deleted'}: {len(models)} registered models")

    # 2. Delete all experiments (and their runs)
    experiments = client.search_experiments()
    n_deleted = 0
    for exp in experiments:
        if exp.name == "Default":
            continue
        if dry_run:
            print(f"  [DRY RUN] Would delete experiment: {exp.name}")
        else:
            client.delete_experiment(exp.experiment_id)
            print(f"  Deleted experiment: {exp.name}")
        n_deleted += 1
    print(f"{'Would delete' if dry_run else 'Deleted'}: {n_deleted} experiments")

    # 3. Delete local checkpoints directory
    ckpt_dir = Path("checkpoints")
    if ckpt_dir.exists():
        if dry_run:
            n_files = sum(1 for _ in ckpt_dir.rglob("*") if _.is_file())
            print(f"  [DRY RUN] Would delete checkpoints/ ({n_files} files)")
        else:
            shutil.rmtree(ckpt_dir)
            print("  Deleted checkpoints/")
    else:
        print("  checkpoints/ not found, skipping")

    # 4. Delete local MLflow artifacts (mlruns/mlruns/)
    mlruns_inner = Path("mlruns/mlruns")
    if mlruns_inner.exists():
        if dry_run:
            n_files = sum(1 for _ in mlruns_inner.rglob("*") if _.is_file())
            print(f"  [DRY RUN] Would delete mlruns/mlruns/ ({n_files} files)")
        else:
            shutil.rmtree(mlruns_inner)
            print("  Deleted mlruns/mlruns/")
    else:
        print("  mlruns/mlruns/ not found, skipping")

    # 5. Delete pipeline output parquets
    for parquet in CLEANUP_PARQUETS:
        p = Path(parquet)
        if p.exists():
            if dry_run:
                print(f"  [DRY RUN] Would delete {parquet}")
            else:
                p.unlink()
                print(f"  Deleted {parquet}")

    print("\nCleanup complete." if not dry_run else "\n[DRY RUN] No files were deleted.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Full pipeline cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    args = parser.parse_args()

    print("=== Pipeline Cleanup ===\n")
    cleanup_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
