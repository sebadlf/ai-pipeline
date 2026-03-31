.PHONY: setup up down ingest features select-features cluster train train-cluster aggregate portfolio backtest promote signals pipeline test

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

# --- Full pipeline ---
pipeline: ingest features select-features cluster train aggregate portfolio backtest

# --- Tests ---
test:
	uv run pytest tests/ -v
