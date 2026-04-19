"""FMP API data ingestion into PostgreSQL.

Usage:
    uv run python -m src.ingestion.fmp_loader
    uv run python -m src.ingestion.fmp_loader --symbols AAPL MSFT --start 2023-01-01
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path

import httpx
from sqlalchemy import text

from src.config import load_config
from src.db import get_engine, in_params, init_db
from src.keys import FMP_API_KEY

FMP_BASE_URL = "https://financialmodelingprep.com/stable"

_MAX_RETRIES = 3
_RETRY_BACKOFF = 2.0


def _get_with_retry(url: str, params: dict, timeout: int = 60) -> httpx.Response:
    """HTTP GET with exponential backoff retry on transient connection errors."""
    for attempt in range(_MAX_RETRIES):
        try:
            resp = httpx.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except (httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.TimeoutException) as e:
            if attempt == _MAX_RETRIES - 1:
                raise
            wait = _RETRY_BACKOFF ** (attempt + 1)
            print(f"  Connection error ({e}), retrying in {wait:.0f}s...")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def fetch_sp500_constituents(
    api_key: str | None = None,
    sectors: list[str] | None = None,
) -> list[str]:
    """Fetch current S&P 500 constituent symbols from FMP API.

    Args:
        api_key: FMP API key.
        sectors: If provided, only return symbols from these GICS sectors.

    Returns:
        Sorted list of ticker symbols.
    """
    api_key = api_key or FMP_API_KEY
    if not api_key:
        raise ValueError("FMP_API_KEY not set")

    url = f"{FMP_BASE_URL}/sp500-constituent"
    resp = _get_with_retry(url, params={"apikey": api_key})
    data = resp.json()

    if sectors:
        sector_set = set(sectors)
        data = [row for row in data if row.get("sector") in sector_set]
        print(f"Filtered to {len(data)} symbols in sectors: {', '.join(sectors)}")

    symbols = sorted({row["symbol"].replace(".", "-") for row in data})
    print(f"Fetched {len(symbols)} S&P 500 constituents from FMP")
    return symbols


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

    resp = _get_with_retry(url, params=params)
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


_TREASURY_TENORS = [
    "month1",
    "month2",
    "month3",
    "month6",
    "year1",
    "year2",
    "year3",
    "year5",
    "year7",
    "year10",
    "year20",
    "year30",
]


def fetch_treasury_rates(
    start_date: str,
    end_date: str | None = None,
    api_key: str | None = None,
) -> list[dict]:
    """Fetch daily US Treasury rates (all 12 tenors) from FMP API.

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

    resp = _get_with_retry(url, params=params)
    data = resp.json()

    if not data:
        print("  No treasury rate data returned")
        return []

    return [{"date": row["date"], **{t: row.get(t) for t in _TREASURY_TENORS}} for row in data]


def upsert_treasury_rates(engine, rows: list[dict]) -> int:
    """Insert or update treasury rate rows (all 12 tenors)."""
    if not rows:
        return 0

    cols = ", ".join(_TREASURY_TENORS)
    params = ", ".join(f":{t}" for t in _TREASURY_TENORS)
    updates = ", ".join(f"{t} = EXCLUDED.{t}" for t in _TREASURY_TENORS)

    inserted = 0
    with engine.begin() as conn:
        for row in rows:
            stmt = text(f"""
                INSERT INTO treasury_rates (date, {cols})
                VALUES (:date, {params})
                ON CONFLICT (date) DO UPDATE SET {updates}
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

    resp = _get_with_retry(url, params=params)
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
                INSERT INTO ohlcv_daily
                    (symbol, date, open, high, low, close, adj_close, volume, change_percent)
                VALUES
                    (:symbol, :date, :open, :high, :low, :close, :adj_close, :volume,
                     :change_percent)
                ON CONFLICT (symbol, date) DO NOTHING
            """)
            result = conn.execute(stmt, row)
            inserted += result.rowcount
    return inserted


def fetch_sectors(
    symbols: list[str],
    api_key: str | None = None,
) -> list[dict]:
    """Fetch GICS sector information for symbols from FMP API.

    Args:
        symbols: List of ticker symbols.
        api_key: FMP API key. Defaults to FMP_API_KEY env var.
    """
    api_key = api_key or FMP_API_KEY
    if not api_key:
        raise ValueError("FMP_API_KEY not set")

    results = []
    for symbol in symbols:
        url = f"{FMP_BASE_URL}/profile"
        params = {"symbol": symbol, "apikey": api_key}
        try:
            resp = _get_with_retry(url, params=params)
            data = resp.json()
            if data and len(data) > 0:
                profile = data[0]
                results.append(
                    {
                        "symbol": symbol,
                        "sector": profile.get("sector", "Unknown"),
                        "sub_industry": profile.get("industry"),
                    }
                )
        except httpx.HTTPStatusError:
            results.append(
                {
                    "symbol": symbol,
                    "sector": "Unknown",
                    "sub_industry": None,
                }
            )

    return results


def upsert_sectors(engine, rows: list[dict]) -> int:
    """Insert or update stock sector rows.

    Args:
        engine: SQLAlchemy engine.
        rows: List of sector dicts with symbol, sector, sub_industry.

    Returns:
        Number of rows inserted/updated.
    """
    if not rows:
        return 0

    inserted = 0
    with engine.begin() as conn:
        for row in rows:
            stmt = text("""
                INSERT INTO stock_sectors (symbol, sector, sub_industry, updated_at)
                VALUES (:symbol, :sector, :sub_industry, NOW())
                ON CONFLICT (symbol) DO UPDATE SET
                    sector = EXCLUDED.sector,
                    sub_industry = EXCLUDED.sub_industry,
                    updated_at = NOW()
            """)
            result = conn.execute(stmt, row)
            inserted += result.rowcount
    return inserted


def fetch_adj_close(
    symbol: str,
    start_date: str,
    end_date: str | None = None,
    api_key: str | None = None,
) -> list[dict]:
    """Fetch dividend-adjusted close prices from FMP API.

    Args:
        symbol: Ticker symbol.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date. Defaults to today.
        api_key: FMP API key.
    """
    api_key = api_key or FMP_API_KEY
    if not api_key:
        raise ValueError("FMP_API_KEY not set")

    end_date = end_date or dt.date.today().isoformat()
    url = f"{FMP_BASE_URL}/historical-price-eod/dividend-adjusted"
    params = {"symbol": symbol, "from": start_date, "to": end_date, "apikey": api_key}

    resp = _get_with_retry(url, params=params)
    data = resp.json()

    if not data:
        return []

    return [
        {"symbol": symbol, "date": row["date"], "adj_close": row.get("adjClose")} for row in data
    ]


def update_adj_close(engine, rows: list[dict]) -> int:
    """Update adj_close column in ohlcv_daily for existing rows."""
    if not rows:
        return 0

    updated = 0
    with engine.begin() as conn:
        for row in rows:
            stmt = text("""
                UPDATE ohlcv_daily SET adj_close = :adj_close
                WHERE symbol = :symbol AND date = :date
            """)
            result = conn.execute(stmt, row)
            updated += result.rowcount
    return updated


_PROBE_OFFSETS_DAYS = [30, 180, 730]
_ADJCLOSE_TOLERANCE = 0.001


def check_adjclose_changed(
    engine,
    symbol: str,
    api_key: str | None = None,
) -> bool:
    """Probe a few historical dates to detect if adjClose has been recalculated.

    Fetches adjClose for 3 reference dates (1mo, 6mo, 2yr ago) from FMP and
    compares against the stored values. Returns True if any value differs or
    if the symbol has no adjClose data yet.

    Args:
        engine: SQLAlchemy engine.
        symbol: Ticker symbol.
        api_key: FMP API key.
    """
    today = dt.date.today()

    probe_dates = [(today - dt.timedelta(days=d)).isoformat() for d in _PROBE_OFFSETS_DAYS]

    with engine.connect() as conn:
        ph, params = in_params("d", probe_dates)
        params["symbol"] = symbol
        result = conn.execute(
            text(f"""
            SELECT date, adj_close FROM ohlcv_daily
            WHERE symbol = :symbol AND date IN ({ph})
            ORDER BY date
        """),
            params,
        )
        db_rows = {str(row[0]): row[1] for row in result}

    if not db_rows or any(v is None for v in db_rows.values()):
        return True

    api_key = api_key or FMP_API_KEY
    for probe_date in probe_dates:
        if probe_date not in db_rows:
            continue
        try:
            rows = fetch_adj_close(symbol, probe_date, probe_date, api_key)
            if not rows:
                continue
            api_val = rows[0].get("adj_close")
            if api_val is None:
                continue
            db_val = db_rows[probe_date]
            if abs(api_val - db_val) > _ADJCLOSE_TOLERANCE:
                return True
        except httpx.HTTPStatusError:
            continue

    return False


def fetch_key_metrics(
    symbol: str,
    period: str = "quarter",
    api_key: str | None = None,
    start_date: str | None = None,
    limit: int = 84,
) -> list[dict]:
    """Fetch key metrics for a symbol from FMP API.

    Args:
        symbol: Ticker symbol.
        period: Reporting period ('quarter' or 'annual').
        api_key: FMP API key.
        start_date: If provided, discard rows with date before this (YYYY-MM-DD).
        limit: Maximum number of quarterly records to fetch (84 = 21 years, covers
            prod's 20-year window plus 1 year margin for forward-fill).
    """
    api_key = api_key or FMP_API_KEY
    if not api_key:
        raise ValueError("FMP_API_KEY not set")

    url = f"{FMP_BASE_URL}/key-metrics"
    params = {"symbol": symbol, "period": period, "limit": limit, "apikey": api_key}

    resp = _get_with_retry(url, params=params)
    data = resp.json()

    if not data:
        return []

    results = []
    for row in data:
        if start_date and row["date"] < start_date:
            continue
        meta = {
            "symbol": row.get("symbol", symbol),
            "date": row["date"],
            "fiscal_year": row.get("fiscalYear"),
            "period": row.get("period"),
        }
        metrics = {
            k: v
            for k, v in row.items()
            if k not in ("symbol", "date", "fiscalYear", "period", "reportedCurrency")
        }
        meta["data"] = json.dumps(metrics)
        results.append(meta)
    return results


def upsert_key_metrics(engine, rows: list[dict]) -> int:
    """Insert or update key metrics quarterly rows."""
    if not rows:
        return 0

    inserted = 0
    with engine.begin() as conn:
        for row in rows:
            stmt = text("""
                INSERT INTO key_metrics_quarterly (symbol, date, fiscal_year, period, data)
                VALUES (:symbol, :date, :fiscal_year, :period, CAST(:data AS jsonb))
                ON CONFLICT (symbol, date, period) DO UPDATE SET
                    fiscal_year = EXCLUDED.fiscal_year,
                    data = EXCLUDED.data
            """)
            result = conn.execute(stmt, row)
            inserted += result.rowcount
    return inserted


def fetch_financial_ratios(
    symbol: str,
    period: str = "quarter",
    api_key: str | None = None,
    start_date: str | None = None,
    limit: int = 84,
) -> list[dict]:
    """Fetch financial ratios for a symbol from FMP API.

    Args:
        symbol: Ticker symbol.
        period: Reporting period ('quarter' or 'annual').
        api_key: FMP API key.
        start_date: If provided, discard rows with date before this (YYYY-MM-DD).
        limit: Maximum number of quarterly records to fetch (84 = 21 years, covers
            prod's 20-year window plus 1 year margin for forward-fill).
    """
    api_key = api_key or FMP_API_KEY
    if not api_key:
        raise ValueError("FMP_API_KEY not set")

    url = f"{FMP_BASE_URL}/ratios"
    params = {"symbol": symbol, "period": period, "limit": limit, "apikey": api_key}

    resp = _get_with_retry(url, params=params)
    data = resp.json()

    if not data:
        return []

    results = []
    for row in data:
        if start_date and row["date"] < start_date:
            continue
        meta = {
            "symbol": row.get("symbol", symbol),
            "date": row["date"],
            "fiscal_year": row.get("fiscalYear"),
            "period": row.get("period"),
        }
        ratios = {
            k: v
            for k, v in row.items()
            if k not in ("symbol", "date", "fiscalYear", "period", "reportedCurrency")
        }
        meta["data"] = json.dumps(ratios)
        results.append(meta)
    return results


def upsert_financial_ratios(engine, rows: list[dict]) -> int:
    """Insert or update financial ratios quarterly rows."""
    if not rows:
        return 0

    inserted = 0
    with engine.begin() as conn:
        for row in rows:
            stmt = text("""
                INSERT INTO financial_ratios_quarterly (symbol, date, fiscal_year, period, data)
                VALUES (:symbol, :date, :fiscal_year, :period, CAST(:data AS jsonb))
                ON CONFLICT (symbol, date, period) DO UPDATE SET
                    fiscal_year = EXCLUDED.fiscal_year,
                    data = EXCLUDED.data
            """)
            result = conn.execute(stmt, row)
            inserted += result.rowcount
    return inserted


GICS_SECTORS = [
    "Technology",
    "Healthcare",
    "Financial Services",
    "Consumer Cyclical",
    "Communication Services",
    "Industrials",
    "Consumer Defensive",
    "Energy",
    "Real Estate",
    "Utilities",
    "Basic Materials",
]


def fetch_sector_performance(
    sector: str,
    start_date: str,
    end_date: str | None = None,
    api_key: str | None = None,
) -> list[dict]:
    """Fetch historical sector performance from FMP API.

    Args:
        sector: GICS sector name (e.g. 'Technology').
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date. Defaults to today.
        api_key: FMP API key.
    """
    api_key = api_key or FMP_API_KEY
    if not api_key:
        raise ValueError("FMP_API_KEY not set")

    end_date = end_date or dt.date.today().isoformat()
    url = f"{FMP_BASE_URL}/historical-sector-performance"
    params = {"sector": sector, "from": start_date, "to": end_date, "apikey": api_key}

    resp = _get_with_retry(url, params=params)
    data = resp.json()

    if not data:
        return []

    return [
        {
            "date": row["date"],
            "sector": row["sector"],
            "exchange": row.get("exchange", ""),
            "average_change": row.get("averageChange"),
        }
        for row in data
    ]


def upsert_sector_performance(engine, rows: list[dict]) -> int:
    """Insert or update sector performance daily rows."""
    if not rows:
        return 0

    inserted = 0
    with engine.begin() as conn:
        for row in rows:
            stmt = text("""
                INSERT INTO sector_performance_daily (date, sector, exchange, average_change)
                VALUES (:date, :sector, :exchange, :average_change)
                ON CONFLICT (date, sector, exchange) DO UPDATE SET
                    average_change = EXCLUDED.average_change
            """)
            result = conn.execute(stmt, row)
            inserted += result.rowcount
    return inserted


def main() -> None:
    """Run data ingestion for configured symbols and treasury rates."""
    config = load_config()
    ingestion_cfg = config["ingestion"]

    from src.config import resolve_start_years_back
    from src.keys import PIPELINE_ENV

    start_years_back = resolve_start_years_back(config)
    print(f"Pipeline environment: {PIPELINE_ENV} ({start_years_back} years of data)")
    today = dt.date.today()
    default_start = today.replace(year=today.year - start_years_back).isoformat()

    # Resolve symbol list: dynamic from API or static from config
    source = ingestion_cfg.get("source", "static")
    if source == "sp500":
        all_symbols = fetch_sp500_constituents()
    else:
        all_symbols = list(ingestion_cfg["symbols"])

    # Append benchmark symbols (SPY, etc.) if not already present
    for bm in ingestion_cfg.get("benchmark_symbols", []):
        if bm not in all_symbols:
            all_symbols.append(bm)

    parser = argparse.ArgumentParser(description="Ingest FMP data")
    parser.add_argument("--symbols", nargs="+", default=all_symbols)
    parser.add_argument("--start", default=default_start)
    parser.add_argument("--end", default=ingestion_cfg.get("end_date"))
    parser.add_argument("--skip-treasury", action="store_true", help="Skip treasury rate ingestion")
    parser.add_argument("--skip-vix", action="store_true", help="Skip VIX ingestion")
    parser.add_argument("--skip-sectors", action="store_true", help="Skip GICS sector ingestion")
    parser.add_argument(
        "--skip-adjclose", action="store_true", help="Skip adjusted close ingestion"
    )
    parser.add_argument(
        "--force-adjclose",
        action="store_true",
        help="Force full adjClose re-download without probe check",
    )
    parser.add_argument(
        "--skip-fundamentals", action="store_true", help="Skip key metrics + ratios ingestion"
    )
    parser.add_argument(
        "--skip-sector-perf", action="store_true", help="Skip historical sector performance"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force ingestion even if already completed today"
    )
    args = parser.parse_args()

    # Skip if already completed today (unless --force)
    marker_path = Path("data/.last_ingest")
    if not args.force and marker_path.exists():
        last_run = marker_path.read_text().strip()
        if last_run == today.isoformat():
            print(f"Ingestion already completed today ({today}). Use --force to re-run.")
            return

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
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
            print(f"  {symbol}: SKIPPED ({type(e).__name__}: {e})")
            failed.append(symbol)

    print(f"\nOHLCV done. {total} total new rows inserted.")
    if failed:
        print(f"  Failed symbols ({len(failed)}): {', '.join(failed)}")

    # --- Adjusted close ingestion (smart probe-and-refresh) ---
    if not args.skip_adjclose:
        force = args.force_adjclose
        mode = "FORCE" if force else "smart probe"
        print(f"\nFetching adjusted close prices ({mode})...")
        adj_total = 0
        adj_refreshed = 0
        adj_skipped = 0
        adj_failed: list[str] = []
        for i, symbol in enumerate(args.symbols, 1):
            try:
                needs_refresh = force or check_adjclose_changed(engine, symbol)
                if needs_refresh:
                    adj_rows = fetch_adj_close(symbol, args.start, args.end)
                    n = update_adj_close(engine, adj_rows)
                    adj_total += n
                    adj_refreshed += 1
                else:
                    adj_skipped += 1
                if i % 50 == 0 or i == len(args.symbols):
                    print(
                        f"  [{i}/{len(args.symbols)}] refreshed: {adj_refreshed}, "
                        f"skipped: {adj_skipped}, rows updated: {adj_total}"
                    )
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
                print(f"  {symbol}: adj_close FAILED ({type(e).__name__})")
                adj_failed.append(symbol)
        print(
            f"  Adjusted close done. {adj_refreshed} refreshed, "
            f"{adj_skipped} unchanged, {adj_total} rows updated."
        )
        if adj_failed:
            print(f"  Failed ({len(adj_failed)}): {', '.join(adj_failed[:10])}...")

    # --- Treasury rates ingestion ---
    if not args.skip_treasury:
        print("\nFetching treasury rates (12 tenors)...")
        treasury_rows = fetch_treasury_rates(args.start, args.end)
        n_treasury = upsert_treasury_rates(engine, treasury_rows)
        print(
            f"  Treasury rates: {n_treasury} rows inserted/updated ({len(treasury_rows)} fetched)"
        )

    # --- VIX ingestion ---
    if not args.skip_vix:
        print("\nFetching VIX data...")
        vix_rows = fetch_vix(args.start, args.end)
        n_vix = upsert_vix(engine, vix_rows)
        print(f"  VIX: {n_vix} rows inserted/updated ({len(vix_rows)} fetched)")

    # --- GICS sector ingestion ---
    if not args.skip_sectors:
        print("\nFetching GICS sectors...")
        sector_rows = fetch_sectors(args.symbols)
        n_sectors = upsert_sectors(engine, sector_rows)
        print(f"  Sectors: {n_sectors} rows inserted/updated ({len(sector_rows)} symbols)")

    # --- Fundamentals: key metrics + financial ratios ---
    # Only re-download if last data for a symbol is older than 90 days
    if not args.skip_fundamentals:
        print("\nFetching key metrics and financial ratios (quarterly)...")
        freshness_cutoff = (today - dt.timedelta(days=90)).isoformat()
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT symbol, MAX(date) FROM key_metrics_quarterly GROUP BY symbol")
            )
            km_last = {row[0]: str(row[1]) for row in result}
            result = conn.execute(
                text("SELECT symbol, MAX(date) FROM financial_ratios_quarterly GROUP BY symbol")
            )
            fr_last = {row[0]: str(row[1]) for row in result}

        km_total = 0
        fr_total = 0
        fund_skipped = 0
        fund_failed: list[str] = []
        for i, symbol in enumerate(args.symbols, 1):
            km_fresh = km_last.get(symbol, "") >= freshness_cutoff
            fr_fresh = fr_last.get(symbol, "") >= freshness_cutoff
            if km_fresh and fr_fresh:
                fund_skipped += 1
                if i % 50 == 0 or i == len(args.symbols):
                    print(
                        f"  [{i}/{len(args.symbols)}] key_metrics: {km_total}, "
                        f"ratios: {fr_total}, skipped: {fund_skipped}"
                    )
                continue
            try:
                if not km_fresh:
                    km_rows = fetch_key_metrics(symbol, start_date=args.start)
                    km_total += upsert_key_metrics(engine, km_rows)
                if not fr_fresh:
                    fr_rows = fetch_financial_ratios(symbol, start_date=args.start)
                    fr_total += upsert_financial_ratios(engine, fr_rows)
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
                print(f"  {symbol}: fundamentals FAILED ({type(e).__name__})")
                fund_failed.append(symbol)
            if i % 50 == 0 or i == len(args.symbols):
                print(
                    f"  [{i}/{len(args.symbols)}] key_metrics: {km_total}, "
                    f"ratios: {fr_total}, skipped: {fund_skipped}"
                )
        print(
            f"  Fundamentals done. KM: {km_total}, Ratios: {fr_total}, "
            f"skipped (fresh): {fund_skipped}"
        )
        if fund_failed:
            print(f"  Failed ({len(fund_failed)}): {', '.join(fund_failed[:10])}...")

    # --- Historical sector performance ---
    if not args.skip_sector_perf:
        print("\nFetching historical sector performance...")
        sp_total = 0
        for sector in GICS_SECTORS:
            try:
                sp_rows = fetch_sector_performance(sector, args.start, args.end)
                n = upsert_sector_performance(engine, sp_rows)
                sp_total += n
                print(f"  {sector}: {n} rows ({len(sp_rows)} fetched)")
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
                print(f"  {sector}: SKIPPED ({type(e).__name__}: {e})")
        print(f"  Sector performance done. {sp_total} total rows.")

    # Mark today's ingestion as complete and whether new data was ingested
    adj_new = adj_total > 0 if not args.skip_adjclose else False
    has_new_data = total > 0 or adj_new
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(today.isoformat())

    new_data_marker = Path("data/.new_data")
    if has_new_data:
        new_data_marker.write_text(today.isoformat())
        print("\nIngestion complete. New data flag set.")
    else:
        new_data_marker.unlink(missing_ok=True)
        print("\nIngestion complete. No new price data.")


if __name__ == "__main__":
    main()
