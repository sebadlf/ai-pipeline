"""Full pipeline cleanup: MLflow experiments, checkpoints, and artifacts.

Permanently deletes all MLflow experiments, runs, registered models,
local checkpoints, MLflow artifact storage, and pipeline output parquets.
Uses direct SQL against the MLflow database for hard delete (MLflow's API
only supports soft-delete for experiments).

Usage:
    uv run python -m src.evaluation.clean_runs
    uv run python -m src.evaluation.clean_runs --dry-run
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from sqlalchemy import create_engine, text

from src.keys import (
    POSTGRES_HOST,
    POSTGRES_DB,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)

MLFLOW_DB = "mlflow"

CLEANUP_PARQUETS = [
    "data/clusters.parquet",
    "data/predictions.parquet",
    "data/portfolios.parquet",
]


def _get_mlflow_engine():
    """Build SQLAlchemy engine for the MLflow database."""
    url = f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{MLFLOW_DB}"
    return create_engine(url)


def cleanup_all(dry_run: bool = False) -> None:
    """Delete all MLflow state, checkpoints, and pipeline outputs."""

    # 1. Drop and recreate the entire MLflow database
    engine = _get_mlflow_engine()
    if dry_run:
        print("  [DRY RUN] Would drop and recreate mlflow database")
    else:
        # Connect to 'postgres' db to drop/create mlflow
        root_url = f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/postgres"
        root_engine = create_engine(root_url, isolation_level="AUTOCOMMIT")
        with root_engine.connect() as conn:
            # Terminate active connections to mlflow DB
            conn.execute(
                text(
                    f"""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = '{MLFLOW_DB}' AND pid <> pg_backend_pid()
            """
                )
            )
            conn.execute(text(f"DROP DATABASE IF EXISTS {MLFLOW_DB}"))
            conn.execute(text(f"CREATE DATABASE {MLFLOW_DB} OWNER {POSTGRES_USER}"))
        root_engine.dispose()
        print("  Dropped and recreated mlflow database")
    engine.dispose()

    # 2. Delete local checkpoints directory
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

    # 3. Delete local MLflow artifacts (mlruns/mlruns/)
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

    # 4. Delete Optuna studies from the trading database
    trading_url = f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    trading_engine = create_engine(trading_url)
    with trading_engine.connect() as conn:
        # Check if Optuna tables exist before attempting cleanup
        result = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'studies')"
            )
        )
        has_optuna = result.scalar()

    if has_optuna:
        if dry_run:
            import optuna

            storage = optuna.storages.RDBStorage(trading_url)
            studies = optuna.study.get_all_study_names(storage)
            print(f"  [DRY RUN] Would delete {len(studies)} Optuna studies: {studies}")
        else:
            import optuna

            storage = optuna.storages.RDBStorage(trading_url)
            studies = optuna.study.get_all_study_names(storage)
            for name in studies:
                optuna.delete_study(study_name=name, storage=storage)
            print(f"  Deleted {len(studies)} Optuna studies")
    else:
        print("  No Optuna tables found, skipping")
    trading_engine.dispose()

    # 5. Delete pipeline output parquets
    for parquet in CLEANUP_PARQUETS:
        p = Path(parquet)
        if p.exists():
            if dry_run:
                print(f"  [DRY RUN] Would delete {parquet}")
            else:
                p.unlink()
                print(f"  Deleted {parquet}")

    if dry_run:
        print("\n[DRY RUN] No files were deleted.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Full pipeline cleanup")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without deleting",
    )
    args = parser.parse_args()

    print("=== Pipeline Cleanup ===\n")
    cleanup_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
