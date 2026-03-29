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
