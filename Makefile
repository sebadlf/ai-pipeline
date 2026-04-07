.PHONY: setup up down ingest features select-features cluster train train-cluster aggregate portfolio backtest promote signals pipeline pipeline-loop cleanup test mlflow-report mlflow-report-prod

setup:
	uv venv
	uv sync

up:
	docker compose up -d

down:
	docker compose down

# --- Stage 0: Data ingestion ---
ingest:
	uv run python -m src.ingestion.fmp_loader

features:
	uv run python -m src.features.technical

select-features:
	uv run python -m src.features.selection

# --- Stage 1: Clustering ---
cluster:
	uv run python -m src.features.clustering

# --- Stage 2: Per-cluster training ---
train:
	uv run python -m src.training.train

train-cluster:
	uv run python -m src.training.train --cluster $(CLUSTER)

# --- Stage 3: Aggregation ---
aggregate:
	uv run python -m src.aggregation.consolidate

# --- Stage 4: Portfolio optimization ---
portfolio:
	uv run python -m src.portfolio.optimizer

# --- Stage 5: Backtesting ---
backtest:
	uv run python -m src.evaluation.backtest

# --- Promotion & signals ---
promote:
	uv run python -m src.evaluation.promote

signals:
	uv run python -m src.strategy.runner

cleanup:
	uv run python -m src.evaluation.clean_runs
	docker compose restart mlflow

# --- MLflow summary (uses MLFLOW_TRACKING_URI from .env) ---
mlflow-report:
	uv run python scripts/mlflow_report.py

mlflow-report-prod:
	MLFLOW_TRACKING_URI=http://192.168.68.64:5000 uv run python scripts/mlflow_report.py

# --- Full pipeline ---
pipeline:
	$(MAKE) ingest
	@if [ -f data/.new_data ] || [ ! -f data/clusters.parquet ]; then \
		echo "Rebuilding features/clusters..."; \
		$(MAKE) features select-features cluster; \
		rm -f data/.new_data; \
	else \
		echo "No new data and clusters exist, skipping features/selection/clustering."; \
	fi
	$(MAKE) train promote aggregate portfolio backtest

# --- Pipeline loop (infinite, Ctrl+C to stop) ---
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

# --- Tests ---
test:
	uv run pytest tests/ -v
