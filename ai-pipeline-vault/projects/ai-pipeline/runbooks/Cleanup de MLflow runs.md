---
last_verified: 2026-04-18
tags: [runbook, mlflow, devops]
---

# Runbook: Cleanup de MLflow runs

## Cuándo usar

- `make pipeline-loop` corrió muchos días y acumuló cientos de runs
- MLflow UI se volvió lento
- Artifacts consumen demasiado disco (`mlflow-artifacts` volume)
- Querés empezar un ciclo limpio de experimentación

## Pre-requisitos

- [ ] Confirmar que no hay nada importante en los runs actuales (hacer `make mlflow-report` antes)
- [ ] Backup si querés conservar el histórico: `docker cp trading-mlflow:/mlflow-artifacts ./mlflow-backup-YYYYMMDD`

## Pasos

### Opción A: Cleanup standard (script del repo)

```bash
make cleanup
```

Ejecuta `src/evaluation/clean_runs.py` que:
- Borra runs fallidos o incompletos
- Mantiene los N más recientes por experimento
- Reinicia MLflow server

### Opción B: Reset total

```bash
make down
docker volume rm ai-pipeline_mlflow-artifacts  # ajustar prefix si el proyecto está renombrado
make up
```

Borra toda la historia de MLflow. Los modelos en registry también se pierden — hay que re-correr `make promote` después.

### Opción C: Por experimento específico

```bash
uv run python -m src.evaluation.clean_runs --experiment cluster/Technology_0 --keep 5
```

Mantiene los 5 runs más recientes del cluster Technology_0.

## Verificación

- `curl http://localhost:5000/api/2.0/mlflow/experiments/search -X POST -H "Content-Type: application/json" -d '{}'` devuelve menos experimentos
- MLflow UI carga rápido otra vez
- Disk usage de `mlflow-artifacts` volume bajó (`docker system df -v`)

## Rollback

Si hiciste reset total y necesitás restaurar:

```bash
make down
docker run --rm -v ai-pipeline_mlflow-artifacts:/dest -v $(pwd)/mlflow-backup-YYYYMMDD:/src alpine cp -r /src/. /dest/
make up
```

## Gotchas

- **Champion alias**: borrar un run no borra el alias `champion` en el Model Registry si apuntaba a ese run. Va a quedar colgado. Re-correr `make promote` resuelve.
- **Optuna persistence**: los studies de Optuna están en Postgres, no en MLflow. No los toca este cleanup. Para limpiarlos hay que entrar al Postgres y borrar de las tablas `optuna_*`.

## Historial

| Fecha | Quién | Notas |
|-------|-------|-------|
| 2026-04-18 | sebadlf | Runbook inicial |
