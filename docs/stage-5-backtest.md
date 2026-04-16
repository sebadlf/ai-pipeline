# Stage 5: Backtesting and Regime Detection

**Files**: `src/evaluation/backtest.py`, `src/evaluation/regime.py`
**Makefile target**: `make backtest`
**Command**: `uv run python -m src.evaluation.backtest`

## Purpose

Evaluate portfolio performance through realistic day-by-day simulation on the **test period** (last 2 years). Backtests are segmented by market regime (bull, bear, sideways) to understand how each portfolio profile performs under different market conditions. The simulation includes transaction costs, position-level stop-loss/take-profit, and a portfolio-level drawdown circuit breaker.

## Market Regime Detection

**File**: `src/evaluation/regime.py`

Classifies each trading day as **bull**, **bear**, or **sideways** using SPY as the benchmark.

### Algorithm

```
For each trading day:
  1. Compute trailing annualized return over lookback_days (126 = 6 months)
  2. Compute SMA crossover: SMA_50 vs SMA_200

  if annualized_return > +10% AND SMA_50 > SMA_200 → bull
  if annualized_return < -10% AND SMA_50 < SMA_200 → bear
  otherwise → sideways
```

Both conditions must be met (return threshold AND SMA alignment) to classify a day as bull or bear. This prevents false signals from temporary return spikes without trend confirmation, or SMA crossovers without return evidence.

### Configuration

```yaml
regime:
  benchmark: SPY
  lookback_days: 126      # 6 months trailing window
  bull_threshold: 0.10    # +10% annualized
  bear_threshold: -0.10   # -10% annualized
  sma_short: 50           # fast SMA
  sma_long: 200           # slow SMA
```

### Implementation Detail

The price history is loaded with a 400-day buffer before the requested start date to ensure the 200-day SMA is valid from the first day of the detection period.

## Backtest Architecture

### Per-Combination Simulation

Backtests are run for every (profile, regime) pair:

```
3 profiles × 3 regimes = 9 backtests per pipeline run
```

For each combination:
1. Filter portfolio allocations to the profile (e.g., "aggressive")
2. Filter the test period price data to only days matching the regime (e.g., "bull")
3. Run `run_portfolio_backtest()` on the filtered data

This reveals whether a portfolio that works well in bull markets collapses in bear markets, and vice versa.

### Day-by-Day Simulation

`run_portfolio_backtest()` iterates through each trading day in chronological order:

```
Day 1:
  Open long positions according to portfolio weights
  cash -= allocation × initial_capital per position
  shares = (capital_for_position × (1 - commission - slippage)) / price

Each subsequent day:
  For each open position:
    Compute PnL: (current_price - entry_price) / entry_price
    If PnL <= -stop_loss → close position
    If PnL >= +take_profit → close position

  Every 21 trading days (rebalance_frequency_days):
    Close ALL positions at market price
    Re-open positions at target weights using current equity
    (Ensures portfolio stays aligned with target allocation)

  Compute portfolio equity = cash + sum(shares × current_price)
  Compute daily return and drawdown

  If drawdown >= max_drawdown_limit:
    Trigger circuit breaker → close ALL positions
    Enter cooldown period

Last day:
  Close remaining open positions at market price
```

### Position Modeling

```python
@dataclass
class Position:
    symbol: str
    entry_price: float
    entry_date: dt.date
    shares: float
    cost_basis: float
```

All positions are **long-only**.

**Position value**: `shares × current_price`
**Closing**: `proceeds = shares × current_price × (1 - commission)`

## Risk Management

### Position-Level Controls

| Parameter | Default | Description |
|---|---|---|
| `position_stop_loss` | 8% | Close position if loss exceeds 8% of entry price |
| `position_take_profit` | 50% | Close position if gain exceeds 50% of entry price |

These are evaluated daily for each open position. Stop-loss prevents catastrophic single-stock losses. Take-profit locks in gains.

### Portfolio-Level Circuit Breaker

| Parameter | Default | Description |
|---|---|---|
| `max_drawdown_limit` | 25% | Trigger if portfolio drawdown exceeds 25% from peak |
| `cooldown_days` | 2 | Stay fully in cash for 2 trading days after trigger |

When the circuit breaker triggers:
1. **All positions** are closed immediately at market prices
2. Portfolio goes to 100% cash
3. The cooldown period begins (2 days by default)
4. After cooldown, the peak equity is reset to current equity to avoid immediate re-triggering
5. Positions are NOT automatically re-opened (simulation continues in cash)

The circuit breaker is the primary mechanism for keeping max drawdown below 30%, which was a hard requirement for this project.

## Output

### Backtest Results

```python
@dataclass
class BacktestResult:
    total_return: float        # cumulative return over test period
    annual_return: float       # annualized return
    sharpe_ratio: float        # risk-adjusted return
    sortino_ratio: float       # downside-risk-adjusted return
    calmar_ratio: float        # return / max drawdown
    omega_ratio: float         # gains/losses ratio
    info_ratio: float          # excess return vs benchmark
    max_drawdown: float        # worst peak-to-trough
    win_rate: float            # fraction of profitable trades
    num_trades: int            # total closed positions
    avg_trade_return: float    # mean return per trade
    final_value: float         # ending portfolio value
    circuit_breaker_triggered: bool
    equity_curve: list[float]  # daily portfolio values
    profile: str               # "aggressive" / "moderate" / "conservative"
    regime: str                # "bull" / "bear" / "sideways"
```

### `backtest_results` table (PostgreSQL)

| Column | Type | Description |
|---|---|---|
| run_date | DATE | Pipeline run date |
| profile | VARCHAR | Portfolio profile |
| regime | VARCHAR | Market regime |
| total_return | FLOAT | Cumulative return |
| annual_return | FLOAT | Annualized return |
| sharpe_ratio | FLOAT | Sharpe |
| sortino_ratio | FLOAT | Sortino |
| calmar_ratio | FLOAT | Calmar |
| omega_ratio | FLOAT | Omega |
| info_ratio | FLOAT | Information ratio |
| max_drawdown | FLOAT | Max drawdown |
| win_rate | FLOAT | Win rate |
| num_trades | INT | Number of trades |

Upserted on `(run_date, profile, regime)`.

### Markdown Reports

Generated at `data/backtest_reports/backtest_{run_date}.md` as a readable table:

```markdown
# Backtest Report — 2026-03-28

| Profile | Regime | Return | Sharpe | Sortino | Calmar | Omega | Info | Max DD | Win Rate | Trades |
|---------|--------|--------|--------|---------|--------|-------|------|--------|----------|--------|
| aggressive | bull | +12.3% | 1.234 | 1.567 | 0.987 | 1.234 | 0.456 | 8.5% | 65.0% | 30 |
```

## MLflow Logging

- **Experiment**: `backtesting`
- **Run name**: `regime-backtest`
- **Metrics**: `{profile}_{regime}_return`, `{profile}_{regime}_sharpe`, `{profile}_{regime}_sortino`, `{profile}_{regime}_calmar`, `{profile}_{regime}_omega`, `{profile}_{regime}_info`, `{profile}_{regime}_max_dd` for all 9 combinations
- **Artifacts**: All markdown reports from `data/backtest_reports/*.md`

## Configuration

```yaml
backtest:
  initial_capital: 100000    # starting portfolio value in USD
  commission_pct: 0.001      # 0.1% per trade (buy and sell)
  slippage_bps: 5            # 5 basis points slippage on entry/exit
  risk:
    position_stop_loss: 0.08     # 8% per-position stop-loss
    position_take_profit: 0.50   # 50% per-position take-profit
    max_drawdown_limit: 0.25     # 25% portfolio drawdown circuit breaker
    cooldown_days: 2             # days in cash after circuit breaker
  output_dir: data/backtest_reports
```

Note: Periodic rebalancing frequency is controlled by `portfolio.constraints.rebalance_frequency_days` (default: 21 trading days, ~1 month).

## CLI Arguments

| Flag | Default | Description |
|---|---|---|
| `--config` | `configs/default.yaml` | Config file path |
