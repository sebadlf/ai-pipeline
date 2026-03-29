"""Promote the best trained model per cluster to MLflow Model Registry.

For each cluster, finds the training run with the highest val_acc that has
a checkpoint artifact, registers it, and sets a 'champion' alias.

Usage:
    uv run python -m src.evaluation.promote
    uv run python -m src.evaluation.promote --cluster Technology_0
"""

from __future__ import annotations

import argparse

import mlflow
import polars as pl
from mlflow.tracking import MlflowClient

from src.config import ClusterConfig, load_config
from src.keys import MLFLOW_TRACKING_URI

MODEL_NAME_PREFIX = "trading-forecaster"


def promote_cluster_model(client: MlflowClient, cluster_id: str, prefix: str = "cluster") -> bool:
    """Find and promote the best model for a single cluster.

    Args:
        client: MLflow client.
        cluster_id: Cluster identifier.
        prefix: Experiment name prefix.

    Returns:
        True if a model was promoted, False otherwise.
    """
    experiment_name = f"{prefix}/{cluster_id}"
    experiment = client.get_experiment_by_name(experiment_name)

    if experiment is None:
        print(f"  No experiment found for {cluster_id}")
        return False

    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="metrics.val_acc > 0",
        order_by=["metrics.val_acc DESC"],
        max_results=10,
    )

    if not runs:
        print(f"  No runs with val_acc for {cluster_id}")
        return False

    # Find best run with checkpoint
    for run in runs:
        artifacts = client.list_artifacts(run.info.run_id)
        ckpt_artifacts = [a for a in artifacts if a.path.startswith("checkpoints")]

        if not ckpt_artifacts:
            # Check for direct checkpoint files
            ckpt_files = [a for a in artifacts if a.path.endswith(".ckpt")]
            if not ckpt_files:
                continue
            best_ckpt = ckpt_files[0].path
        else:
            inner = client.list_artifacts(run.info.run_id, ckpt_artifacts[0].path)
            ckpt_files = [a.path for a in inner if a.path.endswith(".ckpt")]
            if not ckpt_files:
                continue
            best_ckpt = ckpt_files[0]

        run_id = run.info.run_id
        run_name = run.data.tags.get("mlflow.runName", run_id[:12])
        val_acc = run.data.metrics.get("val_acc", 0)
        test_acc = run.data.metrics.get("test_acc", 0)

        print(f"  {cluster_id}: best run {run_name} (val_acc={val_acc:.4f}, test_acc={test_acc:.4f})")

        # Register model
        model_name = f"{MODEL_NAME_PREFIX}-{cluster_id}"
        try:
            client.create_registered_model(model_name)
        except mlflow.exceptions.MlflowException:
            pass

        artifact_uri = f"runs:/{run_id}/{best_ckpt}"
        mv = client.create_model_version(
            name=model_name,
            source=artifact_uri,
            run_id=run_id,
        )
        client.set_registered_model_alias(model_name, "champion", mv.version)
        print(f"  Registered {model_name} v{mv.version} as champion")
        return True

    print(f"  No checkpoint found for {cluster_id}")
    return False


def promote_all_clusters(config: dict) -> None:
    """Promote the best model for each cluster.

    Args:
        config: Full config dict.
    """
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient()

    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))
    train_cfg = config.get("training", {})
    prefix = train_cfg.get("cluster_experiment_prefix", "cluster")

    clusters_df = pl.read_parquet(cluster_cfg.output_parquet)
    cluster_ids = clusters_df["cluster_id"].unique().sort().to_list()

    promoted = 0
    for cluster_id in cluster_ids:
        if promote_cluster_model(client, cluster_id, prefix):
            promoted += 1

    print(f"\nPromoted {promoted}/{len(cluster_ids)} cluster models")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Promote best models to registry")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    parser.add_argument("--cluster", default=None, help="Promote a single cluster")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.cluster:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        client = MlflowClient()
        prefix = config.get("training", {}).get("cluster_experiment_prefix", "cluster")
        promote_cluster_model(client, args.cluster, prefix)
    else:
        promote_all_clusters(config)


if __name__ == "__main__":
    main()
