"""Build the six cached company profiles.

Run from the repo folder:
  python scripts/calibrate_all.py           tagged facts + Sam's targeted 10-K reading (needs an API key)
  python scripts/calibrate_all.py --tagged  tagged facts and labelled defaults only (no AI)

Writes data/profiles/{TICKER}.json, data/filings_sample/{TICKER}.json (only the chunks Sam used)
and evidence/calibration_report.json. Raw SEC downloads are cached in data/cache/ (git-ignored).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import filings, sam  # noqa: E402
from backend.calibration import TICKERS, build_profile, get_tagged_facts, save_profile  # noqa: E402
from backend.env import REPO_DIR  # noqa: E402


async def calibrate(ticker: str, use_text: bool) -> dict:
    t0 = time.time()
    _, sanitizer = filings.chunks_for(ticker)
    sanitizer = {k: (len(v) if k == "quarantined" else v) for k, v in sanitizer.items()}
    findings, run = (await sam.run_sam(ticker)) if use_text else (None, sam.CalibRun(id="none", ticker=ticker))
    accepted, rejected = sam.validate(findings, run, get_tagged_facts(ticker)) if use_text else ({}, [])
    used = {int(c["chunk_id"]): run.retrieved[c["chunk_id"]] for c in
            [{"chunk_id": int(v["citation"].split("chunk ")[1].split(":")[0])} for v in accepted.values()]
            if c["chunk_id"] in run.retrieved}
    if used:
        filings.save_sample(ticker, used)
    p = build_profile(ticker, text=accepted, rejections=rejected, sanitizer=sanitizer)
    save_profile(p)
    return {"ticker": ticker, "accepted": {k: {"value": round(v["value"], 4), "citation": v["citation"]} for k, v in accepted.items()},
            "rejected": rejected, "not_found": findings.not_found if findings else [],
            "searches": run.searches, "model_requests": run.tokens["requests"], "cost_usd": round(run.spend_usd, 5),
            "input_tokens": run.tokens["input"], "cached_tokens": run.tokens["cached"], "output_tokens": run.tokens["output"],
            "seconds": round(time.time() - t0, 1), "sanitizer": sanitizer}


async def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tagged", action="store_true", help="skip Sam (no AI)")
    ap.add_argument("--only", nargs="*", default=TICKERS)
    args = ap.parse_args()
    report = []
    for t in args.only:
        try:
            r = await calibrate(t, not args.tagged)
        except Exception as e:  # one company's failure must not stop the others
            print(f"{t:5} FAILED ({type(e).__name__}); keeping tagged facts and defaults")
            r = await calibrate(t, False)
            r["error"] = type(e).__name__
        report.append(r)
        print(f"{t:5} accepted {sorted(r['accepted'])}  rejected {len(r['rejected'])}  "
              f"${r['cost_usd']:.4f}  {r['seconds']}s  sanitizer: {r['sanitizer']}")
        for x in r["rejected"]:
            print(f"      rejected {x['field']}: {x['reason']}")
    out = REPO_DIR / "evidence" / "calibration_report.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"generated": time.strftime("%Y-%m-%d %H:%M"), "companies": report}, indent=1), encoding="utf-8")
    print(f"total ${sum(r['cost_usd'] for r in report):.4f} -> {out.relative_to(REPO_DIR)}")


if __name__ == "__main__":
    asyncio.run(main())
