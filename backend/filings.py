"""10-K text: sanitize, chunk, and retrieve by keyword scoring (the Lecture 10 pattern).

Seamore never sees a whole filing: only the top-k chunks for each question.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache

from backend import edgar, safety
from backend.env import REPO_DIR

CHUNK_CHARS = 1400
OVERLAP = 200
SAMPLE_DIR = REPO_DIR / "data" / "filings_sample"
STOP = set("the of and to in a for on is are was were by with as at or from that this be an it its our we which".split())


def _tokens(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9\-]+|\d+(?:\.\d+)?%?", s.lower()) if w not in STOP]


TEST_FILINGS: dict[str, tuple[str, bool]] = {}  # ticker -> (html, sanitize?) for Safety Lab fixtures


def naive_text(html: str) -> str:
    """What a pipeline WITHOUT the sanitizer sees: tags stripped, hidden text and comments kept."""
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html)
    s = s.replace("<!--", " ").replace("-->", " ")
    s = re.sub(r"(?i)</?(p|div|tr|br|h\d|table|li)\b[^>]*>", "\n", s)
    s = re.sub(r"(?i)</?t[dh]\b[^>]*>", " | ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"[ \t]+", " ", s)


@lru_cache(maxsize=16)
def chunks_for(ticker: str, html: str | None = None) -> tuple[list[dict], dict]:
    """Sanitized chunks of the latest 10-K, and a report of what the sanitizer removed or quarantined.
    Instruction-like paragraphs are quarantined one by one, so the real data around them survives."""
    sanitize = True
    if html is None and ticker in TEST_FILINGS:
        html, sanitize = TEST_FILINGS[ticker]
    raw = html if html is not None else edgar.filing_document(ticker)
    if sanitize:
        text, removed = safety.html_to_text(raw)
    else:
        text, removed = naive_text(raw), {"hidden_elements": 0, "comments": 0, "zero_width_chars": 0, "sanitizer": "off"}
    out, buf, quarantined = [], "", []
    for para in (p.strip() for p in text.split("\n")):
        if len(para) <= 3:
            continue
        if sanitize and safety.looks_like_instructions(para):
            quarantined.append({"text": para[:300]})
            continue
        if len(buf) + len(para) + 1 > CHUNK_CHARS and buf:
            out.append(buf)
            buf = buf[-OVERLAP:]
        buf = f"{buf}\n{para}" if buf else para
    if buf:
        out.append(buf)
    chunks = [{"chunk_id": i, "text": c} for i, c in enumerate(out)]
    return chunks, {**removed, "chunks": len(chunks), "quarantined": quarantined}


def register_test_filing(ticker: str, html: str, sanitize: bool = True) -> None:
    TEST_FILINGS[ticker] = (html, sanitize)
    chunks_for.cache_clear()
    _index.cache_clear()


def _idf(chunks: list[dict]) -> dict[str, float]:
    df = Counter()
    for c in chunks:
        df.update(set(_tokens(c["text"])))
    n = len(chunks)
    return {w: math.log((n + 1) / (d + 0.5)) for w, d in df.items()}


@lru_cache(maxsize=8)
def _index(ticker: str):
    chunks, _ = chunks_for(ticker)
    return chunks, _idf(chunks)


def search(ticker: str, query: str, k: int = 4) -> list[dict]:
    """Top-k chunks by TF-IDF keyword score. Tables with numbers get a small boost."""
    chunks, idf = _index(ticker)
    q = [w for w in _tokens(query)]
    scored = []
    for c in chunks:
        tf = Counter(_tokens(c["text"]))
        s = sum(idf.get(w, 0.0) * (1 + math.log(tf[w])) for w in q if tf[w])
        if s > 0:
            s *= 1.0 + 0.15 * min(5, c["text"].count("%")) / 5 + (0.1 if " | " in c["text"] else 0)
            scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    return [{"chunk_id": c["chunk_id"], "score": round(s, 2), "text": c["text"]} for s, c in scored[:k]]


def save_sample(ticker: str, used: dict[int, str]) -> None:
    """Commit only the chunks Seamore actually used, as evidence."""
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    info = edgar.latest_10k(ticker)
    (SAMPLE_DIR / f"{ticker}.json").write_text(json.dumps(
        {"ticker": ticker, "accession": info["accession"], "url": info["url"],
         "chunks": [{"chunk_id": k, "text": v} for k, v in sorted(used.items())]}, indent=1), encoding="utf-8")
