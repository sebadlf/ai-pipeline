---
last_verified: 2026-04-18
tags: [runbook, pipeline]
---

# Runbook: Correr el pipeline end-to-end

## Cuándo usar

- Sesión de experimentación manual
- Re-training después de cambios en features o modelo
- Refresh diario antes de mirar signals

## Pre-requisitos

- [ ] `make up` corrió y Postgres + MLflow están healthy
- [ ] `.env` con FMP_API_KEY válida
- [ ] `PIPELINE_ENV` setteado (default `dev`; `prod` para correrlo completo)

## Pasos

### Dev rápido (skippea ingestion)

```bash
make pipeline
```

Corre: features → (selection y normalize si hace falta) → cluster → train-clusters → promote → aggregate → portfolio → backtest.

Features y clustering son condicionales: si el parquet ya existe y no cambió el código, se saltean. `make pipeline` decide en base a timestamps.

### Prod (incluye ingestion)

```bash
PIPELINE_ENV=prod make pipeline-prod
```

Agrega `ingest-force` al principio. Ojo con rate limits de FMP.

### Pipeline en loop (iteración nocturna)

```bash
make pipeline-loop
```

Corre el pipeline dev en bucle infinito hasta Ctrl+C. Útil para dejar corriendo y ver trials de Optuna que acumulan histórico en la Postgres.

### Stages individuales

Cuando querés correr un stage aislado (ej. re-promoción después de cambiar `promotion.evaluation` en el YAML):

```bash
make ingest-force           # FMP → Postgres
make features               # Build features parquet
make select-features        # Filter features
make normalize              # Z-score + clip
make cluster                # KMeans
make train-clusters         # Optuna + ensemble training
make promote                # Register champions in MLflow Registry
make aggregate              # Weighted ensemble inference
make portfolio              # 3 profiles optimization
make backtest               # Regime-aware backtest
make signals                # Generate actionable signals
```

## Verificación

Después de `make pipeline`:
- MLflow UI (http://localhost:5000) muestra runs nuevos con métricas
- `data/predictions.parquet` tiene prob_up por símbolo con fecha reciente
- `data/portfolios.parquet` tiene 3 profiles con pesos
- `data/backtest_reports/*.md` está actualizado

Después de `make signals`:
- Output en consola lista stocks con prob_up arriba del threshold por profile
- Tabla `predictions` en Postgres tiene los mismos valores

## Rollback

Si el pipeline falló a mitad de camino y quedó en un estado inconsistente:

```bash
# Eliminar los artifacts del stage problemático
rm -f data/[archivo].parquet

# Si el problema fue en training:
make cleanup   # limpia MLflow runs y reinicia server
```

No hace falta re-ingest — los datos en Postgres son independientes de los artifacts.

## Gotchas

- **Optuna warm-start**: `train-clusters` retoma studies de corridas previas (filtrado por `max_history_days`). Si cambiaste el espacio de búsqueda y querés empezar de cero, hay que borrar los estudios manualmente en Postgres.
- **MLflow run acumulación**: en dev con `pipeline-loop`, MLflow acumula cientos de runs en días. Correr `make cleanup` semanalmente.
- **Cluster count cambia**: si auto-K elige K distinto, los experiments viejos quedan huérfanos (modelos para clusters que ya no existen). El promotion se encarga solo de eso, pero los experiments huérfanos ocupan espacio.

## Historial

| Fecha | Quién | Notas |
|-------|-------|-------|
| 2026-04-18 | sebadlf | Runbook inicial |
