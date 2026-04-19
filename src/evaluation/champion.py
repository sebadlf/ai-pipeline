"""Shared champion model checkpoint resolution via MLflow Model Registry.

Downloads the champion-aliased model artifact for a given cluster and
returns the local checkpoint path plus the source run_id for lineage.

Usage:
    from src.evaluation.champion import download_champion_checkpoint
    path, run_id = download_champion_checkpoint("Technology_0")
"""

from __future__ import annotations

from pathlib import Path

import mlflow
from mlflow.tracking import MlflowClient

from src.evaluation.promote import MODEL_NAME_PREFIX
from src.keys import MLFLOW_TRACKING_URI


def download_champion_checkpoint(
    cluster_id: str,
    tracking_uri: str = MLFLOW_TRACKING_URI,
) -> tuple[Path, str]:
    """Download the champion checkpoint for a cluster from MLflow registry.

    Args:
        cluster_id: Cluster identifier (e.g. "Technology_0").
        tracking_uri: MLflow tracking URI.

    Returns:
        (local_path, run_id) — path to the downloaded .ckpt file and the
        source run ID for lineage tracking.

    Raises:
        FileNotFoundError: If no champion model is registered for this cluster.
    """
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)

    model_name = f"{MODEL_NAME_PREFIX}-{cluster_id}"

    try:
        mv = client.get_model_version_by_alias(model_name, "champion")
    except mlflow.exceptions.MlflowException as exc:
        raise FileNotFoundError(
            f"No champion model for {model_name}. Run `make promote` after training."
        ) from exc

    # Download artifacts to a local cache directory
    local_dir = mlflow.artifacts.download_artifacts(
        artifact_uri=mv.source,
        tracking_uri=tracking_uri,
    )

    local_path = Path(local_dir)

    # If the download returned a directory, find the .ckpt inside it
    if local_path.is_dir():
        ckpts = list(local_path.glob("*.ckpt"))
        if not ckpts:
            ckpts = list(local_path.rglob("*.ckpt"))
        if not ckpts:
            raise FileNotFoundError(
                f"Champion artifact for {model_name} has no .ckpt file in {local_path}"
            )
        local_path = ckpts[0]

    return local_path, mv.run_id


def download_ensemble_checkpoints(
    cluster_id: str,
    ensemble_k: int = 3,
    tracking_uri: str = MLFLOW_TRACKING_URI,
) -> list[tuple[Path, str]]:
    """Download top-K ensemble checkpoints for a cluster from MLflow registry.

    Tries aliases champion-1, champion-2, ..., champion-K. Falls back to
    single "champion" alias for backward compatibility with pre-ensemble models.

    Args:
        cluster_id: Cluster identifier.
        ensemble_k: Maximum ensemble members to download.
        tracking_uri: MLflow tracking URI.

    Returns:
        List of (local_path, run_id) tuples. At least 1 entry if any champion exists.

    Raises:
        FileNotFoundError: If no champion model is registered for this cluster.
    """
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)
    model_name = f"{MODEL_NAME_PREFIX}-{cluster_id}"

    results = []
    for rank in range(1, ensemble_k + 1):
        alias = f"champion-{rank}"
        try:
            mv = client.get_model_version_by_alias(model_name, alias)
            local_dir = mlflow.artifacts.download_artifacts(
                artifact_uri=mv.source,
                tracking_uri=tracking_uri,
            )
            local_path = Path(local_dir)
            if local_path.is_dir():
                ckpts = list(local_path.glob("*.ckpt")) or list(local_path.rglob("*.ckpt"))
                if not ckpts:
                    continue
                local_path = ckpts[0]
            results.append((local_path, mv.run_id))
        except mlflow.exceptions.MlflowException:
            if rank == 1:
                # Fallback: try plain "champion" alias (pre-ensemble models)
                try:
                    path, run_id = download_champion_checkpoint(cluster_id, tracking_uri)
                    results.append((path, run_id))
                except FileNotFoundError:
                    pass
            break  # stop if champion-N doesn't exist

    if not results:
        raise FileNotFoundError(
            f"No champion model for {model_name}. Run `make promote` after training."
        )

    return results
