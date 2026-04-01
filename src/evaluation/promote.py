"""Promote the best trained model per cluster to MLflow Model Registry.

For each cluster, finds the most recent training run with a checkpoint,
scores it using validation-period trading metrics (val_trade_sortino by
default), compares against the current registry champion, and only
promotes the candidate when it strictly beats the champion.

Usage:
    uv run python -m src.evaluation.promote
    uv run python -m src.evaluation.promote --cluster Technology_0
"""

from __future__ import annotations

import argparse
from typing import Any

import mlflow
import polars as pl
from mlflow.tracking import MlflowClient

from src.config import ClusterConfig, load_config
from src.keys import MLFLOW_TRACKING_URI

MODEL_NAME_PREFIX = "trading-forecaster"


# --------------------------------------------------------------------------- #
# Scoring helpers                                                              #
# --------------------------------------------------------------------------- #

def build_score_tuple(
    metrics: dict[str, Any],
    promotion_cfg: dict,
) -> tuple[float, ...] | None:
    """Build a comparable score tuple from run metrics and promotion config.

    Returns None when the primary metric is missing.
    """
    primary = promotion_cfg.get("primary_metric", "val_acc")
    higher_is_better = promotion_cfg.get("higher_is_better", True)
    tiebreaks = promotion_cfg.get("tiebreak_metrics", [])

    primary_val = metrics.get(primary)
    if primary_val is None:
        return None

    # Build score tuple — higher is always better after sign flip
    sign = 1.0 if higher_is_better else -1.0
    score = [sign * float(primary_val)]
    for tb in tiebreaks:
        val = metrics.get(tb)
        score.append(sign * float(val) if val is not None else float("-inf"))
    return tuple(score)


def candidate_beats_champion(
    candidate_metrics: dict[str, Any],
    champion_metrics: dict[str, Any] | None,
    promotion_cfg: dict,
) -> tuple[bool, str]:
    """Compare candidate vs champion using promotion config.

    Returns:
        (should_promote, reason) tuple.
    """
    cand_score = build_score_tuple(candidate_metrics, promotion_cfg)

    if cand_score is None:
        return False, "candidate failed guards or missing metrics"

    if champion_metrics is None:
        return True, "no existing champion"

    champ_score = build_score_tuple(champion_metrics, promotion_cfg)

    if champ_score is None:
        return True, "champion failed guards or missing metrics"

    if cand_score > champ_score:
        return True, f"candidate score {cand_score} > champion {champ_score}"

    return False, f"candidate score {cand_score} <= champion {champ_score}"


# --------------------------------------------------------------------------- #
# Checkpoint resolution                                                        #
# --------------------------------------------------------------------------- #

def _find_run_checkpoint(client: MlflowClient, run_id: str) -> str | None:
    """Return the artifact path to a .ckpt file in the run, or None."""
    artifacts = client.list_artifacts(run_id)
    ckpt_dirs = [a for a in artifacts if a.path.startswith("checkpoints")]

    if ckpt_dirs:
        inner = client.list_artifacts(run_id, ckpt_dirs[0].path)
        ckpts = [a.path for a in inner if a.path.endswith(".ckpt")]
        if ckpts:
            return ckpts[0]

    # Direct checkpoint files at root level
    ckpts = [a for a in artifacts if a.path.endswith(".ckpt")]
    if ckpts:
        return ckpts[0].path

    return None


# --------------------------------------------------------------------------- #
# Per-cluster promotion                                                        #
# --------------------------------------------------------------------------- #

def promote_cluster_model(
    client: MlflowClient,
    cluster_id: str,
    promotion_cfg: dict,
    prefix: str = "cluster",
) -> bool:
    """Evaluate and conditionally promote the latest model for a cluster.

    Args:
        client: MLflow client.
        cluster_id: Cluster identifier.
        promotion_cfg: Promotion config section from default.yaml.
        prefix: Experiment name prefix.

    Returns:
        True if a model was promoted, False otherwise.
    """
    experiment_name = f"{prefix}/{cluster_id}"
    experiment = client.get_experiment_by_name(experiment_name)

    if experiment is None:
        print(f"  No experiment found for {cluster_id}")
        return False

    # Find the most recent run with a checkpoint (candidate)
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="",
        order_by=["attribute.end_time DESC"],
        max_results=10,
    )

    if not runs:
        print(f"  No runs found for {cluster_id}")
        return False

    # Pick first run that has a usable checkpoint
    candidate_run = None
    best_ckpt = None
    for run in runs:
        ckpt = _find_run_checkpoint(client, run.info.run_id)
        if ckpt is not None:
            candidate_run = run
            best_ckpt = ckpt
            break

    if candidate_run is None:
        print(f"  No checkpoint found for {cluster_id}")
        return False

    candidate_metrics = candidate_run.data.metrics
    run_id = candidate_run.info.run_id
    run_name = candidate_run.data.tags.get("mlflow.runName", run_id[:12])

    primary = promotion_cfg.get("primary_metric", "val_trade_sortino")
    primary_val = candidate_metrics.get(primary, "N/A")
    print(f"  {cluster_id}: candidate run {run_name} ({primary}={primary_val})")

    # Load current champion metrics (if any)
    model_name = f"{MODEL_NAME_PREFIX}-{cluster_id}"
    champion_metrics: dict[str, Any] | None = None

    try:
        mv = client.get_model_version_by_alias(model_name, "champion")
        champion_run = client.get_run(mv.run_id)
        champion_metrics = champion_run.data.metrics
        champ_primary = champion_metrics.get(primary, "N/A")
        print(f"    current champion: run {mv.run_id[:12]} ({primary}={champ_primary})")
    except mlflow.exceptions.MlflowException:
        print(f"    no existing champion for {model_name}")

    # Compare
    should_promote, reason = candidate_beats_champion(
        candidate_metrics, champion_metrics, promotion_cfg,
    )

    if not should_promote:
        print(f"    SKIP: {reason}")
        return False

    # Register and set champion alias
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

    # Set tags for audit
    client.set_model_version_tag(model_name, mv.version, "promotion_metric", primary)
    client.set_model_version_tag(model_name, mv.version, "promotion_score", str(primary_val))
    client.set_model_version_tag(model_name, mv.version, "promotion_reason", reason)

    client.set_registered_model_alias(model_name, "champion", mv.version)
    print(f"    PROMOTED {model_name} v{mv.version} as champion ({reason})")
    return True


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
    promotion_cfg = config.get("promotion", {})

    clusters_df = pl.read_parquet(cluster_cfg.output_parquet)
    cluster_ids = clusters_df["cluster_id"].unique().sort().to_list()

    promoted = 0
    for cluster_id in cluster_ids:
        if promote_cluster_model(client, cluster_id, promotion_cfg, prefix):
            promoted += 1

    print(f"\nPromoted {promoted}/{len(cluster_ids)} cluster models")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Promote best models to registry")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    parser.add_argument("--cluster", default=None, help="Promote a single cluster")
    args = parser.parse_args()

    config = load_config(args.config)
    promotion_cfg = config.get("promotion", {})

    if args.cluster:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        client = MlflowClient()
        prefix = config.get("training", {}).get("cluster_experiment_prefix", "cluster")
        promote_cluster_model(client, args.cluster, promotion_cfg, prefix)
    else:
        promote_all_clusters(config)


if __name__ == "__main__":
    main()
