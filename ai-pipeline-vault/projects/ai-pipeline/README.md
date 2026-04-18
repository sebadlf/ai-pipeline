---
tags: [project, trading, ml, pipeline]
status: active
repo: github.com/sebadlf/ai-pipeline
---

# AI Pipeline

Pipeline ML local para evaluar estrategias de trading sobre el universo S&P 500 (~503 tickers). Corre en Mac Mini M4 Pro (24GB) con arquitectura híbrida: infraestructura en Docker (Postgres + MLflow), compute nativo en macOS para aprovechar MPS GPU.

## Links

- Repo: `github.com/sebadlf/ai-pipeline` (local: `~/development/trading/ai-pipeline`)
- Linear team: `Becerra` (prefix `BEC`) — https://linear.app/gravity-code/team/BEC
- Branch format: `sebadlf-bec-{n}-{descripcion}`
- Spec técnica: `CLAUDE.md` en el repo + `docs/` (un archivo por stage)

## Estado actual

- **7 stages**: ingestion → features → clustering → training (Optuna + ensemble) → promotion → aggregation → portfolio → backtesting → signals
- **Stack**: Python 3.12, Polars, PyTorch Lightning (MPS), Optuna, scikit-learn, scipy, MLflow, Postgres + TimescaleDB
- **Toolchain**: `uv`, `ruff` (lint + format), `pytest`. No hay typechecker activo en CI.
- **Dev vs Prod**: `PIPELINE_ENV` controla horizonte histórico (8yr vs 20yr), epochs (10 vs 50), Optuna trials, modo de clustering (sector vs global KMeans).

## Decisiones

- [[ADR-001 — Docker híbrido con compute nativo]] — por qué Postgres/MLflow en Docker pero PyTorch nativo (MPS no funciona dentro de Docker en Apple Silicon)
- [[ADR-002 — Polars sobre pandas]] — memoria 24GB y volumen de features obliga a Polars
- [[ADR-003 — Ensemble top-3 con weighted average]] — por qué no usar un solo champion por cluster

## Notas de dominio

- [[Feature engineering y selección]]
- [[Normalización con stats persistentes]]
- [[Clustering de stocks]]
- [[Optuna y overfitting gap penalty]]
- [[Promotion cascading y precision-at-threshold]]
- [[Regime detection y backtesting]]

## Runbooks

- [[Setup desde cero]]
- [[Correr el pipeline end-to-end]]
- [[Cleanup de MLflow runs]]

## Planes en curso

- [[Integración Claude+Obsidian+Linear+GitHub — pendientes]] — pasos restantes del setup inicial (smoke-test de flow, CI validation, retro)
