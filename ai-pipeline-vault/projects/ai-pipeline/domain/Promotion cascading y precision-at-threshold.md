---
tags: [domain, promotion, mlflow, ml]
---

# Promotion cascading y precision-at-threshold

## Qué hace

Stage 3 selecciona el mejor modelo por cluster y lo registra como alias `"champion"` en el MLflow Model Registry. Ese alias es lo que `aggregation.consolidate` y `strategy.runner` consumen.

## El problema que resuelve

"Mejor" es ambiguo. Comparar por val_precision no sirve: un modelo con val_prec=0.80 y test_prec=0.55 perdió el juego, no ganó. Necesitamos filtros que capturen **estabilidad** y **generalización**, no sólo el peak en un fold.

## Evaluación: precision-at-threshold walk-forward

Para cada modelo candidato, evaluamos precision en un barrido de thresholds `[0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]`. El primary threshold por defecto es **0.65** (trade-off razonable precision/recall para trading).

Luego hacemos walk-forward: ventana de 63 días (3x horizon), paso de 21 días (=horizon). Por cada ventana computamos precision y recall.

Métricas agregadas:
- **stability_score**: `mean_precision - 1.0 * std_precision` (premia consistencia, castiga varianza)
- **generalization penalty**: si `val_prec - test_prec > 0.20`, penalty adicional al score

## Filtros

Un modelo tiene que pasar todos para ser Tier 1:
- `std_ratio < 0.25` — la std de precision no puede ser más de 25% de la mean
- `recall >= 0.10` — mínimo 10% de UP signals detectados
- `min 3 UP signals por ventana` — sino la métrica es ruido
- `val-test gap <= 0.20` — generalization guardrail

## Adaptive threshold

A veces el modelo está muy bien calibrado pero predice 0 muestras arriba del primary_threshold. En lugar de descartarlo, bajamos el threshold hacia abajo (mínimo 0.50) buscando el más alto que cumpla:
- `signal_rate >= 5%`
- `precision >= 50%`

Si aún así no encuentra nada → graduated fallback (ver abajo).

## Graduated fallback

Ordena candidatos en tiers:
1. **Tier 1**: pasó todos los filtros
2. **Tier 2**: falló solo `signals` o `coverage`
3. **Tier 3**: falló un filtro cualquiera
4. **Tier 4**: ninguno anterior, toma el más reciente con checkpoint válido

Siempre sale algún champion, incluso en clusters problemáticos. Mejor un modelo mediocre que ningún modelo.

## Tiebreaking por FP severity

Cuando dos candidatos están dentro de 0.01 de score, se desempata por **FP severity**: qué tan malos son los false positives en términos de retorno. Un modelo que marca UP y el stock cae 10% es peor que uno que marca UP y el stock se queda plano, aunque ambos sean "FP" en precision pura.

## Calibración por temperature

Antes de la evaluación de promotion, los modelos se calibran con temperature scaling (Guo et al. 2017):
- Bounds `[0.5, 2.5]` — previene T>>1 que colapsa todas las probas a ~0.50
- Signal preservation: castiga calibraciones que dejan <3% de predictions arriba del primary_threshold
- Safety check: si post-cal tiene <1% de signals arriba de 0.60, fallback a T=1.0

## Legacy fallback

Si la config no tiene sección `promotion.evaluation` en el YAML, el sistema cae a comparación simple por métricas (val_precision). Util para setups antiguos o debugging.

## Referencias

- `src/evaluation/promote.py` — registra champion en MLflow Registry
- `src/evaluation/precision_eval.py` — walk-forward evaluation
- `docs/signals-and-promotion.md`
- CLAUDE.md — "Model promotion (cascading elimination)"
