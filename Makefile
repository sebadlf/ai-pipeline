.PHONY: setup up down ingest features train evaluate promote signals pipeline

setup:
	uv venv
	uv sync

up:
	docker compose up -d

down:
	docker compose down

ingest:
	uv run python -m src.ingestion.fmp_loader

features:
	uv run python -m src.features.technical

train:
	uv run python -m src.training.train

evaluate:
	uv run python -m src.evaluation.backtest

promote:
	uv run python -m src.evaluation.promote

signals:
	uv run python -m src.strategy.runner

pipeline: ingest features train evaluate
