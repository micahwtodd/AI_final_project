"""SEC EDGAR client (free, no key).

The SEC's fair-access policy asks automated tools to declare who they are in the
User-Agent header and to stay under 10 requests per second. Grading never
depends on these calls: the game reads cached profiles in data/profiles/.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import httpx

from backend.env import REPO_DIR, load_env

DEFAULT_CONTACT = "Micah Todd micah.todd@yale.edu"
CACHE_DIR = REPO_DIR / "data" / "cache"  # raw EDGAR downloads, git-ignored

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"

_MIN_INTERVAL = 0.15  # about 6-7 requests a second, under the SEC's limit of 10
_lock = threading.Lock()
_last_request = 0.0


def user_agent() -> str:
    load_env()
    return os.environ.get("EDGAR_CONTACT") or DEFAULT_CONTACT


def _get(url: str) -> httpx.Response:
    global _last_request
    with _lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
    r = httpx.get(url, headers={"User-Agent": user_agent(), "Accept-Encoding": "gzip, deflate"},
                  timeout=60, follow_redirects=True)
    r.raise_for_status()
    return r


def _cached_json(name: str, url: str, refresh: bool = False) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / name
    if path.is_file() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    data = _get(url).json()
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def ticker_to_cik(ticker: str) -> int:
    table = _cached_json("company_tickers.json", TICKERS_URL)
    for row in table.values():
        if row["ticker"].upper() == ticker.upper():
            return int(row["cik_str"])
    raise KeyError(f"Ticker not found on EDGAR: {ticker}")


def company_facts(ticker: str, refresh: bool = False) -> dict:
    cik = ticker_to_cik(ticker)
    return _cached_json(f"facts_{ticker.upper()}.json", FACTS_URL.format(cik=cik), refresh)


def submissions(ticker: str, refresh: bool = False) -> dict:
    cik = ticker_to_cik(ticker)
    return _cached_json(f"submissions_{ticker.upper()}.json", SUBMISSIONS_URL.format(cik=cik), refresh)


def latest_10k(ticker: str) -> dict:
    """{accession, filing_date, report_date, primary_document, url} for the latest 10-K."""
    sub = submissions(ticker)
    recent = sub["filings"]["recent"]
    for i, form in enumerate(recent["form"]):
        if form == "10-K":
            acc = recent["accessionNumber"][i]
            doc = recent["primaryDocument"][i]
            return {
                "accession": acc,
                "filing_date": recent["filingDate"][i],
                "report_date": recent["reportDate"][i],
                "primary_document": doc,
                "url": ARCHIVE_URL.format(cik=int(sub["cik"]), acc=acc.replace("-", ""), doc=doc),
            }
    raise LookupError(f"No 10-K found for {ticker}")


def filing_document(ticker: str, refresh: bool = False) -> str:
    """Raw HTML of the latest 10-K's primary document (cached)."""
    info = latest_10k(ticker)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"10k_{ticker.upper()}_{info['accession']}.htm"
    if path.is_file() and not refresh:
        return path.read_text(encoding="utf-8", errors="ignore")
    html = _get(info["url"]).text
    path.write_text(html, encoding="utf-8")
    return html
