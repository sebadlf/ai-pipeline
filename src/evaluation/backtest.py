"""Portfolio-level backtesting with risk management.

Simulates a multi-asset portfolio day by day with:
- Equal-weight position sizing across active positions
- Per-position stop-loss and take-profit
- Portfolio drawdown circuit breaker
- Maximum concurrent positions limit

Usage:
    uv run python -m src.evaluation.backtest
"""

from __future__ import annotations

import datetime as dt
import glob
import os
from dataclasses import dataclass, field

import mlflow
import numpy as np
import polars as pl
import torch

from src.config import compute_split_dates, load_config
from src.keys import MLFLOW_TRACKING_URI
from src.models.base_model import LSTMForecaster
from src.models.dataset import EXCLUDE_COLS


@dataclass
class Position:
    """An open position in a single stock."""

    symbol: str
    entry_price: float
    entry_date: dt.date
    shares: float
    cost_basis: float


@dataclass
class BacktestResult:
    """Container for backtest metrics."""

    total_return: float
    annual_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    avg_trade_return: float
    final_value: float
    circuit_breaker_triggered: bool
    equity_curve: list[float] = field(default_factory=list)


def compute_sharpe(returns: np.ndarray, risk_free_rate: float = 0.0) -> float:
    """Compute annualized Sharpe ratio."""
    excess = returns - risk_free_rate
    if len(excess) < 2 or excess.std() == 0:
        return 0.0
    return float(np.sqrt(252) * excess.mean() / excess.std())


def run_portfolio_backtest(
    signals: pl.DataFrame,
    prices: pl.DataFrame,
    config: dict,
) -> BacktestResult:
    """Run a portfolio-level backtest with risk management.

    Args:
        signals: DataFrame with columns [date, symbol, probability].
        prices: DataFrame with columns [date, symbol, close].
        config: Evaluation config section.
    """
    initial_capital = config["initial_capital"]
    commission_pct = config["commission_pct"]
    confidence = config["confidence_threshold"]
    max_positions = config.get("max_positions", 10)
    stop_loss = config.get("position_stop_loss", 0.08)
    take_profit = config.get("position_take_profit", 0.20)
    max_dd_limit = config.get("max_drawdown_limit", 0.25)
    cooldown_days = config.get("cooldown_days", 10)

    dates = sorted(signals["date"].unique().to_list())

    cash = initial_capital
    positions: dict[str, Position] = {}
    equity_curve = []
    daily_returns_list = []
    trade_returns: list[float] = []
    peak_equity = initial_capital
    circuit_breaker = False
    cooldown_until: dt.date | None = None

    for day in dates:
        # -- Price updates and risk checks on existing positions --
        closed_symbols = []
        for sym, pos in positions.items():
            price_row = prices.filter(
                (pl.col("date") == day) & (pl.col("symbol") == sym)
            )
            if price_row.is_empty():
                continue
            current_price = price_row["close"][0]
            pnl_pct = (current_price - pos.entry_price) / pos.entry_price

            # Stop-loss
            if pnl_pct <= -stop_loss:
                proceeds = pos.shares * current_price * (1 - commission_pct)
                trade_ret = (proceeds - pos.cost_basis) / pos.cost_basis
                trade_returns.append(trade_ret)
                cash += proceeds
                closed_symbols.append(sym)
                continue

            # Take-profit
            if pnl_pct >= take_profit:
                proceeds = pos.shares * current_price * (1 - commission_pct)
                trade_ret = (proceeds - pos.cost_basis) / pos.cost_basis
                trade_returns.append(trade_ret)
                cash += proceeds
                closed_symbols.append(sym)
                continue

        for sym in closed_symbols:
            del positions[sym]

        # -- Compute portfolio equity --
        portfolio_value = cash
        for sym, pos in positions.items():
            price_row = prices.filter(
                (pl.col("date") == day) & (pl.col("symbol") == sym)
            )
            if not price_row.is_empty():
                portfolio_value += pos.shares * price_row["close"][0]

        equity_curve.append(portfolio_value)

        if len(equity_curve) >= 2:
            daily_ret = (equity_curve[-1] - equity_curve[-2]) / equity_curve[-2]
            daily_returns_list.append(daily_ret)

        # -- Drawdown circuit breaker --
        peak_equity = max(peak_equity, portfolio_value)
        current_dd = (portfolio_value - peak_equity) / peak_equity

        if current_dd <= -max_dd_limit and not circuit_breaker:
            circuit_breaker = True
            cooldown_until = day + dt.timedelta(days=cooldown_days)
            # Close all positions
            for sym, pos in list(positions.items()):
                price_row = prices.filter(
                    (pl.col("date") == day) & (pl.col("symbol") == sym)
                )
                if not price_row.is_empty():
                    proceeds = pos.shares * price_row["close"][0] * (1 - commission_pct)
                    trade_ret = (proceeds - pos.cost_basis) / pos.cost_basis
                    trade_returns.append(trade_ret)
                    cash += proceeds
            positions.clear()
            continue

        if cooldown_until and day < cooldown_until:
            continue
        if cooldown_until and day >= cooldown_until:
            circuit_breaker = False
            cooldown_until = None
            peak_equity = portfolio_value

        # -- Generate new signals for today --
        day_signals = signals.filter(pl.col("date") == day)
        buy_candidates = day_signals.filter(
            (pl.col("probability") >= confidence)
            & ~pl.col("symbol").is_in(list(positions.keys()))
        ).sort("probability", descending=True)

        slots_available = max_positions - len(positions)
        if slots_available <= 0 or buy_candidates.is_empty():
            continue

        # Equal-weight allocation from available cash
        n_buys = min(slots_available, len(buy_candidates))
        candidates = buy_candidates.head(n_buys)

        capital_per_position = cash / max(max_positions, len(positions) + n_buys)

        for row in candidates.iter_rows(named=True):
            sym = row["symbol"]
            price_row = prices.filter(
                (pl.col("date") == day) & (pl.col("symbol") == sym)
            )
            if price_row.is_empty():
                continue

            price = price_row["close"][0]
            if price <= 0 or capital_per_position <= 0:
                continue

            cost = capital_per_position
            shares = (cost * (1 - commission_pct)) / price
            positions[sym] = Position(
                symbol=sym,
                entry_price=price,
                entry_date=day,
                shares=shares,
                cost_basis=cost,
            )
            cash -= cost

    # -- Close remaining positions at last available price --
    last_date = dates[-1] if dates else None
    for sym, pos in list(positions.items()):
        price_row = prices.filter(
            (pl.col("date") == last_date) & (pl.col("symbol") == sym)
        )
        if not price_row.is_empty():
            proceeds = pos.shares * price_row["close"][0] * (1 - commission_pct)
            trade_ret = (proceeds - pos.cost_basis) / pos.cost_basis
            trade_returns.append(trade_ret)
            cash += proceeds
    positions.clear()

    final_value = cash
    equity_arr = np.array(equity_curve) if equity_curve else np.array([initial_capital])
    peak = np.maximum.accumulate(equity_arr)
    drawdowns = (equity_arr - peak) / peak
    max_drawdown = float(drawdowns.min())

    daily_returns_arr = np.array(daily_returns_list) if daily_returns_list else np.array([0.0])
    n_days = len(equity_curve)
    years = n_days / 252 if n_days > 0 else 1
    total_return = final_value / initial_capital - 1
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

    winning = sum(1 for r in trade_returns if r > 0)
    win_rate = winning / len(trade_returns) if trade_returns else 0.0
    avg_trade = float(np.mean(trade_returns)) if trade_returns else 0.0

    return BacktestResult(
        total_return=total_return,
        annual_return=annual_return,
        sharpe_ratio=compute_sharpe(daily_returns_arr),
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        num_trades=len(trade_returns),
        avg_trade_return=avg_trade,
        final_value=final_value,
        circuit_breaker_triggered=circuit_breaker or (cooldown_until is not None),
        equity_curve=equity_curve,
    )


def main() -> None:
    """Run portfolio backtest on test set."""
    config = load_config()
    eval_cfg = config["evaluation"]
    model_cfg = config["model"]

    split_dates = compute_split_dates(config)
    print("Temporal splits:")
    print(split_dates.summary())

    seq_len = model_cfg["sequence_length"]
    test_cutoff = split_dates.test_start
    train_end = split_dates.train_end

    # Load features
    raw_df = pl.read_parquet("data/features.parquet").sort(["symbol", "date"])

    # Drop all-null columns
    all_null_cols = [c for c in raw_df.columns if raw_df[c].null_count() == len(raw_df)]
    if all_null_cols:
        raw_df = raw_df.drop(all_null_cols)

    feature_cols = [c for c in raw_df.columns if c not in EXCLUDE_COLS]

    # Compute normalization stats from training period only
    train_df = raw_df.filter(pl.col("date") < train_end)
    train_df = train_df.drop_nulls(subset=feature_cols)
    train_matrix = train_df.select(feature_cols).to_numpy()
    train_mean = train_matrix.mean(axis=0)
    train_std = train_matrix.std(axis=0)
    train_std[train_std == 0] = 1.0

    # Load model
    checkpoints = sorted(
        glob.glob("**/best-*.ckpt", recursive=True),
        key=lambda p: os.path.getmtime(p),
    )
    checkpoints = [c for c in checkpoints if not c.startswith("mlruns/")]
    if not checkpoints:
        print("No checkpoint found. Run training first.")
        return

    ckpt_path = checkpoints[-1]
    print(f"Loading model from {ckpt_path}")
    model = LSTMForecaster.load_from_checkpoint(ckpt_path, map_location="cpu")
    model.eval()

    # Generate per-symbol, per-day signals for the test period
    symbols = raw_df["symbol"].unique().sort().to_list()
    all_signals = []
    all_prices = []

    for symbol in symbols:
        sym_df = raw_df.filter(pl.col("symbol") == symbol).sort("date")
        sym_df = sym_df.drop_nulls(subset=feature_cols)
        test_df = sym_df.filter(pl.col("date") >= test_cutoff)

        if len(test_df) < seq_len:
            continue

        # We need seq_len rows before each test day for context
        # Find the index where test period starts in the full symbol data
        full_features = sym_df.select(feature_cols).to_numpy()
        full_dates = sym_df["date"].to_list()

        test_start_idx = None
        for i, d in enumerate(full_dates):
            if d >= test_cutoff:
                test_start_idx = i
                break

        if test_start_idx is None or test_start_idx < seq_len:
            continue

        # Normalize all features
        norm_features = (full_features - train_mean) / train_std

        # Generate predictions for each test day
        for i in range(test_start_idx, len(full_dates)):
            window = norm_features[i - seq_len : i]
            x = torch.tensor(window, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                prob = model.predict_proba(x).item()

            all_signals.append({
                "date": full_dates[i],
                "symbol": symbol,
                "probability": prob,
            })

        # Collect close prices for test period
        test_prices = sym_df.filter(pl.col("date") >= test_cutoff).select(["date", "symbol"])
        # Need close prices - reload from OHLCV
        from src.db import get_engine
        engine = get_engine()
        price_query = f"""
            SELECT date, symbol, close FROM ohlcv_daily
            WHERE symbol = '{symbol}' AND date >= '{test_cutoff}'
            ORDER BY date
        """
        price_df = pl.read_database(price_query, engine)
        all_prices.append(price_df)

    signals_df = pl.DataFrame(all_signals)
    prices_df = pl.concat(all_prices)

    print(f"Generated {len(signals_df):,} signals for {len(symbols)} symbols")
    print(f"Test period: {test_cutoff} to {signals_df['date'].max()}")

    prob_above = signals_df.filter(pl.col("probability") >= eval_cfg["confidence_threshold"]).height
    print(f"Signals above threshold: {prob_above:,} / {len(signals_df):,}")

    # Run portfolio backtest
    result = run_portfolio_backtest(signals_df, prices_df, eval_cfg)

    # Print results
    print("\n=== Portfolio Backtest Results ===")
    print(f"Total Return:     {result.total_return:+.2%}")
    print(f"Annual Return:    {result.annual_return:+.2%}")
    print(f"Sharpe Ratio:     {result.sharpe_ratio:.3f}")
    print(f"Max Drawdown:     {result.max_drawdown:.2%}")
    print(f"Win Rate:         {result.win_rate:.2%}")
    print(f"Num Trades:       {result.num_trades}")
    print(f"Avg Trade Return: {result.avg_trade_return:+.2%}")
    print(f"Final Value:      ${result.final_value:,.2f}")
    if result.circuit_breaker_triggered:
        print(f"  ⚠ Circuit breaker was triggered (drawdown limit: {eval_cfg.get('max_drawdown_limit', 0.25):.0%})")

    print(f"\n--- Risk Parameters ---")
    print(f"Max Positions:    {eval_cfg.get('max_positions', 10)}")
    print(f"Stop Loss:        {eval_cfg.get('position_stop_loss', 0.08):.0%}")
    print(f"Take Profit:      {eval_cfg.get('position_take_profit', 0.20):.0%}")
    print(f"DD Limit:         {eval_cfg.get('max_drawdown_limit', 0.25):.0%}")

    # Log to MLflow
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("trading-forecaster")

    with mlflow.start_run(run_name="backtest"):
        mlflow.log_metric("total_return", result.total_return)
        mlflow.log_metric("annual_return", result.annual_return)
        mlflow.log_metric("sharpe_ratio", result.sharpe_ratio)
        mlflow.log_metric("max_drawdown", result.max_drawdown)
        mlflow.log_metric("win_rate", result.win_rate)
        mlflow.log_metric("num_trades", result.num_trades)
        mlflow.log_metric("avg_trade_return", result.avg_trade_return)
        mlflow.log_metric("final_value", result.final_value)
        mlflow.log_params({
            "confidence_threshold": eval_cfg["confidence_threshold"],
            "max_positions": eval_cfg.get("max_positions", 10),
            "stop_loss": eval_cfg.get("position_stop_loss", 0.08),
            "take_profit": eval_cfg.get("position_take_profit", 0.20),
            "max_drawdown_limit": eval_cfg.get("max_drawdown_limit", 0.25),
        })
        print("\nMetrics logged to MLflow.")


if __name__ == "__main__":
    main()
