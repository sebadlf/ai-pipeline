---
tags: [domain, backtesting, regime, portfolio]
---

# Regime detection y backtesting

## Regime detection

El mercado no es uniforme: un backtest que promedia bull/bear/sideways esconde más de lo que muestra. Stage 6 segmenta el histórico en regímenes y reporta métricas por régimen.

**Criterios de clasificación** (`src/evaluation/regime.py`):
- **Bull**: SPY arriba de SMA200 y trailing annualized return > umbral positivo
- **Bear**: SPY debajo de SMA200 y trailing return < umbral negativo
- **Sideways**: resto

Son heurísticas deliberadamente simples. Alternativas más sofisticadas (HMM, regime-switching models) existen pero agregan varianza al análisis sin claridad mucho mayor para este uso.

## Backtest

`src/evaluation/backtest.py` simula cada una de las 3 portfolios (aggressive/moderate/conservative) contra cada régimen con:

### Risk management
- Stop-loss por posición: -8%
- Take-profit por posición: +50%
- Portfolio circuit breaker: drawdown -25% → freeze 2 días de cooldown, no abrir posiciones nuevas
- Rebalancing cada 21 días: cierra todas las posiciones y reabre a los target weights con la equity actual

### Sector/position limits
- Max single position weight: 10%, min: 1%
- Sector weight cap: 20-30% según profile (conservative más estricto)

### Costos
- Comisión: 0.1%
- Slippage: 5 bps
- Capital inicial: $100,000

## Métricas reportadas

Por cada (profile, regime) — ver `src/portfolio/metrics.py`:
- Sharpe, Sortino, Calmar, Omega, Information ratio
- Max drawdown, total return, volatility
- Win rate, avg gain, avg loss

Output: markdown reports en `data/backtest_reports/`.

## Cómo leer los reports

No buscar "el perfil ganador": cada regime tiene un perfil óptimo. Lo útil es:
- **Aggressive en bull**: debería brillar
- **Conservative en bear**: debería sobrevivir con DD controlado
- **Moderate**: curva más plana, robusto cross-regime

Si **aggressive** tiene mal Sharpe en bull, o **conservative** tiene DD grande en bear, hay algo que investigar — el modelo no está agregando valor donde se supone.

## Rebalancing gotcha

El rebalancing cada 21 días es simple pero caro: cerrar y reabrir todas las posiciones genera comisiones y slippage. Alternativas (rebalancing con threshold, continuous weight updates) están en el backlog pero requieren cambiar el motor de backtest.

## Referencias

- `src/evaluation/regime.py` — classification logic
- `src/evaluation/backtest.py` — simulation engine
- `src/portfolio/metrics.py` — todas las métricas
- `docs/stage-5-backtest.md`
- CLAUDE.md — "Stage 6: Regime-Aware Backtesting" + "Risk management (backtest)"
