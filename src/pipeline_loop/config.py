"""Constants for the autonomous pipeline improvement loop."""

from __future__ import annotations

from pathlib import Path

# --- Loop limits ---
BUDGET_CYCLES = 20
CAP_ISSUES_PER_CYCLE = 5
MAX_FIX_ATTEMPTS = 3
MAX_CONSECUTIVE_ABANDONS = 3
POLL_INTERVAL_SECONDS = 30
PR_TIMEOUT_MINUTES = 60
PIPELINE_RETRY_WAIT_MINUTES = 10

# --- MLflow cleanup triggers ---
MLFLOW_MAX_RUNS_BEFORE_CLEANUP = 200
MLFLOW_DAYS_SINCE_LAST_CLEANUP = 7

# --- Linear labels ---
LABEL_AUTO = "pipeline-auto"
LABEL_BLOCKED = "auto-blocked"
LABEL_STOP = "loop-stop"

# --- Vault paths (relative to repo root) ---
VAULT_ROOT = Path("ai-pipeline-vault")
LOOP_DIR = VAULT_ROOT / "projects" / "ai-pipeline" / "pipeline-loop"
REPORTS_DIR = LOOP_DIR / "reports"
VERDICT_FILE = LOOP_DIR / "verdict.json"
LOG_FILE = LOOP_DIR / "loop-log.md"
STATE_FILE = LOOP_DIR / "state.json"

# --- Pipeline local data ---
DATA_DIR = Path("data")
STOP_FLAG_FILE = DATA_DIR / ".loop-stop"

# --- Valid verdict values ---
VERDICT_IMPROVE = "improve"
VERDICT_PLATEAU = "plateau"
VERDICT_UNCLEAR = "unclear"
VALID_VERDICTS = (VERDICT_IMPROVE, VERDICT_PLATEAU, VERDICT_UNCLEAR)
