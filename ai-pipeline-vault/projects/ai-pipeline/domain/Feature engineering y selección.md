---
tags: [domain, features, ml]
---

# Feature engineering y selección

## Qué hace

Pipeline de 3 pasos antes del training:

1. **Construcción** (`src/features/technical.py`) — Polars lee OHLCV + macro + fundamentals + sector performance de Postgres y calcula ~200 features en ventanas múltiples (5/10/20/50/200). Output: `data/features.parquet`.
2. **Selección** (`src/features/selection.py`) — filtra por null rate (>90%), varianza (bottom 1%), correlación (>0.95 entre pares) y mutual information (<0.01). Output: `data/features_selected.parquet` + `data/selected_features.json` manifest.
3. **Normalización** (`src/features/normalize.py`) — computa stats del training set (mean, std, p01, p99), clippea outliers a [p01, p99], aplica Z-score. Output: `data/features_normalized.parquet` + `data/normalization_stats.json`.

## Por qué importa

### Adj close para indicadores
Todos los indicadores derivados de precio (SMA, EMA, RSI, MACD, Bollinger, ATR) usan `adj_close` cuando está disponible. Si usaran `close`, habría inconsistencia con el target binario (que se calcula sobre adj_close por dividendos/splits). Esa inconsistencia genera señal espuria.

### Normalización con stats persistentes
Las stats del training set se guardan en `normalization_stats.json` y se reusan en aggregation + inference. Si normalizáramos "globalmente" (incluyendo val/test) estaríamos filtrando información del futuro al modelo. Drift detection compara las stats de inference-time con las del training: si la distribución se corrió >3 std, se loggea warning.

### Null handling
- **Fundamentals**: forward-fill por símbolo (los datos quarterly se propagan hasta el próximo quarter)
- **Remanentes**: median-fill por símbolo
- **Returns/target nulos**: drop de la fila (no inventar target)

## Features incluidas (referencia)

Para el listado completo ver `docs/stage-0-features.md` en el repo. Categorías:
- Technical (SMA/EMA/RSI/MACD/BB/ATR/Stochastic/Volume SMA)
- Returns (1d/5d/20d) y volatility multi-window
- Volume (OBV ROC, relative volume)
- Macro (12 tenors treasury + spreads + lagged)
- VIX (close, SMA, percentile rank, lagged)
- Cross-sectional (relative strength vs SPY)
- Fundamentals (~40 key metrics + ratios, QoQ changes)
- Sector performance + relative-to-sector
- Cyclical time encoding (sin/cos day-of-week, month-of-year)

## Gotchas descubiertos

- La normalización inline en `dataset.py` y la LayerNorm en el modelo fueron **removidas**: reemplazadas por este paso dedicado para tener una sola source of truth y evitar re-computar stats en cada epoch.
- Feature selection se corre una sola vez sobre el training set. Re-correr el pipeline con datos nuevos puede cambiar el conjunto seleccionado — tracking del manifest es crítico para reproducibilidad en inference.

## Referencias

- `docs/stage-0-features.md` — listado completo y detalles
- `src/features/{technical,selection,normalize}.py`
- [[ADR-002 — Polars sobre pandas]]
