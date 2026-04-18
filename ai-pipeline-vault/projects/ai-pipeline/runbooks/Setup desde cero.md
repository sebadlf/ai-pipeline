---
last_verified: 2026-04-18
tags: [runbook, setup]
---

# Runbook: Setup del proyecto desde cero

## Cuándo usar

- Clonaste el repo en una máquina nueva
- Reseteaste tu entorno de desarrollo
- Onboarding de alguien nuevo

## Pre-requisitos

- [ ] macOS (Apple Silicon recomendado para MPS — ver [[ADR-001 — Docker híbrido con compute nativo]])
- [ ] Docker Desktop instalado y corriendo
- [ ] Python 3.12+ disponible (uv lo instala si hace falta)
- [ ] `uv` instalado: `brew install uv` o `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [ ] API key de [financialmodelingprep.com](https://financialmodelingprep.com) (plan pago, alta de cuenta)

## Pasos

### 1. Clonar y entrar

```bash
git clone git@github.com:sebadlf/ai-pipeline.git
cd ai-pipeline
```

### 2. Configurar entorno

```bash
cp .env.example .env
# Editar .env y setear FMP_API_KEY + POSTGRES_PASSWORD
```

### 3. Instalar dependencias

```bash
make setup
# ≡ uv venv + uv sync
```

### 4. Levantar infraestructura (Postgres + MLflow)

```bash
make up
# ≡ docker compose up -d
```

Verificar: `docker ps` debería mostrar `trading-postgres` y `trading-mlflow` healthy. MLflow UI en http://localhost:5000.

### 5. Primera ingestión

```bash
make ingest-force
```

Warning: con `PIPELINE_ENV=prod` esto baja ~20 años de histórico del S&P 500 — puede tardar una hora la primera vez y consumir muchas requests de FMP. En dev (`PIPELINE_ENV=dev`) son 8 años.

### 6. Correr pipeline completo (dev)

```bash
make pipeline
```

Esto corre features → selection → normalize → cluster → train → promote → aggregate → portfolio → backtest.

## Verificación

- `data/features_normalized.parquet` existe y pesa > 100MB
- `data/clusters.parquet` tiene ~503 filas con `cluster_id` asignado
- MLflow UI muestra experimentos `cluster/*` con runs completados
- `data/backtest_reports/` tiene markdown de los 3 profiles

## Rollback

Si algo se rompió irreparablemente:

```bash
make down
rm -rf pgdata mlruns data/*
make up
```

Vas a perder todo. Primera corrida de nuevo toma ~1hr en dev.

## Gotchas conocidos

- **DataLoader workers = 0 en macOS**: si el trainer tira errores de fork/spawn, confirmá que `num_workers=0` en `TradingDataModule`
- **MPS out of memory**: bajar `batch_size` en config. MPS no libera memoria agresivamente entre epochs.
- **Docker container trading-postgres unhealthy**: borrar `pgdata/` suele ser la salida (perdés la DB). Alternativa: `docker exec -it trading-postgres pg_isready -U trading` para diagnosticar.

## Historial

| Fecha | Quién | Notas |
|-------|-------|-------|
| 2026-04-18 | sebadlf | Runbook inicial al armar vault |
