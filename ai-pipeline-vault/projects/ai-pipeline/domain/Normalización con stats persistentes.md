---
tags: [domain, features, normalization, ml]
---

# Normalización con stats persistentes

## El patrón

En lugar de normalizar inline dentro del `Dataset` (recalculando stats cada epoch) o usar LayerNorm en la entrada del modelo, hacemos **normalización como step explícito** en el pipeline:

1. Leer `features_selected.parquet`.
2. Subset al período de training (según `SplitDates`).
3. Calcular mean, std, p01, p99 **por feature** sobre el training set únicamente.
4. Clippear outliers a [p01, p99] en todo el dataset.
5. Aplicar Z-score con las stats del training.
6. Guardar stats en `data/normalization_stats.json` y dataset normalizado en `data/features_normalized.parquet`.

## Por qué

### No leak del futuro
Si calculamos mean/std sobre todo el dataset (train + val + test), estamos dándole al modelo información sobre la distribución de val/test — un leak sutil pero real. Con stats-del-training, val y test se ven por fuera de distribución cuando corresponde (y eso es *lo que queremos* para medir generalización).

### Reproducibilidad en inference
En producción, nuevos datos (inference-time) tienen que normalizarse con las mismas stats que el modelo vio en training. Serializar en JSON hace que aggregation y strategy runner usen exactamente los mismos números, sin ambigüedad.

### Drift detection
Al re-entrenar o correr inference sobre datos nuevos, comparamos la distribución actual con `normalization_stats.json`. Si una feature se corrió >3 std vs el training, se loggea warning — señal de que el modelo está operando fuera de su régimen de entrenamiento.

## Clipping a [p01, p99]

Previo al Z-score. Motivo: outliers extremos (ej. volatility spikes en Mar 2020) dominarían la escala y comprimirían toda la señal útil hacia ~0 después del Z-score. Con clipping, el p99 es el máximo post-normalización; outliers reales quedan representados pero no distorsionan.

## Gotchas

- **Regenerar stats al cambiar split dates**: las stats son función del período de training. `compute_split_dates()` usa `date.today()` para el boundary, así que correr el pipeline en un día distinto genera un training set ligeramente distinto y unas stats nuevas. Eso es por diseño (daily retraining), pero hay que tenerlo presente.
- **Consistencia con aggregation**: `consolidate.py` carga `normalization_stats.json` y aplica el mismo clip + Z-score a los datos de inference. Si el archivo no existe o es viejo, inference falla ruidosamente.

## Referencias

- `src/features/normalize.py`
- `src/aggregation/consolidate.py` — aplicación en inference
- [[Feature engineering y selección]]
