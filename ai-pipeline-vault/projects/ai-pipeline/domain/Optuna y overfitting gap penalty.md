---
tags: [domain, optuna, ml, training]
---

# Optuna y overfitting gap penalty

## El problema

Optuna optimiza agresivamente. Con ~12 hyperparams tunables y precision-at-threshold como objetivo (métrica ruidosa), es trivial que el optimizador encuentre configs que memorizan el training set y exhiben precision alta en el fold de validación por pura varianza.

Signal de esto: train accuracy 0.85+, val accuracy 0.55 (apenas mejor que random). Overfitting duro.

## La mitigación: penalty explícito

En cada trial, tras los 3 CV folds, computamos `avg_train_acc - avg_val_acc`. Si ese gap supera `max_overfit_gap` (0.30), el objective score se escala a la baja por factor `max_gap / actual_gap`.

```python
if gap > max_overfit_gap:
    score = score * (max_overfit_gap / gap)
```

Efecto: un trial con train=0.90, val=0.55 (gap=0.35) pierde ~15% del score. Un trial con train=0.75, val=0.60 (gap=0.15, pasa) queda intacto. Optuna converge a configs con generalización aceptable.

## Otros guardrails

### Recall floor
Si el modelo predice "UP" en <15% de los samples, la métrica de precision se vuelve inestable (denominator chico). Aplicamos penalty cuadrática si `recall < 0.15`.

### Convergence-based early stopping
Si el best score no mejora en 3 (dev) / 5 (prod) trials consecutivos, el study termina. Evita correr 50 trials cuando ya encontramos el plateau.

### Time-series CV con purge gaps
3 folds de expanding window, con purge de 21 días (=horizon) entre train y val. Previene leakage por autocorrelación temporal.

### Capacity limits
Máx `hidden_size=128` y `num_layers=3`. Limita el overfit estructural: un modelo con 256 unidades y 5 capas tiene demasiada capacidad para el volumen de data por cluster.

### Noise + feature masking
Data augmentation durante training: Gaussian noise (0.01-0.08 std tunable) + feature masking (10% random drop). Reduce memorización.

## Persistencia de estudios

Los estudios de Optuna se guardan en la misma Postgres del pipeline (tabla gestionada por Optuna). Esto permite:
- **Warm-starting**: re-correr train-clusters retoma desde donde quedó
- **Historia**: podemos inspeccionar qué configs se probaron en el pasado
- **Filtrado por recencia**: `max_history_days` (dev:7d, prod:60d) descarta trials viejos para que el optimizer no se guíe por hyperparams que ya no son relevantes (ej. porque cambiaron las features)

## Top-N dedup

Al final del study, Optuna devuelve los N mejores trials. Pero Optuna no sabe nada de "near-duplicates": dos trials con LR 1e-3 y 1.1e-3 son esencialmente el mismo modelo. Aplicamos dedup sobre 10 key params y tomamos **top-3 únicos** para el ensemble. Ver [[ADR-003 — Ensemble top-3 con weighted average]].

## Referencias

- `src/training/optimize.py`
- `docs/stage-2-training.md`
- CLAUDE.md — "Optuna optimization"
- [[ADR-003 — Ensemble top-3 con weighted average]]
