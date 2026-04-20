.PHONY: setup up down ingest ingest-force features select-features normalize cluster optimize-global train-clusters train-global promote aggregate portfolio backtest signals cleanup cleanup-keep-features cleanup-dry-run test mlflow-report mlflow-report-prod pipeline pipeline-prod pipeline-loop

# =============================================================================
# Infrastructure
# =============================================================================

setup:
	uv venv
	uv sync

up:
	docker compose up -d

down:
	docker compose down

# =============================================================================
# Stage 0: Data Ingestion & Feature Engineering
# =============================================================================

# Ingestion - manual only in dev, use 'make ingest-force' when needed
# In prod, this runs automatically via pipeline-prod
ingest:
	@echo "In dev, ingestion is skipped by default."
	@echo "Run 'make ingest-force' if you need fresh data."

ingest-force:
	uv run python -m src.ingestion.fmp_loader

features:
	uv run python -m src.features.technical

select-features:
	uv run python -m src.features.selection

normalize:
	uv run python -m src.features.normalize

# =============================================================================
# Stage 1: Clustering
# =============================================================================

cluster:
	uv run python -m src.features.clustering

# =============================================================================
# Stage 2: Model Training
# =============================================================================

# Per-cluster Optuna optimization with overtuning mitigations
# Each cluster gets its own hyperparameters via 3-fold CV + ensemble top-3
train-clusters:
	uv run python -m src.training.train

# Alias for backward compatibility
train-global: train-clusters

# =============================================================================
# Stage 3: Model Promotion
# =============================================================================

promote:
	uv run python -m src.evaluation.promote

# =============================================================================
# Stage 4: Aggregation
# =============================================================================

aggregate:
	uv run python -m src.aggregation.consolidate

# =============================================================================
# Stage 5: Portfolio Optimization
# =============================================================================

portfolio:
	uv run python -m src.portfolio.optimizer

# =============================================================================
# Stage 6: Backtesting
# =============================================================================

backtest:
	uv run python -m src.evaluation.backtest

# =============================================================================
# Stage 7: Signal Generation
# =============================================================================

signals:
	uv run python -m src.strategy.runner

# =============================================================================
# Full Pipeline
# =============================================================================

# Pipeline for dev - skips ingestion by default
# Always re-runs normalization (cheap vs training, and required so that
# changes to src/features/normalize.py take effect on the next training
# pass — see BEC-41).
pipeline:
	@if [ -f data/.new_data ] || [ ! -f data/clusters.parquet ]; then \
		echo "Rebuilding features/clusters..."; \
		$(MAKE) features select-features normalize cluster; \
		rm -f data/.new_data; \
	else \
		echo "No new data and clusters exist, refreshing normalization only."; \
		$(MAKE) normalize; \
	fi
	$(MAKE) train-clusters promote aggregate portfolio backtest

# Pipeline for prod - includes ingestion
pipeline-prod:
	$(MAKE) ingest-force
	@if [ -f data/.new_data ] || [ ! -f data/clusters.parquet ]; then \
		echo "Rebuilding features/clusters..."; \
		$(MAKE) features select-features normalize cluster; \
		rm -f data/.new_data; \
	else \
		echo "No new data and clusters exist, refreshing normalization only."; \
		$(MAKE) normalize; \
	fi
	$(MAKE) train-clusters promote aggregate portfolio backtest

# Pipeline loop (infinite, Ctrl+C to stop) - uses dev pipeline (no ingestion)
pipeline-loop:
	@i=1; while true; do \
		echo ""; \
		echo "========================================"; \
		echo "  Pipeline iteration $$i — $$(date)"; \
		echo "========================================"; \
		$(MAKE) pipeline || { echo "ERROR in iteration $$i"; exit 1; }; \
		echo "  Iteration $$i complete — $$(date)"; \
		i=$$((i + 1)); \
	done

# =============================================================================
# Utilities
# =============================================================================

cleanup:
	uv run python -m src.evaluation.clean_runs
	docker compose restart mlflow

cleanup-keep-features:
	uv run python -m src.evaluation.clean_runs --keep-features
	docker compose restart mlflow

cleanup-dry-run:
	uv run python -m src.evaluation.clean_runs --dry-run

test:
	uv run pytest tests/ -v

mlflow-report:
	uv run python scripts/mlflow_report.py

mlflow-report-prod:
	MLFLOW_TRACKING_URI=http://192.168.68.64:5000 uv run python scripts/mlflow_report.py

mlflow-runs-report:
	uv run python scripts/mlflow_runs_report.py

mlflow-runs-report-prod:
	MLFLOW_TRACKING_URI=http://192.168.68.64:5000 uv run python scripts/mlflow_runs_report.py
