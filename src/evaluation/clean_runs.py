"""Full pipeline cleanup: MLflow, Optuna, checkpoints, artifacts, and pipeline outputs.

Permanently deletes all MLflow experiments, runs, registered models,
Optuna studies, local checkpoints, MLflow artifact storage, pipeline
output parquets, normalization stats, backtest reports, and pipeline
DB tables (cluster_assignments, predictions, portfolio_allocations,
backtest_results).

Uses direct SQL against the MLflow database for hard delete (MLflow's API
only supports soft-delete for experiments).

Usage:
    uv run python -m src.evaluation.clean_runs
    uv run python -m src.evaluation.clean_runs --dry-run
    uv run python -m src.evaluation.clean_runs --keep-features
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

# Pipeline output files to delete
CLEANUP_PARQUETS = [
    "data/clusters.parquet",
    "data/predictions.parquet",
    "data/portfolios.parquet",
    "data/features_selected.parquet",
    "data/features_normalized.parquet",
]

CLEANUP_FILES = [
    "data/selected_features.json",
    "data/normalization_stats.json",
]

# Pipeline DB tables to truncate (order matters for foreign keys)
PIPELINE_TABLES = [
    "backtest_results",
    "portfolio_allocations",
    "predictions",
    "cluster_assignments",
]


def _get_mlflow_engine():
    """Build SQLAlchemy engine for the MLflow database."""
    url = f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{MLFLOW_DB}"
    return create_engine(url)


def _get_trading_engine():
    """Build SQLAlchemy engine for the trading database."""
    url = f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    return create_engine(url)


def cleanup_all(dry_run: bool = False, keep_features: bool = False) -> None:
    """Delete all MLflow state, Optuna studies, checkpoints, and pipeline outputs.

    Args:
        dry_run: Show what would be deleted without actually deleting.
        keep_features: Keep features.parquet (skip re-computing from DB).
    """
    print("1/7  MLflow database")
    _cleanup_mlflow_db(dry_run)

    print("\n2/7  Optuna studies")
    _cleanup_optuna(dry_run)

    print("\n3/7  Pipeline DB tables")
    _cleanup_pipeline_tables(dry_run)

    print("\n4/7  Local checkpoints")
    _cleanup_directory("checkpoints", dry_run)

    print("\n5/7  Local MLflow artifacts")
    _cleanup_directory("mlruns/mlruns", dry_run)

    print("\n6/7  Pipeline output files")
    _cleanup_output_files(dry_run, keep_features)

    print("\n7/7  Backtest reports")
    _cleanup_directory("data/backtest_reports", dry_run, recreate=True)

    # Touch .new_data flag so next `make pipeline` rebuilds everything
    new_data_flag = Path("data/.new_data")
    if not dry_run:
        new_data_flag.parent.mkdir(parents=True, exist_ok=True)
        new_data_flag.touch()
        print(f"\nTouched {new_data_flag} — next `make pipeline` will rebuild features/clusters")
    else:
        print(f"\n[DRY RUN] Would touch {new_data_flag}")

    if dry_run:
        print("\n[DRY RUN] No files were deleted.")
    else:
        print("\nCleanup complete. Run `docker compose restart mlflow` to reinitialize MLflow.")


def _cleanup_mlflow_db(dry_run: bool) -> None:
    """Drop and recreate the MLflow database."""
    if dry_run:
        print("  [DRY RUN] Would drop and recreate mlflow database")
        return
    try:
        root_url = f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/postgres"
        root_engine = create_engine(root_url, isolation_level="AUTOCOMMIT")
        with root_engine.connect() as conn:
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
    except Exception as e:
        print(f"  Could not connect to database: {e}")


def _cleanup_optuna(dry_run: bool) -> None:
    """Delete all Optuna studies from the trading database."""
    try:
        trading_engine = _get_trading_engine()
        with trading_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'studies')"
                )
            )
            has_optuna = result.scalar()
    except Exception as e:
        print(f"  Could not connect to database: {e}")
        return

    if has_optuna:
        if dry_run:
            import optuna

            trading_url = f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
            storage = optuna.storages.RDBStorage(trading_url)
            studies = optuna.study.get_all_study_names(storage)
            print(f"  [DRY RUN] Would delete {len(studies)} Optuna studies: {studies}")
        else:
            import optuna

            trading_url = f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
            storage = optuna.storages.RDBStorage(trading_url)
            studies = optuna.study.get_all_study_names(storage)
            for name in studies:
                optuna.delete_study(study_name=name, storage=storage)
            print(f"  Deleted {len(studies)} Optuna studies")
    else:
        print("  No Optuna tables found, skipping")
    trading_engine.dispose()


def _cleanup_pipeline_tables(dry_run: bool) -> None:
    """Truncate pipeline output tables in the trading database."""
    try:
        trading_engine = _get_trading_engine()
        with trading_engine.connect() as conn:
            for table in PIPELINE_TABLES:
                result = conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                        "WHERE table_name = :table)"
                    ),
                    {"table": table},
                )
                if not result.scalar():
                    print(f"  Table {table} does not exist, skipping")
                    continue

                count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = count_result.scalar()

                if dry_run:
                    print(f"  [DRY RUN] Would truncate {table} ({count:,} rows)")
                else:
                    conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                    print(f"  Truncated {table} ({count:,} rows)")
            if not dry_run:
                conn.commit()
        trading_engine.dispose()
    except Exception as e:
        print(f"  Could not connect to database: {e}")


def _cleanup_directory(path: str, dry_run: bool, recreate: bool = False) -> None:
    """Delete a directory and optionally recreate it empty."""
    dir_path = Path(path)
    if dir_path.exists():
        n_files = sum(1 for _ in dir_path.rglob("*") if _.is_file())
        if dry_run:
            print(f"  [DRY RUN] Would delete {path}/ ({n_files} files)")
        else:
            shutil.rmtree(dir_path)
            print(f"  Deleted {path}/ ({n_files} files)")
            if recreate:
                dir_path.mkdir(parents=True, exist_ok=True)
    else:
        print(f"  {path}/ not found, skipping")


def _cleanup_output_files(dry_run: bool, keep_features: bool) -> None:
    """Delete pipeline output parquets and metadata files."""
    all_files = CLEANUP_PARQUETS + CLEANUP_FILES

    for filepath in all_files:
        p = Path(filepath)
        if not p.exists():
            continue
        if dry_run:
            print(f"  [DRY RUN] Would delete {filepath}")
        else:
            p.unlink()
            print(f"  Deleted {filepath}")

    # features.parquet — only delete if --keep-features is not set
    features_path = Path("data/features.parquet")
    if features_path.exists():
        if keep_features:
            print(f"  Kept {features_path} (--keep-features)")
        elif dry_run:
            print(f"  [DRY RUN] Would delete {features_path}")
        else:
            features_path.unlink()
            print(f"  Deleted {features_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Full pipeline cleanup")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without deleting",
    )
    parser.add_argument(
        "--keep-features",
        action="store_true",
        help="Keep features.parquet (skip re-computing technical indicators from DB)",
    )
    args = parser.parse_args()

    print("=== Pipeline Cleanup ===\n")
    cleanup_all(dry_run=args.dry_run, keep_features=args.keep_features)


if __name__ == "__main__":
    main()
