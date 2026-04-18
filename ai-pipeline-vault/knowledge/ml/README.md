---
tags: [knowledge, ml, trading]
---

# ML & Trading — Base de conocimiento

Conocimiento transversal de ML financiero y patrones aplicables a múltiples proyectos de trading.

## Hyperparameter optimization

- [[Optuna — Overfitting gap penalty]] — castigar configs que memorizan training set
- [[Optuna — Ensemble top-3]] — evitar overtuning con promedio ponderado
- [[Time-series CV con purge gaps]] — evitar leakage temporal en folds

## Feature engineering

- [[Feature selection pipelines]] — null/variance/correlation/MI filters
- [[Normalización con stats persistentes]] — por qué guardar mean/std/p01/p99 del training set
- [[Adj close y consistencia de indicadores]] — usar ajustado en indicadores para matchear con target

## Model architecture

- [[LSTM para forecasting financiero]] — residual connection en last timestep, input dropout
- [[FocalLoss y class imbalance]] — cuándo usar sobre CrossEntropy ponderada
- [[Temperature calibration]] — Guo et al. 2017, bounds y signal preservation

## Evaluation & promotion

- [[Precision-at-threshold walk-forward]] — evaluar estabilidad de precision
- [[Cascading promotion con graduated fallback]] — tiers de elegibilidad
- [[Champion selection con generalization penalty]] — penalizar val→test gap

## Portfolio & backtesting

- [[Métricas de portfolio — Sharpe/Sortino/Calmar/Omega]] — cuándo usar cada una
- [[Multi-profile optimization]] — agressive/moderate/conservative
- [[Regime detection — SPY SMA + trailing returns]]
- [[Risk management en backtest]] — stop-loss, circuit breaker, rebalancing

## Por explorar

- [ ] Meta-learning / hyperparameter transfer learning entre clusters
- [ ] Purged K-Fold de Lopez de Prado vs expanding window
- [ ] Alternativas a KMeans (HDBSCAN, Spectral)
