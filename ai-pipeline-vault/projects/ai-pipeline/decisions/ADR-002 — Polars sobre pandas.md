---
date: 2026-04-18
status: accepted
tags: [adr, data, python]
---

# ADR-002: Polars sobre pandas para feature engineering

## Contexto

Feature engineering procesa ~503 stocks del S&P 500 × ~5000 días de histórico (prod: 20 años) × ~200 features. El dataset completo no entra cómodamente en 24GB de RAM con pandas (que copia agresivamente y tiene overhead por el índice). Además, rolling windows multi-símbolo con pandas requieren groupby + apply que son órdenes de magnitud más lentos que los equivalentes en Polars.

## Decisión

Polars como motor de feature engineering. pandas solo se usa donde una librería upstream lo exige (ej. scikit-learn consume numpy/pandas en algunos paths — pero igual hacemos el `.to_numpy()` explícito).

## Alternativas consideradas

### Opción A: pandas
- Pro: ecosistema maduro, todo el mundo lo sabe
- Contra: memoria y velocidad insuficientes para el volumen de este pipeline

### Opción B: Polars (esta decisión)
- Pro: columnar, lazy, multi-threaded, mucho menos RAM. Expresiones declarativas para rolling windows
- Contra: API distinta, menos Stack Overflow hits, algunas libs downstream piden pandas

### Opción C: Dask
- Pro: escalado horizontal si algún día salimos del Mac
- Contra: overkill para un pipeline local, complejidad extra, performance peor que Polars para este tamaño

## Consecuencias

- Todo el código en `src/features/` es Polars nativo
- Cuando hay que interoperar con scikit-learn o scipy, se hace `.to_numpy()` explícito
- Los parquet files (`data/features*.parquet`) se leen/escriben con Polars
- Devs nuevos al proyecto tienen que aprender Polars — agregar link en `knowledge/python/`

## Referencias

- `src/features/technical.py`
- CLAUDE.md — "Constraints and preferences / RAM: 24GB → prefer Polars"
