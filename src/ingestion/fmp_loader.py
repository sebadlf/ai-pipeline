"""FMP API data ingestion into PostgreSQL.

Usage:
    uv run python -m src.ingestion.fmp_loader
    uv run python -m src.ingestion.fmp_loader --symbols AAPL MSFT --start 2023-01-01
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys

import httpx
from sqlalchemy import text

from src.config import load_config
from src.db import get_engine, init_db, ohlcv_daily
from src.keys import FMP_API_KEY

FMP_BASE_URL = "https://financialmodelingprep.com/stable"


def fetch_ohlcv(
    symbol: str,
    start_date: str,
    end_date: str | None = None,
    api_key: str | None = None,
) -> list[dict]:
    """Fetch daily OHLCV data from FMP API.

    Args:
        symbol: Ticker symbol (e.g. AAPL).
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date. Defaults to today.
        api_key: FMP API key. Defaults to FMP_API_KEY env var.
    """
    api_key = api_key or FMP_API_KEY
    if not api_key:
        raise ValueError("FMP_API_KEY not set")

    end_date = end_date or dt.date.today().isoformat()
    url = f"{FMP_BASE_URL}/historical-price-eod/full"
    params = {"symbol": symbol, "from": start_date, "to": end_date, "apikey": api_key}

    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not data:
        print(f"  No data returned for {symbol}")
        return []

    return [
        {
            "symbol": row["symbol"],
            "date": row["date"],
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "adj_close": None,
            "volume": row["volume"],
            "change_percent": row.get("changePercent"),
        }
        for row in data
    ]


def fetch_treasury_rates(
    start_date: str,
    end_date: str | None = None,
    api_key: str | None = None,
) -> list[dict]:
    """Fetch daily US Treasury rates from FMP API.

    Args:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date. Defaults to today.
        api_key: FMP API key. Defaults to FMP_API_KEY env var.
    """
    api_key = api_key or FMP_API_KEY
    if not api_key:
        raise ValueError("FMP_API_KEY not set")

    end_date = end_date or dt.date.today().isoformat()
    url = f"{FMP_BASE_URL}/treasury-rates"
    params = {"from": start_date, "to": end_date, "apikey": api_key}

    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not data:
        print("  No treasury rate data returned")
        return []

    return [
        {
            "date": row["date"],
            "year2": row.get("year2"),
            "year10": row.get("year10"),
            "year30": row.get("year30"),
        }
        for row in data
    ]


def upsert_treasury_rates(engine, rows: list[dict]) -> int:
    """Insert or update treasury rate rows.

    Args:
        engine: SQLAlchemy engine.
        rows: List of treasury rate dicts.

    Returns:
        Number of rows inserted/updated.
    """
    if not rows:
        return 0

    inserted = 0
    with engine.begin() as conn:
        for row in rows:
            stmt = text("""
                INSERT INTO treasury_rates (date, year2, year10, year30)
                VALUES (:date, :year2, :year10, :year30)
                ON CONFLICT (date) DO UPDATE SET
                    year2 = EXCLUDED.year2,
                    year10 = EXCLUDED.year10,
                    year30 = EXCLUDED.year30
            """)
            result = conn.execute(stmt, row)
            inserted += result.rowcount
    return inserted


def fetch_vix(
    start_date: str,
    end_date: str | None = None,
    api_key: str | None = None,
) -> list[dict]:
    """Fetch daily VIX index data from FMP API.

    Args:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date. Defaults to today.
        api_key: FMP API key. Defaults to FMP_API_KEY env var.
    """
    api_key = api_key or FMP_API_KEY
    if not api_key:
        raise ValueError("FMP_API_KEY not set")

    end_date = end_date or dt.date.today().isoformat()
    url = f"{FMP_BASE_URL}/historical-price-eod/full"
    params = {"symbol": "^VIX", "from": start_date, "to": end_date, "apikey": api_key}

    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not data:
        print("  No VIX data returned")
        return []

    return [
        {
            "date": row["date"],
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "change_percent": row.get("changePercent"),
        }
        for row in data
    ]


def upsert_vix(engine, rows: list[dict]) -> int:
    """Insert or update VIX daily rows.

    Args:
        engine: SQLAlchemy engine.
        rows: List of VIX dicts.

    Returns:
        Number of rows inserted/updated.
    """
    if not rows:
        return 0

    inserted = 0
    with engine.begin() as conn:
        for row in rows:
            stmt = text("""
                INSERT INTO vix_daily (date, open, high, low, close, change_percent)
                VALUES (:date, :open, :high, :low, :close, :change_percent)
                ON CONFLICT (date) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    change_percent = EXCLUDED.change_percent
            """)
            result = conn.execute(stmt, row)
            inserted += result.rowcount
    return inserted


def upsert_ohlcv(engine, rows: list[dict]) -> int:
    """Insert OHLCV rows, skip duplicates.

    Args:
        engine: SQLAlchemy engine.
        rows: List of OHLCV dicts.

    Returns:
        Number of rows inserted.
    """
    if not rows:
        return 0

    inserted = 0
    with engine.begin() as conn:
        for row in rows:
            stmt = text("""
                INSERT INTO ohlcv_daily (symbol, date, open, high, low, close, adj_close, volume, change_percent)
                VALUES (:symbol, :date, :open, :high, :low, :close, :adj_close, :volume, :change_percent)
                ON CONFLICT (symbol, date) DO NOTHING
            """)
            result = conn.execute(stmt, row)
            inserted += result.rowcount
    return inserted


def main() -> None:
    """Run data ingestion for configured symbols and treasury rates."""
    config = load_config()
    ingestion_cfg = config["ingestion"]

    start_years_back = ingestion_cfg["start_years_back"]
    today = dt.date.today()
    default_start = today.replace(year=today.year - start_years_back).isoformat()

    parser = argparse.ArgumentParser(description="Ingest FMP OHLCV data")
    parser.add_argument("--symbols", nargs="+", default=ingestion_cfg["symbols"])
    parser.add_argument("--start", default=default_start)
    parser.add_argument("--end", default=ingestion_cfg.get("end_date"))
    parser.add_argument(
        "--skip-treasury", action="store_true", help="Skip treasury rate ingestion"
    )
    parser.add_argument(
        "--skip-vix", action="store_true", help="Skip VIX ingestion"
    )
    args = parser.parse_args()

    engine = get_engine()
    init_db(engine)

    # --- OHLCV ingestion ---
    total = 0
    failed: list[str] = []
    for i, symbol in enumerate(args.symbols, 1):
        print(f"[{i}/{len(args.symbols)}] Fetching {symbol}...")
        try:
            rows = fetch_ohlcv(symbol, args.start, args.end)
            n = upsert_ohlcv(engine, rows)
            print(f"  {symbol}: {n} new rows inserted ({len(rows)} fetched)")
            total += n
        except httpx.HTTPStatusError as e:
            print(f"  {symbol}: SKIPPED (HTTP {e.response.status_code})")
            failed.append(symbol)

    print(f"\nOHLCV done. {total} total new rows inserted.")
    if failed:
        print(f"  Failed symbols ({len(failed)}): {', '.join(failed)}")

    # --- Treasury rates ingestion ---
    if not args.skip_treasury:
        print("\nFetching treasury rates...")
        treasury_rows = fetch_treasury_rates(args.start, args.end)
        n_treasury = upsert_treasury_rates(engine, treasury_rows)
        print(
            f"  Treasury rates: {n_treasury} rows inserted/updated"
            f" ({len(treasury_rows)} fetched)"
        )

    # --- VIX ingestion ---
    if not args.skip_vix:
        print("\nFetching VIX data...")
        vix_rows = fetch_vix(args.start, args.end)
        n_vix = upsert_vix(engine, vix_rows)
        print(
            f"  VIX: {n_vix} rows inserted/updated"
            f" ({len(vix_rows)} fetched)"
        )


if __name__ == "__main__":
    main()
