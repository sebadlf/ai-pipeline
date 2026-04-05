# Propuesta de endpoints FMP para el pipeline de trading ML

Este documento relaciona el objetivo del proyecto (universo S&P 500, features técnicas + macro + fundamentales, clustering, LSTM ternario BUY/SELL/HOLD, carteras y backtest) con endpoints adicionales de [Financial Modeling Prep](https://site.financialmodelingprep.com/developer/docs) documentados en `fmp-docs/stable/`.

**Convención:** URLs base `https://financialmodelingprep.com/stable/...` (misma que usa [`src/ingestion/fmp_loader.py`](../src/ingestion/fmp_loader.py)). Detalle de parámetros: ver el `.md` homónimo en `stable/`.

---

## 1. Qué consume el pipeline hoy

| Uso | Endpoint stable (aprox.) | Notas |
|-----|---------------------------|--------|
| Universo | `sp500-constituent` | Símbolos y sector |
| OHLCV | `historical-price-eod/full` | Precios diarios |
| Ajuste dividendos | `historical-price-eod/dividend-adjusted` | `adj_close` |
| VIX | `historical-price-eod/full` con `^VIX` | Tratado como serie de precios |
| Treasury | `treasury-rates` | Curva y spreads macro |
| Perfil / GICS | `profile` | Sector, industria, beta |
| Fundamentales | `key-metrics`, `ratios` | Trimestral → tablas JSONB |
| Sector histórico | `historical-sector-performance` | Momentum sectorial |

Prueba de conectividad (con API key válida en variable de entorno): los anteriores responden `200` en pruebas recientes; el indicador económico documentado como `economic-indicators` (no `economics-indicators`) también responde correctamente con `name=GDP`.

---

## 2. Endpoints de alto valor para mejorar el pipeline

### 2.1 Calendario y eventos (targets y filtros de régimen)

| Prioridad | Endpoint | Por qué |
|-----------|----------|---------|
| Alta | `earnings-calendar` | Evitar ventanas alrededor de earnings; features binarios “días hasta/después earnings”. |
| Alta | `earnings-company` | Histórico de resultados por símbolo coherente con el calendario. |
| Media | `dividends-company`, `splits-calendar` / `splits-company` | Explicar saltos de precio; ya hay precio ajustado, pero eventos explícitos ayudan a calidad de datos. |
| Media | `economics-calendar` | Alineación de macro (NFP, CPI) con retornos; ampliar el bloque macro más allá de Treasury + VIX. |

Referencias locales: `stable/earnings-calendar.md`, `stable/earnings-company.md`, `stable/economics-calendar.md`.

### 2.2 Sentimiento y expectativas (features alternativos al solo precio)

| Prioridad | Endpoint | Por qué |
|-----------|----------|---------|
| Alta | `financial-estimates` | EPS/revenue estimados vs realizados (sorpresa) como feature de corto plazo. |
| Alta | `price-target-summary`, `ratings-snapshot`, `historical-ratings` | Consenso de analistas y cambios de rating; útil para ranking dentro del cluster y para filtrar señales ruidosas. |
| Media | `grades`, `grades-summary`, `historical-grades` | Otra vista de opinión del sell-side. |

Referencias: `stable/financial-estimates.md`, `stable/price-target-summary.md`, `stable/ratings-snapshot.md`.

### 2.3 Microestructura y riesgo idiosincrático

| Prioridad | Endpoint | Por qué |
|-----------|----------|---------|
| Media | `shares-float`, `historical-market-cap` | Liquidez y tamaño como features de riesgo (el loader ya toca market cap vía perfil; serie histórica enriquece). |
| Media | `stock-price-change` / `quote-change` | Resúmenes de rendimiento multi-periodo si se quieren alinear con el horizonte del modelo sin recalcular todo en Polars. |
| Baja | `aftermarket-quote`, `aftermarket-trade` | Solo si en el futuro el pipeline opera intradía o overnight; hoy es EOD. |

Referencias: `stable/shares-float.md`, `stable/historical-market-cap.md`.

### 2.4 Texto y NLP (etapa experimental)

| Prioridad | Endpoint | Por qué |
|-----------|----------|---------|
| Media | `search-transcripts`, `latest-transcripts`, `transcripts-dates-by-symbol` | Embeddings o sentimiento por trimestre; coste de cómputo y almacenamiento altos. |
| Baja | `stock-news`, `search-stock-news`, `press-releases` | Ruido alto; puede servir para event studies o filtrar crisis. |

Referencias: `stable/search-transcripts.md`, `stable/stock-news.md`.

### 2.5 Institucional e insider (señal lenta, cartera)

| Prioridad | Endpoint | Por qué |
|-----------|----------|---------|
| Media | `insider-trade-statistics`, `latest-insider-trade`, `search-insider-trades` | Agregados de compra/venta insider por símbolo o tiempo. |
| Baja | `latest-filings`, `form-13f-filings-dates`, `filings-extract` | Posicionamiento institucional; más relevante para stock picking que para el LSTM masivo, pero útil como capa de scoring. |

Referencias: `stable/insider-trade-statistics.md`, `stable/latest-filings.md`.

### 2.6 Índices y benchmarks adicionales

| Prioridad | Endpoint | Por qué |
|-----------|----------|---------|
| Media | `historical-sp-500`, `historical-dow-jones`, `historical-nasdaq` | Series de índice explícitas además de derivar todo desde `SPY` u OHLCV. |
| Media | `sp-500` (constituyentes / composición si aplica al contrato del API) | Validar cambios de índice; cruzar con `symbol-change`. |

Referencias: `stable/historical-sp-500.md`, `stable/symbol-changes-list.md`.

### 2.7 Indicadores técnicos precomputados (opcional)

FMP expone muchos endpoints bajo `stable/` (p. ej. `simple-moving-average`, `relative-strength-index`, …). El pipeline **ya calcula** indicadores en Polars; usar la API solo tendría sentido para:

- reducir código mantenido, o  
- contrastar QA frente a la fuente del proveedor.

Si no hay divergencia, **no** aporta señal nueva; valor principal = ahorro de mantenimiento, no alpha.

### 2.8 Bulk (operación a escala S&P 500)

| Prioridad | Endpoint | Por qué |
|-----------|----------|---------|
| Alta | `profile-bulk`, `ratios-bulk`, `key-metrics-ttm-bulk`, `income-statement-bulk`, etc. | Menos llamadas HTTP y menor riesgo de rate limit al ingerir cientos de símbolos. Conviene revisar límites del plan FMP y el tamaño de payload. |

Referencias: `stable/profile-bulk.md`, `stable/rating-bulk.md`, `stable/scores-bulk.md`.

### 2.9 Otros (baja prioridad para este repo)

- **Senado / Cámara** (`senate-trading`, `house-trading`, …): interesante temáticamente, poco correlacionado con el modelo actual por acción del S&P 500.
- **ESG** (`stable/` bajo prefijo esg si está en el índice): encaje solo si se amplía el objetivo de inversión.
- **Cripto / Forex / Commodity**: no alineados con el universo accionario actual.

---

## 3. Recomendación de roadmap corto

1. **Ingesta:** añadir `earnings-calendar` + `earnings-company` (y opcionalmente `economic-indicators` ampliando nombres más allá de lo que ya use el feature engineering).  
2. **Features:** `financial-estimates` + `price-target-summary` o `ratings-snapshot` como columnas por símbolo/fecha (asof join como fundamentales).  
3. **Infra:** migrar rutas críticas a **bulk** donde el plan lo permita.  
4. **Validación:** comparar una muestra de indicadores FMP vs Polars antes de sustituir cálculos propios.

---

## 4. Cómo profundizar en cada endpoint

Cada slug listado tiene su página local: `fmp-docs/stable/<slug>.md`, o el índice completo en [`STABLE_INDEX.md`](STABLE_INDEX.md).
