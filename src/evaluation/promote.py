"""Promote the best trained model per cluster to MLflow Model Registry.

Supports two promotion modes:
1. **Cascading elimination** (new): Precision-focused evaluation with walk-forward
   stability, minimum recall, and FP severity tiebreaking. Activated when
   `promotion.evaluation` section exists in config.
2. **Legacy tuple comparison**: Simple metric comparison with tiebreakers.
   Used as fallback when no `evaluation` section is present.

Usage:
    uv run python -m src.evaluation.promote
    uv run python -m src.evaluation.promote --cluster Technology_0
"""

from __future__ import annotations

import argparse
import logging
from typing import Any

import mlflow
import polars as pl
from mlflow.tracking import MlflowClient

from src.config import ClusterConfig, PromotionEvalConfig, load_config
from src.keys import MLFLOW_TRACKING_URI

logger = logging.getLogger(__name__)

MODEL_NAME_PREFIX = "trading-forecaster"


# --------------------------------------------------------------------------- #
# Legacy scoring helpers                                                       #
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


# --------------------------------------------------------------------------- #
# Cascading elimination                                                        #
# --------------------------------------------------------------------------- #


def cascading_compare(
    cand_metrics: dict[str, Any],
    champ_metrics: dict[str, Any] | None,
    promotion_cfg: dict,
) -> tuple[bool, str]:
    """Compare candidate vs champion using cascading elimination.

    Args:
        cand_metrics: Candidate run metrics (includes params as strings).
        champ_metrics: Champion run metrics, or None if no champion.
        promotion_cfg: Full promotion config section.

    Returns:
        (should_promote, reason) tuple.
    """
    eval_config = PromotionEvalConfig.from_dict(promotion_cfg)

    # Check candidate passed all filters
    cand_passed = cand_metrics.get("val_passed_all_filters")
    if cand_passed != "true":
        cand_stage = cand_metrics.get("val_elimination_stage", "unknown")
        return False, f"candidate failed filters ({cand_stage})"

    cand_score = cand_metrics.get("val_stability_score")
    if cand_score is None:
        return False, "candidate missing val_stability_score"
    cand_score = float(cand_score)

    # No champion → promote
    if champ_metrics is None:
        return True, f"no existing champion (score={cand_score:.4f})"

    # Check if champion passed filters
    champ_passed = champ_metrics.get("val_passed_all_filters")
    if champ_passed != "true":
        return True, f"champion failed filters, candidate passed (score={cand_score:.4f})"

    champ_score = champ_metrics.get("val_stability_score")
    if champ_score is None:
        return True, f"champion missing stability_score, candidate has {cand_score:.4f}"
    champ_score = float(champ_score)

    # Compare stability scores
    margin = eval_config.tiebreak_margin
    if cand_score > champ_score + margin:
        return True, f"candidate score {cand_score:.4f} > champion {champ_score:.4f}"

    if cand_score < champ_score - margin:
        return False, f"candidate score {cand_score:.4f} <= champion {champ_score:.4f}"

    # Within tiebreak margin — prefer lower FP severity
    cand_fp_sev = float(cand_metrics.get("val_fp_severity", float("inf")))
    champ_fp_sev = float(champ_metrics.get("val_fp_severity", float("inf")))

    if cand_fp_sev < champ_fp_sev:
        return True, (
            f"tiebreak: candidate fp_severity {cand_fp_sev:.4f} "
            f"< champion {champ_fp_sev:.4f} (scores within {margin})"
        )

    return False, (
        f"tiebreak: candidate fp_severity {cand_fp_sev:.4f} "
        f">= champion {champ_fp_sev:.4f} (scores within {margin})"
    )


# --------------------------------------------------------------------------- #
# Unified comparison                                                           #
# --------------------------------------------------------------------------- #


def candidate_beats_champion(
    candidate_metrics: dict[str, Any],
    champion_metrics: dict[str, Any] | None,
    promotion_cfg: dict,
) -> tuple[bool, str]:
    """Compare candidate vs champion using promotion config.

    Uses cascading elimination when `evaluation` section exists in config,
    otherwise falls back to legacy tuple comparison.

    Returns:
        (should_promote, reason) tuple.
    """
    if "evaluation" in promotion_cfg:
        return cascading_compare(candidate_metrics, champion_metrics, promotion_cfg)

    # Legacy path
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

    # Direct checkpoint files at root level
    ckpts = [a for a in artifacts if a.path.endswith(".ckpt")]
    if ckpts:
        return ckpts[0].path

    # Search inside all artifact directories for .ckpt files
    for artifact in artifacts:
        if artifact.is_dir:
            inner = client.list_artifacts(run_id, artifact.path)
            ckpts = [a.path for a in inner if a.path.endswith(".ckpt")]
            if ckpts:
                return ckpts[0]

    return None


# --------------------------------------------------------------------------- #
# Per-cluster promotion                                                        #
# --------------------------------------------------------------------------- #


def _find_best_candidate(
    client: MlflowClient,
    runs: list,
    promotion_cfg: dict,
) -> tuple[Any | None, str | None]:
    """Find the best candidate run among recent runs.

    For cascading mode: finds the run with highest val_stability_score
    that passed all filters and has a checkpoint.

    For legacy mode: finds the most recent run with a checkpoint.

    Returns:
        (run, checkpoint_path) or (None, None).
    """
    use_cascading = "evaluation" in promotion_cfg

    if not use_cascading:
        # Legacy: first run with checkpoint
        for run in runs:
            ckpt = _find_run_checkpoint(client, run.info.run_id)
            if ckpt is not None:
                return run, ckpt
        return None, None

    # Cascading: collect all runs with checkpoints and classify into tiers
    tier1 = []  # Passed all filters, ranked by stability_score
    tier2 = []  # Failed signals/coverage only, ranked by val_precision_up * gen_ratio
    tier3 = []  # Failed any single filter, ranked by val_precision_up * gen_ratio
    tier4 = []  # Any run with checkpoint (fallback)

    for run in runs:
        ckpt = _find_run_checkpoint(client, run.info.run_id)
        if ckpt is None:
            continue

        all_metrics = {**run.data.metrics, **run.data.params}
        passed = all_metrics.get("val_passed_all_filters")
        score = all_metrics.get("val_stability_score")
        elim_stage = all_metrics.get("val_elimination_stage", "unknown")
        val_prec = float(all_metrics.get("val_precision_up", 0.0))
        test_prec = float(all_metrics.get("test_precision_up", 0.0))

        # Generalization ratio for ranking
        gen_ratio = min(test_prec / val_prec, 1.0) if val_prec > 0 and test_prec > 0 else 0.5
        adjusted_score = val_prec * (1.0 + gen_ratio) / 2.0

        tier4.append((run, ckpt, adjusted_score))

        if passed == "true" and score is not None:
            tier1.append((run, ckpt, float(score)))
        elif elim_stage in ("failed_signals", "failed_coverage"):
            tier2.append((run, ckpt, adjusted_score))
        elif elim_stage != "unknown":
            tier3.append((run, ckpt, adjusted_score))

    # Try tiers in order
    for tier_num, tier in [(1, tier1), (2, tier2), (3, tier3), (4, tier4)]:
        if tier:
            tier.sort(key=lambda x: x[2], reverse=True)
            best_run, best_ckpt, best_score = tier[0]
            # Log the promotion tier
            try:
                client.set_tag(best_run.info.run_id, "promotion_tier", str(tier_num))
            except Exception:
                pass
            return best_run, best_ckpt

    return None, None


def promote_cluster_model(
    client: MlflowClient,
    cluster_id: str,
    promotion_cfg: dict,
    prefix: str = "cluster",
) -> bool:
    """Evaluate and conditionally promote the best model for a cluster.

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

    # Find recent runs
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="",
        order_by=["attribute.end_time DESC"],
        max_results=10,
    )

    if not runs:
        print(f"  No runs found for {cluster_id}")
        return False

    # Find best candidate
    candidate_run, best_ckpt = _find_best_candidate(client, runs, promotion_cfg)

    if candidate_run is None:
        print(f"  No checkpoint found for {cluster_id}")
        return False

    # Merge metrics and params for comparison
    candidate_metrics = {**candidate_run.data.metrics, **candidate_run.data.params}
    run_id = candidate_run.info.run_id
    run_name = candidate_run.data.tags.get("mlflow.runName", run_id[:12])

    use_cascading = "evaluation" in promotion_cfg
    if use_cascading:
        score = candidate_metrics.get("val_stability_score", "N/A")
        stage = candidate_metrics.get("val_elimination_stage", "N/A")
        print(f"  {cluster_id}: candidate run {run_name} (stability_score={score}, stage={stage})")
    else:
        primary = promotion_cfg.get("primary_metric", "val_acc")
        primary_val = candidate_metrics.get(primary, "N/A")
        print(f"  {cluster_id}: candidate run {run_name} ({primary}={primary_val})")

    # Load current champion metrics (if any)
    model_name = f"{MODEL_NAME_PREFIX}-{cluster_id}"
    champion_metrics: dict[str, Any] | None = None

    try:
        mv = client.get_model_version_by_alias(model_name, "champion")
        champion_run = client.get_run(mv.run_id)
        champion_metrics = {**champion_run.data.metrics, **champion_run.data.params}
        if use_cascading:
            champ_score = champion_metrics.get("val_stability_score", "N/A")
            print(f"    current champion: run {mv.run_id[:12]} (stability_score={champ_score})")
        else:
            primary = promotion_cfg.get("primary_metric", "val_acc")
            champ_primary = champion_metrics.get(primary, "N/A")
            print(f"    current champion: run {mv.run_id[:12]} ({primary}={champ_primary})")
    except mlflow.exceptions.MlflowException:
        print(f"    no existing champion for {model_name}")

    # Compare
    should_promote, reason = candidate_beats_champion(
        candidate_metrics,
        champion_metrics,
        promotion_cfg,
    )

    if not should_promote:
        print(f"    SKIP: {reason}")
        return False

    # Register and set champion alias
    try:
        client.create_registered_model(model_name)
    except mlflow.exceptions.MlflowException:
        logger.debug("Model %s already registered", model_name)

    artifact_uri = f"runs:/{run_id}/{best_ckpt}"
    mv = client.create_model_version(
        name=model_name,
        source=artifact_uri,
        run_id=run_id,
    )

    # Set tags for audit
    if use_cascading:
        score_val = candidate_metrics.get("val_stability_score", "N/A")
        client.set_model_version_tag(
            model_name, mv.version, "promotion_metric", "val_stability_score"
        )
        client.set_model_version_tag(model_name, mv.version, "promotion_score", str(score_val))
    else:
        primary = promotion_cfg.get("primary_metric", "val_acc")
        primary_val = candidate_metrics.get(primary, "N/A")
        client.set_model_version_tag(model_name, mv.version, "promotion_metric", primary)
        client.set_model_version_tag(model_name, mv.version, "promotion_score", str(primary_val))
    client.set_model_version_tag(model_name, mv.version, "promotion_reason", reason)

    client.set_registered_model_alias(model_name, "champion", mv.version)
    client.set_registered_model_alias(model_name, "champion-1", mv.version)
    print(f"    PROMOTED {model_name} v{mv.version} as champion ({reason})")

    # Promote ensemble members (rank 2, 3, ...) from the same optimization cycle
    _promote_ensemble_members(client, cluster_id, run_id, model_name, experiment, prefix)

    return True


def _promote_ensemble_members(
    client: MlflowClient,
    cluster_id: str,
    champion_run_id: str,
    model_name: str,
    experiment,
    prefix: str,
) -> None:
    """Promote ensemble members (rank 2+) alongside the champion.

    Finds runs with ensemble_rank > 1 that were created near the champion run,
    and registers them with champion-2, champion-3 aliases.
    """
    # Find the champion run's start time to locate sibling ensemble runs
    champion_run = client.get_run(champion_run_id)
    champion_start = champion_run.info.start_time  # milliseconds

    # Search for recent runs with ensemble_rank params
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="",
        order_by=["attribute.end_time DESC"],
        max_results=20,
    )

    # Find sibling ensemble runs (same optimization cycle, within 2 hours)
    time_window_ms = 2 * 60 * 60 * 1000  # 2 hours
    for run in runs:
        if run.info.run_id == champion_run_id:
            continue
        rank_str = run.data.params.get("ensemble_rank")
        if not rank_str or rank_str == "1":
            continue
        # Check if this run is from the same optimization cycle
        if abs(run.info.start_time - champion_start) > time_window_ms:
            continue

        rank = int(rank_str)
        # Find checkpoint artifact
        artifacts = client.list_artifacts(run.info.run_id, "checkpoints")
        ckpt = next((a.path for a in artifacts if a.path.endswith(".ckpt")), None)
        if not ckpt:
            continue

        artifact_uri = f"runs:/{run.info.run_id}/{ckpt}"
        mv = client.create_model_version(
            name=model_name,
            source=artifact_uri,
            run_id=run.info.run_id,
        )
        alias = f"champion-{rank}"
        client.set_registered_model_alias(model_name, alias, mv.version)
        client.set_model_version_tag(model_name, mv.version, "ensemble_rank", str(rank))
        print(f"    PROMOTED {model_name} v{mv.version} as {alias}")


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
