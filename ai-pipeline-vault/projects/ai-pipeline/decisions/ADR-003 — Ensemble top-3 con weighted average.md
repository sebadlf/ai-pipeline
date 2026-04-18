---
date: 2026-04-18
status: accepted
tags: [adr, ml, optuna, ensemble]
---

# ADR-003: Ensemble top-3 con weighted average por cluster

## Contexto

Optuna tiende a overfittear cuando el espacio de búsqueda es grande y el dataset tiene señal débil (como pasa con precision-at-threshold en trading). Elegir el *único* "best trial" introduce dos riesgos:

1. **Lucky trial**: una config gana por ruido en los CV folds y no generaliza.
2. **Brittleness**: si el mejor modelo se rompe (cambio de features, cambio de régimen), no hay backup suave.

Además, durante el desarrollo notamos que trials con hyperparams muy distintos alcanzaban precisiones similares en validación — señal de que el óptimo local es plano y varios puntos son igualmente válidos.

## Decisión

Por cada cluster, entrenar los **top-3 trials deduplicados** (10 key params chequeados para near-duplicates) como modelos full-training. En inferencia, ensemble por **promedio ponderado** de `prob_up`, con pesos proporcionales a `val_precision_up` de cada miembro.

Adicionalmente: el mejor miembro del ensemble se tagea como "champion" usando un score ajustado por generalización: `base_score * (1 + test_prec/val_prec) / 2`. Prefiere modelos donde test precision se parece a val precision (menos overfitting al fold de validación).

## Alternativas consideradas

### Opción A: Single best trial
- Pro: simple, barato
- Contra: frágil, lucky trials, sin redundancia

### Opción B: Ensemble top-3 weighted (esta decisión)
- Pro: reduce varianza, capta diversidad en el espacio de hyperparams, el peso por `val_precision_up` premia calidad
- Contra: 3x costo de training e inferencia por cluster

### Opción C: Stacking con meta-learner
- Pro: potencialmente mejor generalización
- Contra: complejidad, riesgo de leakage en el meta-learner, más hyperparams que tunear

### Opción D: Bayesian model averaging
- Pro: fundamentación teórica
- Contra: requiere priors y posteriors bien definidos que no tenemos

## Consecuencias

- Cada cluster genera 3 MLflow runs (una por miembro del ensemble), dentro del experimento `cluster/{cluster_id}`
- Storage de modelos en MLflow se triplica por cluster — aceptamos el costo
- Aggregation (`src/aggregation/consolidate.py`) carga los 3 checkpoints por cluster y hace weighted average
- Champion selection vs ensemble: el "champion" se registra en el Model Registry para poder ser consultado individual cuando hace falta (ej. signals rápidos en un cluster), pero la predicción primaria siempre es el ensemble
- Dedup logic de 10 key params previene que los 3 trials ganadores sean esencialmente el mismo modelo con seed distinto

## Referencias

- `src/training/optimize.py` — dedup logic y top-N selection
- `src/training/train.py` — ensemble training
- `src/aggregation/consolidate.py` — weighted average por `val_precision_up`
- `src/evaluation/promote.py` — champion selection
- CLAUDE.md — "Optuna optimization / Ensemble"
