---
tags: [knowledge, architecture]
---

# Arquitectura — Base de conocimiento

## Patrones de diseño

- [[Pipeline multi-stage con artifacts]] — cada stage lee/escribe archivos explícitos (parquet, json)
- [[Docker híbrido — infra dentro, compute fuera]] — cuándo tiene sentido este split

## Diseño de sistemas

- [[MLflow como source of truth experimental]] — tracking, registry, qué va en artifacts
- [[Postgres + TimescaleDB para time-series]] — hypertables, queries por rango
- [[Optuna con storage persistente]] — warm-starting entre corridas

## ADRs (cross-project)

Las decisiones específicas de cada proyecto van en `projects/[nombre]/decisions/`. Acá van las que aplican a múltiples proyectos.
