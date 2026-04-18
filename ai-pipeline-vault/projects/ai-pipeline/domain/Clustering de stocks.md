---
tags: [domain, clustering, ml]
---

# Clustering de stocks

## Qué hace

Stage 1 agrupa los ~503 stocks del S&P 500 en clusters de comportamiento similar. Cada cluster entrena su propio modelo en Stage 2 (Optuna per-cluster).

- **Prod**: Global KMeans sobre 20 features (behavioral + macro-sensitivity + fundamentals + sector-relative)
- **Dev**: Sector-based (un cluster por sector GICS) — más rápido, menos exploración de hyperparams

Output: `data/clusters.parquet` + tabla `cluster_assignments` en Postgres.

## Por qué clusters

Un modelo global sobre 503 stocks fuerza al LSTM a aprender patrones promediados. Stocks de servicios públicos (baja vol, dividend-paying, poca sensibilidad macro) tienen dinámicas muy distintas a tech high-growth. Un modelo compartido subserve a ambos.

Con clusters + modelos per-cluster:
- Optuna puede especializar hyperparams (ej. sequence length corto para volátiles, largo para estables)
- La señal es más coherente dentro de cada grupo
- Ensemble cross-cluster (en portfolio stage) diversifica errores

## Features de clustering (20)

Resumen (detalle en `docs/stage-1-clustering.md`):

- **7 behavioral**: volatility realized, beta-to-SPY, skew, kurtosis, max drawdown, return autocorrelation, trading activity
- **2 macro-sensitivity**: sensibilidad a cambios en yield curve y VIX
- **1 sector-relative**: performance relativa al sector
- **4 key metrics**: market cap, PE, dividend yield, revenue growth
- **6 financial ratios**: ROE, ROA, debt/equity, current ratio, gross margin, operating margin

Se toman snapshots en el período de training únicamente.

## Auto-K selection

PCA primero (reteniendo 95% de varianza) para reducir dim. Luego silhouette analysis sobre un rango de K candidatos — se elige el K que maximiza silhouette promedio.

**Merge de clusters chicos**: post-clustering, cualquier cluster con menos de `min_cluster_size` (configurable) se merge al centroide más cercano. Un cluster con 3 stocks no tiene data suficiente para entrenar un modelo decente.

## Gotchas

- **Cluster ID no es estable entre corridas**: re-clusterizar con datos nuevos puede renumerar los clusters o cambiar la pertenencia. Por eso `cluster_assignments` se escribe con timestamp, y `MLflow experiments` usan el cluster_id como nombre (`cluster/{cluster_id}`). Cambiar la partición del universo invalida los modelos anteriores — hay que re-entrenar.
- **Sector-based en dev es intencionalmente crudo**: sirve para iterar rápido, no para evaluar calidad del modelo final. Benchmark real es con global KMeans en prod.

## Referencias

- `docs/stage-1-clustering.md`
- `src/features/clustering.py`
- CLAUDE.md — "Stage 1: Stock Clustering"
