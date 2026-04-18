---
date: 2026-04-18
status: accepted
tags: [adr, infra, ml, macos]
---

# ADR-001: Docker híbrido — infraestructura en contenedores, compute nativo

## Contexto

El pipeline corre en Mac Mini M4 Pro (Apple Silicon, 24GB RAM). PyTorch soporta MPS (Metal Performance Shaders) para GPU acceleration, pero **MPS no es accesible desde dentro de Docker** en Apple Silicon: Docker corre una VM Linux que no tiene passthrough al GPU de Metal. Entrenar dentro de Docker obliga a usar CPU, lo que multiplica varias veces el tiempo de training.

Al mismo tiempo, servicios stateful (Postgres con TimescaleDB, MLflow server) se benefician de containerización: aislamiento, versionado, reproducibilidad, volúmenes persistentes, networking declarativo.

## Decisión

Split híbrido:

- **Docker Compose**: Postgres + TimescaleDB, MLflow Tracking Server (v3.10.1). Volúmenes `./pgdata` y `mlflow-artifacts`. Red `ml-network`.
- **Nativo en macOS**: toda la parte de cómputo (ingestion, features, clustering, training con MPS, Optuna, portfolio, backtest). PyTorch Lightning con `accelerator="mps"`.

## Alternativas consideradas

### Opción A: Todo en Docker
- Pro: reproducibilidad total, un solo comando para levantar
- Contra: sin MPS, training 5-10x más lento en CPU. Inaceptable para iteración.

### Opción B: Todo nativo
- Pro: máxima performance
- Contra: setup de Postgres + MLflow manual, no portable, difícil compartir entorno

### Opción C: Docker para todo excepto training (este split)
- Pro: MPS disponible, infra estable y versionada
- Contra: dos planos de ejecución que coordinar

## Consecuencias

- `docker-compose.yml` solo tiene Postgres y MLflow. Nada de PyTorch ahí.
- DataLoader workers = 0 en macOS (conflicto entre MPS y multiprocessing/fork)
- Training paralelo entre clusters usa `multiprocessing` con `spawn` context (obligatorio para MPS safety)
- Workers en subprocesos llaman `dispose_engine()` al salir para liberar conexiones SQLAlchemy
- Cualquier persona clonando el repo en Linux/x86 tiene que deshabilitar MPS en `Trainer` (o caer a CPU); en Apple Silicon, el setup "just works"

## Referencias

- CLAUDE.md — sección "Architecture decisions / Hybrid Docker / Native split"
- `docker-compose.yml` en el repo
