"""Discover and document FMP API endpoint response structures."""
import json
import urllib.request
import urllib.error
import ssl
import sys

ssl._create_default_https_context = ssl._create_unverified_context

API_KEY = "0ENjHpFWpiC9mKG2qqgSTSu1cbCCN9XM"
BASE = "https://financialmodelingprep.com"

# New /stable endpoints (FMP deprecated /api/v3 after Aug 2025)
ENDPOINTS = {
    "COMPANY INFO": [
        ("1. Profile", f"/stable/profile?symbol=AAPL&apikey={API_KEY}"),
        ("2. Stock Screener", f"/stable/stock-screener?limit=3&marketCapMoreThan=1000000000&apikey={API_KEY}"),
        ("3. Most Active", f"/stable/most-active?apikey={API_KEY}"),
        ("4. Top Gainers", f"/stable/top-gainers?apikey={API_KEY}"),
        ("5. Top Losers", f"/stable/top-losers?apikey={API_KEY}"),
    ],
    "FINANCIAL STATEMENTS": [
        ("6. Income Statement", f"/stable/income-statement?symbol=AAPL&period=quarter&limit=2&apikey={API_KEY}"),
        ("7. Balance Sheet", f"/stable/balance-sheet-statement?symbol=AAPL&period=quarter&limit=2&apikey={API_KEY}"),
        ("8. Cash Flow", f"/stable/cash-flow-statement?symbol=AAPL&period=quarter&limit=2&apikey={API_KEY}"),
        ("9. Income Statement Growth", f"/stable/income-statement-growth?symbol=AAPL&period=quarter&limit=2&apikey={API_KEY}"),
        ("10. Financial Growth", f"/stable/financial-growth?symbol=AAPL&period=quarter&limit=2&apikey={API_KEY}"),
    ],
    "RATIOS & METRICS": [
        ("11. Ratios (Quarterly)", f"/stable/ratios?symbol=AAPL&period=quarter&limit=2&apikey={API_KEY}"),
        ("12. Key Metrics (Quarterly)", f"/stable/key-metrics?symbol=AAPL&period=quarter&limit=2&apikey={API_KEY}"),
        ("13. Ratios TTM", f"/stable/ratios-ttm?symbol=AAPL&apikey={API_KEY}"),
        ("14. Key Metrics TTM", f"/stable/key-metrics-ttm?symbol=AAPL&apikey={API_KEY}"),
        ("15. Enterprise Values", f"/stable/enterprise-values?symbol=AAPL&period=quarter&limit=2&apikey={API_KEY}"),
    ],
    "ANALYST & ESTIMATES": [
        ("16. Analyst Estimates", f"/stable/analyst-estimates?symbol=AAPL&period=quarter&limit=2&apikey={API_KEY}"),
        ("17. Analyst Recommendations", f"/stable/analyst-stock-recommendations?symbol=AAPL&limit=5&apikey={API_KEY}"),
        ("18. Price Target", f"/stable/price-target?symbol=AAPL&apikey={API_KEY}"),
        ("19. Upgrades/Downgrades", f"/stable/upgrades-downgrades?symbol=AAPL&apikey={API_KEY}"),
        ("20. Grade", f"/stable/grade?symbol=AAPL&limit=5&apikey={API_KEY}"),
    ],
}

def fetch(path: str):
    url = BASE + path
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        return {"__error__": f"HTTP {e.code}", "__body__": body}
    except Exception as e:
        return {"__error__": str(e)}

def describe_value(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return f"boolean (sample: {v})"
    if isinstance(v, int):
        return f"integer (sample: {v})"
    if isinstance(v, float):
        return f"float (sample: {v})"
    if isinstance(v, str):
        if len(v) > 60:
            return f'string (sample: "{v[:57]}...")'
        return f'string (sample: "{v}")'
    if isinstance(v, list):
        return f"array[{len(v)} items]"
    if isinstance(v, dict):
        return f"object({len(v)} keys)"
    return type(v).__name__

def print_fields(obj, indent=2):
    if isinstance(obj, list):
        if len(obj) == 0:
            print(" " * indent + "(empty array)")
            return
        print(f"{' ' * indent}Response: Array with {len(obj)} items. First item fields:")
        obj = obj[0]
    if isinstance(obj, dict):
        for k, v in obj.items():
            print(f"{' ' * indent}  {k}: {describe_value(v)}")
    else:
        print(f"{' ' * indent}{describe_value(obj)}")

for category, endpoints in ENDPOINTS.items():
    print(f"\n{'='*80}")
    print(f"  {category}")
    print(f"{'='*80}")
    for name, path in endpoints:
        # Strip apikey from display path
        display_path = path.split("?")[0] + "?" + "&".join(
            p for p in path.split("?")[1].split("&") if not p.startswith("apikey=")
        )
        print(f"\n--- {name} ---")
        print(f"  GET {BASE}{display_path.rstrip('?').rstrip('&')}")
        data = fetch(path)
        if isinstance(data, dict) and "__error__" in data:
            print(f"  ERROR: {data['__error__']}")
            if data.get("__body__"):
                print(f"  Body: {data['__body__']}")
            continue
        print_fields(data)
    print()
