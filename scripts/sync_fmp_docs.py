#!/usr/bin/env python3
"""Download FMP developer documentation (stable API pages) for offline use.

The public docs site returns 403 to default curl; this script uses a browser-like
User-Agent and parses embedded Next.js __NEXT_DATA__ JSON.

Usage:
    uv run python scripts/sync_fmp_docs.py
    uv run python scripts/sync_fmp_docs.py --verify  # needs FMP_API_KEY in env

Output under repo root: fmp-docs/
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import re
import sys
import time
from pathlib import Path

import httpx

SITE_BASE = "https://site.financialmodelingprep.com"
DOCS_MAIN = f"{SITE_BASE}/developer/docs"
API_BASE = "https://financialmodelingprep.com/stable"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    s = re.sub(r"</p>\s*", "\n\n", s, flags=re.I)
    s = re.sub(r"</li>\s*", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return html_module.unescape(s).strip()


def _extract_slugs(main_html: str) -> list[str]:
    found = set(re.findall(r"/developer/docs/stable/([a-z0-9-]+)", main_html))
    return sorted(found)


def _fetch_doc_page(client: httpx.Client, slug: str) -> dict | None:
    url = f"{SITE_BASE}/developer/docs/stable/{slug}"
    r = client.get(url)
    r.raise_for_status()
    m = NEXT_DATA_RE.search(r.text)
    if not m:
        return None
    data = json.loads(m.group(1))
    doc = data.get("props", {}).get("pageProps", {}).get("doc")
    if not isinstance(doc, dict):
        return None
    return doc


def _doc_to_markdown(slug: str, doc: dict) -> str:
    title = doc.get("title") or slug
    desc = doc.get("description") or ""
    urls = doc.get("urls") or []
    content_html = doc.get("content") or ""
    params = doc.get("params") or {}
    related = doc.get("relatedIDs") or []

    lines = [
        f"# {title}",
        "",
        f"**Source:** [{SITE_BASE}/developer/docs/stable/{slug}]"
        f"({SITE_BASE}/developer/docs/stable/{slug})",
        "",
        desc,
        "",
    ]
    if urls:
        lines.append("## Endpoint URLs")
        for u in urls:
            lines.append(f"- `{u}`")
        lines.append("")
    body = _html_to_text(content_html)
    if body:
        lines.append("## Description")
        lines.append(body)
        lines.append("")
    if params:
        lines.append("## Parameters (from docs JSON)")
        lines.append("```json")
        lines.append(json.dumps(params, indent=2))
        lines.append("```")
        lines.append("")
    if related:
        lines.append("## Related API slugs")
        lines.append(", ".join(f"`{r}`" for r in related))
        lines.append("")
    return "\n".join(lines)


def sync_docs(output_dir: Path, delay_s: float) -> tuple[int, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stable_dir = output_dir / "stable"
    stable_dir.mkdir(exist_ok=True)

    headers = {"User-Agent": USER_AGENT}
    ok, fail = 0, 0

    with httpx.Client(headers=headers, timeout=60.0, follow_redirects=True) as client:
        main = client.get(DOCS_MAIN)
        main.raise_for_status()
        slugs = _extract_slugs(main.text)
        (output_dir / "developer-docs-main.html").write_text(main.text, encoding="utf-8")

        for i, slug in enumerate(slugs):
            try:
                doc = _fetch_doc_page(client, slug)
                if doc is None:
                    print(f"  skip (no __NEXT_DATA__ doc): {slug}", file=sys.stderr)
                    fail += 1
                    continue
                md = _doc_to_markdown(slug, doc)
                (stable_dir / f"{slug}.md").write_text(md, encoding="utf-8")
                ok += 1
                if (i + 1) % 50 == 0:
                    print(f"  ... {i + 1}/{len(slugs)}")
            except Exception as e:
                print(f"  ERROR {slug}: {e}", file=sys.stderr)
                fail += 1
            time.sleep(delay_s)

        # Auto-generated list of stable pages (do not hand-edit; re-run sync)
        index_lines = [
            "# Índice API stable (generado)",
            "",
            f"Fuente: [{DOCS_MAIN}]({DOCS_MAIN}). "
            "Regenerar con `uv run python scripts/sync_fmp_docs.py`.",
            "",
        ]
        for slug in slugs:
            if (stable_dir / f"{slug}.md").exists():
                index_lines.append(f"- [{slug}](stable/{slug}.md)")
        (output_dir / "STABLE_INDEX.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    return ok, fail


def verify_sample_endpoints(api_key: str) -> None:
    """Smoke-test a few stable endpoints relevant to the trading pipeline."""
    tests = [
        ("/sp500-constituent", {}),
        ("/historical-price-eod/full", {"symbol": "AAPL", "from": "2024-01-02"}),
        ("/treasury-rates", {}),
        ("/profile", {"symbol": "AAPL"}),
        ("/key-metrics", {"symbol": "AAPL", "period": "quarter", "limit": 1}),
        ("/ratios", {"symbol": "AAPL", "period": "quarter", "limit": 1}),
        ("/historical-sector-performance", {"sector": "Technology", "from": "2024-01-01"}),
        ("/batch-quote", {"symbols": "AAPL,MSFT"}),
        # Path per FMP stable docs (not "economics-indicators")
        ("/economic-indicators", {"name": "GDP"}),
    ]
    params_base = {"apikey": api_key}
    with httpx.Client(timeout=60.0) as client:
        for path, extra in tests:
            url = f"{API_BASE}{path}"
            r = client.get(url, params={**params_base, **extra})
            snippet = r.text[:120].replace("\n", " ")
            status = "OK" if r.is_success else "FAIL"
            print(f"  {status} {path} -> HTTP {r.status_code} {snippet}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync FMP developer docs locally")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "fmp-docs",
        help="Output directory",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.12,
        help="Delay between doc page requests (seconds)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="After sync, smoke-test API endpoints (set FMP_API_KEY)",
    )
    args = parser.parse_args()

    print(f"Syncing FMP docs to {args.output} ...")
    ok, fail = sync_docs(args.output, args.delay)
    print(f"Done: {ok} pages written, {fail} failed/skipped.")

    if args.verify:
        import os

        key = os.environ.get("FMP_API_KEY", "").strip()
        if not key:
            print("FMP_API_KEY not set; skipping --verify", file=sys.stderr)
            return
        print("Verifying sample API endpoints...")
        verify_sample_endpoints(key)


if __name__ == "__main__":
    main()
