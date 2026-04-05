"""Centralized environment variable loading.

All secrets and configuration keys are loaded here from .env
and accessed by the rest of the project via this module.
"""

from dotenv import load_dotenv
import os

load_dotenv()

# FMP API
FMP_API_KEY: str = os.getenv("FMP_API_KEY", "")

# PostgreSQL
POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB: str = os.getenv("POSTGRES_DB", "trading")
POSTGRES_USER: str = os.getenv("POSTGRES_USER", "trading")
POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "changeme")

# MLflow
MLFLOW_TRACKING_URI: str = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")

# Optuna storage (defaults to same Postgres used by the pipeline, psycopg v3 driver)
OPTUNA_STORAGE_URL: str = os.getenv(
    "OPTUNA_STORAGE_URL",
    f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)

# Pipeline environment: "dev" (default) or "prod"
PIPELINE_ENV: str = os.getenv("PIPELINE_ENV", "dev")
