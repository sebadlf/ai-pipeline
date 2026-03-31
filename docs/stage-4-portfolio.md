# Stage 4: Portfolio Optimization

**Files**: `src/portfolio/optimizer.py`, `src/portfolio/metrics.py`
**Makefile target**: `make portfolio`
**Command**: `uv run python -m src.portfolio.optimizer`

## Purpose

Given unified predictions (BUY/SELL/HOLD with confidence scores for every stock), construct three risk-profiled portfolios by optimizing position weights. The optimization maximizes a combination of risk-adjusted return metrics (Sharpe, Sortino, Calmar, Omega, Information ratio) while enforcing diversification constraints.

## Three Risk Profiles

The pipeline constructs three portfolios simultaneously, each targeting a different risk-return tradeoff:

### Aggressive

| Parameter | Value | Rationale |
|---|---|---|
| Primary metric | Sortino | Focuses on upside, only penalizes downside volatility |
| Complementary metric | Omega | Captures full return distribution shape |
| Max positions | 25 | Higher diversification allowance |
| Max sector weight | 30% | Moderate sector concentration |
| Min confidence | 50% | Lower threshold, more positions |
| Allow short | Yes | Can take SELL signal positions |

### Moderate

| Parameter | Value | Rationale |
|---|---|---|
| Primary metric | Sharpe | Classic risk-adjusted return |
| Complementary metric | Calmar | Considers drawdown risk |
| Max positions | 20 | Moderate diversification |
| Max sector weight | 25% | Balanced sector exposure |
| Min confidence | 55% | Medium confidence threshold |
| Allow short | No | Long-only |

### Conservative

| Parameter | Value | Rationale |
|---|---|---|
| Primary metric | Calmar | Minimizes drawdown-relative return |
| Complementary metric | Sortino | Downside protection |
| Max positions | 15 | Concentrated, high-conviction |
| Max sector weight | 20% | Strict sector limits |
| Min confidence | 60% | Only high-confidence signals |
| Allow short | No | Long-only |

## Optimization Algorithm

### Objective Function

The optimizer uses scipy's SLSQP (Sequential Least Squares Quadratic Programming) to minimize the negative of a blended metric:

```
objective = -(0.8 × primary_metric + 0.2 × complementary_metric)
```

The 80/20 weighting gives dominance to the primary metric while allowing the complementary metric to break ties and provide secondary guidance.

### Returns Estimation

Portfolio returns for optimization are estimated using **validation-period** historical data (not training or test). This prevents the optimizer from fitting to the same data the model was trained on.

```
Validation period: val_start → val_end (1 year)
```

Daily returns are loaded from `ohlcv_daily` for candidate symbols, pivoted into a `(n_days, n_symbols)` matrix, and portfolio returns are computed as `returns_matrix @ weights`.

### Direction Handling

For profiles that allow shorting (`allow_short: true`):
- BUY signals use positive returns (standard long)
- SELL signals negate returns in the matrix (short = profit from price decline)

### Constraints

| Constraint | Type | Default | Description |
|---|---|---|---|
| Weights sum to 1 | Equality | Always | Fully invested portfolio |
| Max single position | Bound | 10% | Diversification per stock |
| Min single position | Bound | 1% | Avoid dust positions |
| Max sector weight | Inequality | Profile-specific | Sector concentration limit |

Sector constraints use the `stock_sectors` table to map each symbol to its GICS sector. For each sector present in the portfolio candidates, an inequality constraint ensures the sum of weights for that sector does not exceed `max_sector_weight`.

### Candidate Selection

Before optimization, candidates are filtered:

1. **Confidence filter**: Only symbols with `confidence >= min_confidence` are included
2. **Signal filter**: Long-only profiles keep only BUY predictions; short-enabled profiles keep BUY and SELL
3. **Position limit**: Top N by confidence, where N = `max_positions`

If optimization fails (SLSQP doesn't converge), the optimizer falls back to equal-weight allocation across candidates.

## Portfolio Metrics

`src/portfolio/metrics.py` provides pure numpy functions for computing risk-adjusted return metrics. All ratios are annualized assuming 252 trading days per year.

### Sharpe Ratio

```
Sharpe = √252 × mean(daily_excess_returns) / std(daily_excess_returns)
```

Measures return per unit of total volatility. Higher is better. Risk-free rate defaults to 0.

### Sortino Ratio

```
Sortino = √252 × mean(excess_returns) / std(min(excess_returns, 0))
```

Like Sharpe but only penalizes downside volatility. Better for asymmetric return distributions common in trading strategies.

### Omega Ratio

```
Omega = sum(max(returns - threshold, 0)) / sum(max(threshold - returns, 0))
```

Ratio of cumulative gains above threshold to cumulative losses below. Captures the full return distribution without assuming normality.

### Calmar Ratio

```
Calmar = annualized_return / max_drawdown
```

Return relative to worst peak-to-trough decline. Critical for evaluating tail risk.

### Information Ratio

```
Information = √252 × mean(portfolio_returns - benchmark_returns) / std(portfolio_returns - benchmark_returns)
```

Measures risk-adjusted outperformance versus a benchmark (SPY). Tracking error in the denominator.

### Max Drawdown

```
max_drawdown = max((peak - trough) / peak) over all time
```

Largest peak-to-trough decline as a fraction.

## Output

### `data/portfolios.parquet`

| Column | Type | Description |
|---|---|---|
| profile | str | "aggressive", "moderate", or "conservative" |
| symbol | str | Stock ticker |
| weight | float | Position weight (0.01 to 0.10) |
| signal | str | "BUY" or "SELL" |
| cluster_id | str | Which cluster the symbol belongs to |

### `portfolio_allocations` table (PostgreSQL)

Same columns plus `run_date`, upserted on `(run_date, profile, symbol)`.

## MLflow Logging

- **Experiment**: `portfolio-optimization`
- **Run name**: `portfolio-design`
- **Metrics**: `{profile}_n_positions`, `{profile}_max_weight` for each profile
- **Artifact**: `data/portfolios.parquet`

## CLI Arguments

| Flag | Default | Description |
|---|---|---|
| `--config` | `configs/default.yaml` | Config file path |
