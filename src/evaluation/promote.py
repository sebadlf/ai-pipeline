"""Promote the best trained model to MLflow Model Registry.

Finds the training run with the highest val_acc that has a checkpoint
artifact, registers it, and sets the 'champion' alias.

Usage:
    uv run python -m src.evaluation.promote
"""

from __future__ import annotations

import mlflow
from mlflow.tracking import MlflowClient

from src.keys import MLFLOW_TRACKING_URI

MODEL_NAME = "trading-forecaster"


def promote_best_model() -> None:
    """Find the training run with the best val_acc and promote it."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient()

    experiment = client.get_experiment_by_name("trading-forecaster")
    if experiment is None:
        print("No experiment found. Run training first.")
        return

    # Search training runs (have val_acc), sorted by best val_acc
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="metrics.val_acc > 0",
        order_by=["metrics.val_acc DESC"],
        max_results=20,
    )

    if not runs:
        print("No training runs with val_acc found.")
        return

    # Find the best run that actually has a checkpoint artifact
    best_run = None
    best_ckpt_path = None

    for run in runs:
        top_artifacts = [a.path for a in client.list_artifacts(run.info.run_id)]
        ckpt_dirs = [a for a in top_artifacts if a.startswith("best-")]
        if not ckpt_dirs:
            continue

        inner = client.list_artifacts(run.info.run_id, ckpt_dirs[0])
        ckpt_files = [a.path for a in inner if a.path.endswith(".ckpt")]
        if ckpt_files:
            best_run = run
            best_ckpt_path = ckpt_files[0]
            break

    if best_run is None:
        print("No training run with a checkpoint artifact found.")
        return

    run_id = best_run.info.run_id
    run_name = best_run.data.tags.get("mlflow.runName", run_id[:12])
    val_acc = best_run.data.metrics.get("val_acc", 0)
    test_acc = best_run.data.metrics.get("test_acc", 0)
    print(f"Best training run: {run_name}")
    print(f"  run_id:   {run_id}")
    print(f"  val_acc:  {val_acc:.4f}")
    print(f"  test_acc: {test_acc:.4f}")
    print(f"  checkpoint: {best_ckpt_path}")

    # Register model
    try:
        client.create_registered_model(MODEL_NAME)
        print(f"Created registered model '{MODEL_NAME}'")
    except mlflow.exceptions.MlflowException:
        pass

    artifact_uri = f"runs:/{run_id}/{best_ckpt_path}"
    mv = client.create_model_version(
        name=MODEL_NAME,
        source=artifact_uri,
        run_id=run_id,
    )
    print(f"Registered model version {mv.version}")

    client.set_registered_model_alias(MODEL_NAME, "champion", mv.version)
    print(f"Model version {mv.version} aliased as 'champion'.")


def main() -> None:
    """Entry point."""
    promote_best_model()


if __name__ == "__main__":
    main()
