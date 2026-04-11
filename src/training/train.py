"""Model training with Optuna hyperparameter optimization.

Supports per-cluster training (Stage 2) where each cluster gets its own
Optuna study that optimizes for precision of the UP class, then trains
a final model with the best hyperparameters.

Usage:
    uv run python -m src.training.train
    uv run python -m src.training.train --cluster Technology_0
    uv run python -m src.training.train --config configs/default.yaml
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import tempfile

import mlflow
import numpy as np
import polars as pl

from src.config import (
    ClusterConfig,
    SplitDates,
    compute_split_dates,
    get_cluster_buy_threshold,
    get_normalized_parquet_path,
    load_config,
    resolve_env_value,
)
from src.keys import MLFLOW_TRACKING_URI


def _load_entry_exit_prices(
    symbols: list[str],
    entry_date,
    horizon: int,
) -> pl.DataFrame:
    """Load entry price at entry_date and exit price horizon trading days later.

    Returns DataFrame with columns [symbol, date_entry, price_entry, date_exit, price_exit].
    """
    import datetime as dt
    from sqlalchemy import text
    from src.db import get_engine, in_params

    engine = get_engine()
    ph, params = in_params("s", symbols)
    buffer_days = int(horizon * 2.5)
    end_buffer = entry_date + dt.timedelta(days=buffer_days)
    params["entry_date"] = entry_date
    params["end_buffer"] = end_buffer
    query = text(f"""
        SELECT date, symbol, close FROM ohlcv_daily
        WHERE symbol IN ({ph})
          AND date >= :entry_date AND date <= :end_buffer
        ORDER BY symbol, date
    """).bindparams(**params)
    with engine.connect() as conn:
        prices = pl.read_database(query, conn)
    if prices.is_empty():
        return pl.DataFrame(schema={
            "symbol": pl.Utf8, "date_entry": pl.Date, "price_entry": pl.Float64,
            "date_exit": pl.Date, "price_exit": pl.Float64,
        })

    rows = []
    for symbol in symbols:
        sym_prices = prices.filter(pl.col("symbol") == symbol).sort("date")
        if sym_prices.is_empty():
            continue
        price_entry = sym_prices["close"][0]
        date_entry = sym_prices["date"][0]
        if len(sym_prices) > horizon:
            price_exit = sym_prices["close"][horizon]
            date_exit = sym_prices["date"][horizon]
        else:
            price_exit = sym_prices["close"][-1]
            date_exit = sym_prices["date"][-1]
        rows.append({
            "symbol": symbol,
            "date_entry": date_entry,
            "price_entry": float(price_entry),
            "date_exit": date_exit,
            "price_exit": float(price_exit),
        })
    return pl.DataFrame(rows)


def _build_trade_summary(trades_df: pl.DataFrame) -> dict:
    """Build a summary dict from enriched trades DataFrame."""
    if trades_df.is_empty() or "trade_return" not in trades_df.columns:
        return {}

    returns = trades_df["trade_return"].to_numpy()
    returns = returns[np.isfinite(returns)]
    if len(returns) == 0:
        return {}

    winners = returns[returns > 0]
    losers = returns[returns < 0]
    flat = returns[returns == 0]

    summary = {
        "total_trades": len(returns),
        "winners": len(winners),
        "losers": len(losers),
        "flat": len(flat),
        "win_rate": len(winners) / len(returns) if len(returns) > 0 else 0.0,
        "avg_return": float(np.mean(returns)),
        "median_return": float(np.median(returns)),
        "std_return": float(np.std(returns)),
        "total_return": float(np.sum(returns)),
        "avg_winner": float(np.mean(winners)) if len(winners) > 0 else 0.0,
        "avg_loser": float(np.mean(losers)) if len(losers) > 0 else 0.0,
        "best_trade": float(np.max(returns)),
        "worst_trade": float(np.min(returns)),
        "profit_factor": float(np.sum(winners) / abs(np.sum(losers))) if len(losers) > 0 and np.sum(losers) != 0 else float("inf") if len(winners) > 0 else 0.0,
        "expectancy": float(
            (len(winners) / len(returns)) * (np.mean(winners) if len(winners) > 0 else 0)
            + (len(losers) / len(returns)) * (np.mean(losers) if len(losers) > 0 else 0)
        ) if len(returns) > 0 else 0.0,
        "max_consecutive_winners": int(_max_consecutive(returns > 0)),
        "max_consecutive_losers": int(_max_consecutive(returns < 0)),
    }
    return summary


def _max_consecutive(mask: np.ndarray) -> int:
    """Count the longest consecutive run of True values."""
    if len(mask) == 0:
        return 0
    max_run = 0
    current = 0
    for v in mask:
        if v:
            current += 1
            max_run = max(max_run, current)
        else:
            current = 0
    return max_run


def _run_split_eval(
    prefix: str,
    preds: list[dict],
    period_start,
    period_end,
    client,
    run_id: str,
    config: dict,
) -> None:
    """Evaluate and log trade metrics for a single split period."""
    from src.evaluation.backtest import load_test_prices, run_portfolio_backtest

    if not preds:
        print(f"    {prefix}: no predictions")
        return

    horizon = config.get("target", {}).get("horizon", 21)
    buy_threshold = config.get("target", {}).get("buy_threshold", 0.025)

    min_prob_up = config.get("training", {}).get("actionable_threshold", 0.70)
    n_actionable = sum(1 for p in preds if p["prob_up"] >= min_prob_up)
    n_total = len(preds)
    mean_prob = sum(p["prob_up"] for p in preds) / n_total if n_total else 0
    print(f"    {prefix}: {n_total} predictions, {n_actionable} actionable (prob_up >= {min_prob_up:.0%}), mean={mean_prob:.2%}")

    client.log_metric(run_id, f"{prefix}_trade_n_actionable", n_actionable)
    client.log_metric(run_id, f"{prefix}_trade_n_total", n_total)

    actionable = [p for p in preds if p["prob_up"] >= min_prob_up]

    if actionable:
        symbols = [p["symbol"] for p in actionable]
        price_data = _load_entry_exit_prices(symbols, period_end, horizon)

        trade_rows = []
        for p in actionable:
            row = {"symbol": p["symbol"], "cluster_id": p["cluster_id"], "prob_up": p["prob_up"]}
            sym_price = price_data.filter(pl.col("symbol") == p["symbol"])
            if not sym_price.is_empty():
                entry = float(sym_price["price_entry"][0])
                exit_ = float(sym_price["price_exit"][0])
                ret = (exit_ - entry) / entry if entry != 0 else 0.0
                row["date_entry"] = sym_price["date_entry"][0]
                row["date_exit"] = sym_price["date_exit"][0]
                row["price_entry"] = round(entry, 2)
                row["price_exit"] = round(exit_, 2)
                row["trade_return"] = round(ret, 6)
                row["result"] = "WIN" if ret >= buy_threshold else ("LOSS" if ret < 0 else "FLAT")
            trade_rows.append(row)

        trades_df = pl.DataFrame(trade_rows)
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            trades_df.write_csv(f.name)
            client.log_artifact(run_id, f.name, artifact_path=f"trade_details/{prefix}_trades")

        summary = _build_trade_summary(trades_df)
        if summary:
            for key, val in summary.items():
                safe_val = float(val) if np.isfinite(float(val)) else 0.0
                client.log_metric(run_id, f"{prefix}_ts_{key}", safe_val)

            summary_rows = [{"metric": k, "value": v} for k, v in summary.items()]
            summary_df = pl.DataFrame(summary_rows)
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
                summary_df.write_csv(f.name)
                client.log_artifact(run_id, f.name, artifact_path=f"trade_details/{prefix}_summary")

    if not actionable:
        print(f"    {prefix}: no actionable predictions, skipping backtest")
        for key in ["total_return", "sharpe", "sortino", "calmar",
                     "max_drawdown", "win_rate", "num_trades", "avg_return"]:
            client.log_metric(run_id, f"{prefix}_trade_{key}", 0.0)
        return

    weight = 1.0 / len(actionable)
    allocations_df = pl.DataFrame([
        {"symbol": p["symbol"], "weight": weight}
        for p in actionable
    ])

    symbols = [p["symbol"] for p in actionable]
    prices_df = load_test_prices(symbols, period_start, period_end)

    if prices_df.is_empty():
        print(f"    {prefix}: no price data for period")
        return

    bt_config = config.get("backtest", {})
    result = run_portfolio_backtest(allocations_df, prices_df, bt_config)

    metrics = {
        f"{prefix}_trade_total_return": result.total_return,
        f"{prefix}_trade_sharpe": result.sharpe_ratio,
        f"{prefix}_trade_sortino": result.sortino_ratio,
        f"{prefix}_trade_calmar": result.calmar_ratio,
        f"{prefix}_trade_max_drawdown": result.max_drawdown,
        f"{prefix}_trade_win_rate": result.win_rate,
        f"{prefix}_trade_num_trades": result.num_trades,
        f"{prefix}_trade_avg_return": result.avg_trade_return,
        f"{prefix}_trade_final_value": result.final_value,
    }
    for key, value in metrics.items():
        val = float(value) if value is not None and np.isfinite(value) else 0.0
        client.log_metric(run_id, key, val)

    print(f"    {prefix}: return={result.total_return:+.2%}, "
          f"sharpe={result.sharpe_ratio:.3f}, trades={result.num_trades}, "
          f"win_rate={result.win_rate:.1%}")


def _evaluate_cluster_trades(
    model,
    config: dict,
    cluster_id: str,
    split_dates: SplitDates,
    run_id: str,
    clusters_parquet: str,
) -> None:
    """Run mini-backtests for a cluster across train/val/test splits."""
    from src.aggregation.consolidate import run_inference_for_period

    features_path = get_normalized_parquet_path(config)
    features_df = pl.read_parquet(features_path).sort(["symbol", "date"])

    all_null_cols = [c for c in features_df.columns if features_df[c].null_count() == len(features_df)]
    if all_null_cols:
        features_df = features_df.drop(all_null_cols)

    clusters_df = pl.read_parquet(clusters_parquet)
    client = mlflow.MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)

    model.eval()
    print(f"  Trade eval across splits:")

    splits = [
        ("train", split_dates.start_date, split_dates.train_end),
        ("val", split_dates.val_start, split_dates.val_end),
        ("test", split_dates.test_start, split_dates.today),
    ]

    for prefix, period_start, period_end in splits:
        preds = run_inference_for_period(
            cluster_id, model, features_df, clusters_df, config,
            split_dates, period_start, period_end,
        )
        _run_split_eval(
            prefix, preds, period_start, period_end,
            client, run_id, config,
        )


def train_single_cluster(config: dict, cluster_id: str, global_params: dict | None = None) -> None:
    """Train a model for a single cluster using Optuna optimization or global params.

    Args:
        config: Full config dict.
        cluster_id: Cluster identifier (e.g. "Technology_0").
        global_params: Optional pre-computed hyperparameters from global optimization.
                      If provided, skips Optuna and trains directly with these params.
    """
    from src.training.optimize import optimize_cluster, train_final_model
    from src.config import compute_split_dates

    if global_params is not None:
        # Use pre-computed global hyperparameters
        print(f"Using global hyperparameters for {cluster_id}")
        split_dates = compute_split_dates(config)
        train_final_model(config, cluster_id, global_params, split_dates)
    else:
        # Run per-cluster optimization
        optimize_cluster(config, cluster_id)


def _train_cluster_worker(args: tuple) -> tuple[str, bool, str]:
    """Train a single cluster in a separate process.

    Each worker gets its own MPS context and DB connection via spawn.

    Returns:
        Tuple of (cluster_id, success, error_message).
    """
    config, cluster_id, global_params = args
    try:
        train_single_cluster(config, cluster_id, global_params)
        return (cluster_id, True, "")
    except Exception as e:
        import traceback
        return (cluster_id, False, traceback.format_exc())
    finally:
        from src.db import dispose_engine
        dispose_engine()


def _sort_clusters_by_run_count(cluster_ids: list[str], config: dict) -> list[str]:
    """Sort clusters by number of existing MLflow runs (fewest first).

    This ensures that when training is interrupted and restarted,
    under-trained clusters get priority.
    """
    try:
        client = mlflow.MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
        prefix = config.get("training", {}).get("cluster_experiment_prefix", "cluster")
        run_counts: dict[str, int] = {}
        for cid in cluster_ids:
            experiment_name = f"{prefix}/{cid}"
            experiment = client.get_experiment_by_name(experiment_name)
            if experiment is None:
                run_counts[cid] = 0
            else:
                runs = client.search_runs(
                    experiment_ids=[experiment.experiment_id],
                    max_results=1,
                    output_format="list",
                )
                # Use search_runs count as approximation; for exact count we'd
                # need to paginate, but this is sufficient for ordering.
                runs_all = client.search_runs(
                    experiment_ids=[experiment.experiment_id],
                    output_format="list",
                )
                run_counts[cid] = len(runs_all)
        sorted_ids = sorted(cluster_ids, key=lambda cid: run_counts.get(cid, 0))
        counts_str = ", ".join(f"{cid}={run_counts.get(cid, 0)}" for cid in sorted_ids)
        print(f"  Cluster training order (by run count): {counts_str}")
        return sorted_ids
    except Exception:
        # If MLflow is unavailable, fall back to alphabetical order
        return cluster_ids


def train_all_clusters(config: dict, global_params: dict | None = None) -> None:
    """Train one model per cluster, optionally in parallel.

    Uses multiprocessing with spawn context for parallel training when
    max_workers > 1. Each worker gets its own MPS GPU context.

    Args:
        config: Full config dict.
        global_params: Optional pre-computed hyperparameters from global optimization.
                      If provided, all clusters use these params.
    """
    cluster_cfg = ClusterConfig.from_dict(config.get("clustering", {}))
    clusters_df = pl.read_parquet(cluster_cfg.output_parquet)
    cluster_ids = clusters_df["cluster_id"].unique().sort().to_list()

    # Order clusters by fewest MLflow runs first so interrupted pipelines
    # don't always retrain the same clusters.
    cluster_ids = _sort_clusters_by_run_count(cluster_ids, config)

    max_workers = int(resolve_env_value(
        config.get("training", {}).get("max_workers", 1), default=1
    ))

    mode = " (using global hyperparameters)" if global_params else " (with per-cluster optimization)"
    parallel_info = f", {max_workers} workers" if max_workers > 1 else ""
    print(f"Found {len(cluster_ids)} clusters to train{mode}{parallel_info}")

    if max_workers <= 1:
        # Sequential fallback
        failed = []
        for i, cluster_id in enumerate(cluster_ids, 1):
            n_symbols = clusters_df.filter(pl.col("cluster_id") == cluster_id).height
            print(f"\n[{i}/{len(cluster_ids)}] Cluster {cluster_id} ({n_symbols} symbols)")
            try:
                train_single_cluster(config, cluster_id, global_params)
            except Exception as e:
                print(f"  ERROR training {cluster_id}: {e}")
                import traceback
                traceback.print_exc()
                failed.append(cluster_id)
    else:
        # Parallel training with spawn (required for MPS safety)
        ctx = mp.get_context("spawn")
        worker_args = [(config, cid, global_params) for cid in cluster_ids]

        print(f"Starting parallel training with {max_workers} workers...")
        failed = []
        with ctx.Pool(processes=max_workers) as pool:
            for cluster_id, success, error_msg in pool.imap_unordered(
                _train_cluster_worker, worker_args
            ):
                if success:
                    print(f"  ✓ {cluster_id} completed successfully")
                else:
                    print(f"  ✗ {cluster_id} FAILED:\n{error_msg}")
                    failed.append(cluster_id)

    print(f"\nTraining complete: {len(cluster_ids) - len(failed)}/{len(cluster_ids)} clusters succeeded.")
    if failed:
        print(f"  Failed clusters: {', '.join(failed)}")


def main() -> None:
    """Entry point for training."""
    parser = argparse.ArgumentParser(description="Train trading model")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    parser.add_argument("--cluster", default=None, help="Train a single cluster ID")
    parser.add_argument("--use-global-params", action="store_true",
                        help="Use pre-computed global hyperparameters from optimize-global")
    args = parser.parse_args()

    config = load_config(args.config)

    # Load global hyperparameters if requested
    global_params = None
    if args.use_global_params:
        from src.training.optimize import load_global_best_params
        global_params = load_global_best_params()
        if global_params is None:
            print("ERROR: No global hyperparameters found. Run 'make optimize-global' first.")
            return
        print(f"Loaded global hyperparameters: {global_params}")

    if args.cluster:
        train_single_cluster(config, args.cluster, global_params)
    else:
        train_all_clusters(config, global_params)


if __name__ == "__main__":
    main()
