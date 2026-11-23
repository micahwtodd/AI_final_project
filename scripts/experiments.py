"""Experiments E1 to E4 and cost projections -> evidence/experiments.json (shown on the Experiments page).

E1  Solo versus Team on ten fixed questions (data/test/questions.json): engine facts present (marked in code),
    whether two differing views reached the learner, tokens, cost, latency. The ten answer pairs are saved for
    a reader to judge side by side.
E2  Team routing (Vera picks one or two specialists) versus asking every specialist, same ten questions.
E3  Calibration (Seamore reading the 10-K) with targeted retrieval (k=4 chunks per search) versus a large read
    (16 chunks per search), two companies: which profile fields changed, tokens and cost.
E4  Stable-prefix prompt caching on versus off (a random line at the start of the instructions breaks the
    cacheable prefix after the tool definitions; the provider still caches the tool definitions themselves, so
    "off" is a partial break), Solo mode on the ten questions: cached tokens, cost and latency.
Projections: cost per session, per learner per month, at 100 and 10,000 learners, one-time calibration per
company, the same workload priced on the two larger course models, and the cap as the maximum spend.

Every token count is the provider-reported usage. Costs use backend/pricing.py.
Run:  python scripts/experiments.py            (all; about 15 to 25 minutes, well under $2)
      python scripts/experiments.py E1 E4      (a subset; earlier results in the file are kept)
"""

from __future__ import annotations

import asyncio
import json
import re
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic_ai import Agent  # noqa: E402

from backend import agents, engine, examiner, filings, game, sam  # noqa: E402
from backend.calibration import get_tagged_facts  # noqa: E402
from backend.env import MODEL_NAME, redact  # noqa: E402
from backend.pricing import PRICES, cost_usd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "evidence" / "experiments.json"
QUESTIONS = json.loads((ROOT / "data" / "test" / "questions.json").read_text(encoding="utf-8"))
CONCURRENCY = 3
QUESTIONS_PER_SESSION = 8  # assumption for the projection: about one or two team questions a quarter
SESSIONS_PER_MONTH = 4

# ---------------------------------------------------------------- marking facts in code

NUM = re.compile(r"-?\$?\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> list[float]:
    out = []
    for m in NUM.findall(text.replace("−", "-")):
        try:
            out.append(float(m.replace("$", "").replace(",", "")))
        except ValueError:
            pass
    return out


def facts_for(q: dict, dash: dict) -> list[dict]:
    out = []
    for f in q["facts"]:
        if f["kind"] == "dash":
            out.append({**f, "target": dash[f["field"]]})
        elif f["kind"] == "dash_scaled":
            out.append({**f, "target": round(dash[f["field"]] * f["scale"], 3)})
        else:
            out.append(dict(f))
    return out


def has_fact(text: str, f: dict) -> bool:
    low = text.lower()
    if f["kind"] == "words":
        return any(w.lower() in low for w in f["any"])
    target = abs(f["target"])
    tol = max(0.03 * target, 0.06)
    return any(abs(abs(n) - target) <= tol for n in _numbers(text))


# ---------------------------------------------------------------- one question in a fresh session

def _fresh_session(mode: str) -> game.Session:
    s = game.new_game(QUESTIONS["scenario"]["ticker"], QUESTIONS["scenario"]["seed"], agent_mode=mode)
    s.budget_cap_usd = 5.0  # the experiment measures; the learner-facing cap stays $0.25
    return s


async def ask_once(mode: str, q: dict, note: str | None = None) -> dict:
    s = _fresh_session(mode)
    dash = engine.dashboard(s.state).model_dump()
    t0 = time.time()
    tok0, spend0 = dict(s.tokens), s.spend_usd
    try:
        await agents.ask(s, q["text"], asyncio.Queue(), lambda _s: None, note=note)
    except Exception as e:  # never let one failure stop the experiment
        return {"id": q["id"], "error": redact(f"{type(e).__name__}: {e}")[:200]}
    secs = time.time() - t0
    reply = next((m for m in reversed(s.chat) if m["role"] == "agent"), {})
    subs = reply.get("subs") or []
    shown = " ".join([reply.get("text", "")] + [x["text"] for x in subs])  # what reached the learner
    facts = facts_for(q, dash)
    got = [has_fact(shown, f) for f in facts]
    d = {k: s.tokens[k] - tok0.get(k, 0) for k in s.tokens}
    return {
        "id": q["id"], "question": q["text"], "mode": mode, "note": note, "seconds": round(secs, 1),
        "tokens": {"input": d["input"], "cached": d["cached"], "cache_write": d["cache_write"], "output": d["output"],
                   "requests": d["requests"]},
        "cost_usd": round(s.spend_usd - spend0, 6),
        "specialists": [x["agent"] for x in subs],
        "two_views": len({x["agent"] for x in subs}) >= 2,
        "facts": [{"name": f["name"], "target": f.get("target"), "found": g} for f, g in zip(facts, got)],
        "facts_found": sum(got), "facts_total": len(got),
        "reply": reply.get("text", ""), "specialist_answers": subs, "stopped": reply.get("stopped"),
    }


async def run_batch(mode: str, note: str | None = None) -> list[dict]:
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(q):
        async with sem:
            r = await ask_once(mode, q, note)
            print(f"  {mode}{' (all)' if note else ''} {q['id']}: {r.get('facts_found', '?')}/{r.get('facts_total', '?')} facts, "
                  f"${r.get('cost_usd', 0):.4f}, {r.get('seconds', 0)}s", flush=True)
            return r
    return await asyncio.gather(*(one(q) for q in QUESTIONS["questions"]))


def summarize(rows: list[dict]) -> dict:
    ok = [r for r in rows if "error" not in r]
    n = max(1, len(ok))
    tok = {k: sum(r["tokens"][k] for r in ok) for k in ("input", "cached", "cache_write", "output", "requests")}
    decisions = [r for r in ok if next(q for q in QUESTIONS["questions"] if q["id"] == r["id"])["decision"]]
    return {
        "questions": len(ok), "errors": len(rows) - len(ok),
        "facts_found": sum(r["facts_found"] for r in ok), "facts_total": sum(r["facts_total"] for r in ok),
        "two_views_on_decisions": sum(r["two_views"] for r in decisions), "decision_questions": len(decisions),
        "avg_cost_usd": round(sum(r["cost_usd"] for r in ok) / n, 6), "total_cost_usd": round(sum(r["cost_usd"] for r in ok), 6),
        "avg_seconds": round(sum(r["seconds"] for r in ok) / n, 1),
        "avg_tokens": {k: round(v / n) for k, v in tok.items()},
        "cached_share": round(tok["cached"] / tok["input"], 3) if tok["input"] else 0.0,
    }


# ---------------------------------------------------------------- E3: calibration retrieval size

def _val(v):
    """A profile field's value, whatever shape validate() returned it in."""
    if hasattr(v, "value"):
        return v.value
    return v.get("value") if isinstance(v, dict) else v


async def calibrate(ticker: str, large: bool) -> dict:
    orig = filings.search
    if large:
        filings.search = lambda t, q, k=4: orig(t, q, 16)  # a large read: 16 chunks per search
    try:
        t0 = time.time()
        findings, run = await sam.run_sam(ticker, cap_usd=1.0)
        secs = time.time() - t0
    finally:
        filings.search = orig
    accepted, rejected = sam.validate(findings, run, get_tagged_facts(ticker))
    return {"ticker": ticker, "variant": "large read (16 chunks per search)" if large else "targeted (k=4)",
            "seconds": round(secs, 1), "searches": run.searches, "chunks_read": len(run.retrieved),
            "tokens": {k: run.tokens[k] for k in ("input", "cached", "cache_write", "output", "requests")},
            "cost_usd": round(run.spend_usd, 6),
            "accepted": {k: _val(v) for k, v in accepted.items()},
            "rejected": len(rejected)}


async def e3() -> dict:
    rows = []
    for t in ("JXN", "LNC"):
        for large in (False, True):
            r = await calibrate(t, large)
            print(f"  E3 {t} {r['variant']}: {len(r['accepted'])} fields, ${r['cost_usd']:.4f}, {r['seconds']}s", flush=True)
            rows.append(r)
    changed = {}
    for t in ("JXN", "LNC"):
        a, b = [r["accepted"] for r in rows if r["ticker"] == t]
        diff = {}
        for k in sorted(set(a) | set(b)):
            va, vb = a.get(k), b.get(k)
            if va is None or vb is None or abs(va - vb) > 1e-9 * max(1.0, abs(va)):  # values only, not the quoted wording
                diff[k] = {"targeted": va, "large": vb}
        changed[t] = diff
    return {"runs": rows, "fields_changed": changed,
            "note": "Compared by value; the citation wording can differ between runs without the number changing."}


# ---------------------------------------------------------------- E4: caching off (prefix broken by a random line)

async def e4_off() -> list[dict]:
    real = agents.get_agent

    def uncached(kind: str):
        a = Agent(agents.make_model(), deps_type=agents.Deps, output_type=agents.AgentReply,
                  instructions=f"[run {secrets.token_hex(8)}]\n" + agents.load_prompt(agents.PROMPT_FILES[kind]),
                  retries=1, name=kind)
        agents.register_tools(a, agents.TOOLSETS[kind])
        return a
    agents.get_agent = uncached
    try:
        out = []
        for q in QUESTIONS["questions"]:  # one at a time, so nothing else warms a cache
            r = await ask_once("solo", q)
            print(f"  E4 off {q['id']}: cached {r.get('tokens', {}).get('cached', 0)}, ${r.get('cost_usd', 0):.4f}", flush=True)
            out.append(r)
        return out
    finally:
        agents.get_agent = real


async def e4_on() -> list[dict]:
    out = []
    for q in QUESTIONS["questions"]:
        r = await ask_once("solo", q)
        print(f"  E4 on {q['id']}: cached {r.get('tokens', {}).get('cached', 0)}, ${r.get('cost_usd', 0):.4f}", flush=True)
        out.append(r)
    return out


# ---------------------------------------------------------------- the examiner's cost per session

async def examiner_session() -> dict:
    s = game.new_game("JXN", 409, demo=True)
    s.budget_cap_usd = 5.0
    tok0 = dict(s.tokens)
    for q in range(1, engine.n_quarters() + 1):
        game.advance(s)
        card = engine.card_for(q)
        r = await game.explain(s, card.sample_answer)
        if not r.get("final"):
            await game.explain(s, "", not_sure=True)
    d = {k: s.tokens[k] - tok0.get(k, 0) for k in ("input", "cached", "cache_write", "output", "requests")}
    return {"tokens": d, "cost_usd": round(s.spend_usd, 6), "quarters": engine.n_quarters()}


def price(tokens: dict, model: str) -> float:
    return cost_usd(tokens["input"], tokens["output"], tokens.get("cached", 0), tokens.get("cache_write", 0), model)


def projections(res: dict) -> dict:
    team = res["E1"]["team_summary"]["avg_tokens"]
    exam = res["examiner"]["tokens"]
    per_session = {k: team[k] * QUESTIONS_PER_SESSION + exam[k] for k in ("input", "cached", "cache_write", "output", "requests")}
    calib = [r for r in res["E3"]["runs"] if r["variant"].startswith("targeted")]
    calib_cost = sum(r["cost_usd"] for r in calib) / max(1, len(calib))
    models = {}
    for m in PRICES:
        c = price(per_session, m)
        models[m] = {"per_session": round(c, 5), "per_learner_month": round(c * SESSIONS_PER_MONTH, 4),
                     "learners_100_month": round(c * SESSIONS_PER_MONTH * 100, 2),
                     "learners_10000_month": round(c * SESSIONS_PER_MONTH * 10_000, 2)}
    cap = 0.25
    return {
        "assumptions": {"team_questions_per_session": QUESTIONS_PER_SESSION, "examiner_calls_per_session": engine.n_quarters(),
                        "sessions_per_learner_month": SESSIONS_PER_MONTH, "model_used": MODEL_NAME,
                        "note": "Per-session tokens = average Team question (E1) x questions per session + one measured examiner session."},
        "tokens_per_session": per_session, "models": models,
        "calibration_one_time_per_company_usd": round(calib_cost, 4),
        "cap": {"per_session_usd": cap, "max_per_learner_month": cap * SESSIONS_PER_MONTH,
                "max_100_month": cap * SESSIONS_PER_MONTH * 100, "max_10000_month": cap * SESSIONS_PER_MONTH * 10_000},
    }


async def main(which: set[str]) -> None:
    res = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if not agents.ai_available():
        sys.exit("No API key found (or RISK_DESK_OFFLINE is set): the experiments need the model.")
    t0 = time.time()
    if "E1" in which:
        print("E1: Solo vs Team", flush=True)
        solo, team = await run_batch("solo"), await run_batch("team")
        res["E1"] = {"solo": solo, "team": team, "solo_summary": summarize(solo), "team_summary": summarize(team)}
    if "E2" in which:
        print("E2: Team routing vs asking every specialist", flush=True)
        allq = await run_batch("team", note="consult all three specialists (Morty, Bonnie and Swap Dogg), then synthesize.")
        res["E2"] = {"all": allq, "all_summary": summarize(allq),
                     "route_summary": res.get("E1", {}).get("team_summary")}
    if "E3" in which:
        print("E3: calibration retrieval size", flush=True)
        res["E3"] = await e3()
    if "E4" in which:
        print("E4: caching on vs off", flush=True)
        on = await e4_on()
        off = await e4_off()
        res["E4"] = {"on": on, "off": off, "on_summary": summarize(on), "off_summary": summarize(off)}
    if "E1" in which or "projections" in which or "examiner" not in res:
        print("Examiner session (for the projection)", flush=True)
        res["examiner"] = await examiner_session()
    if "E1" in res and "E3" in res:
        res["projections"] = projections(res)
    res["generated"] = time.strftime("%Y-%m-%d %H:%M")
    res["model"] = MODEL_NAME
    res["seconds"] = round(time.time() - t0, 1)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    spent = sum(x.get("total_cost_usd", 0) for k in ("E1", "E2", "E4") for x in
                [res.get(k, {}).get(s, {}) for s in ("solo_summary", "team_summary", "all_summary", "on_summary", "off_summary")] if x)
    print(f"done in {res['seconds']}s; wrote {OUT}; experiment model spend about ${spent:.4f} plus calibration and examiner", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    pick = {a.upper() for a in sys.argv[1:]} or {"E1", "E2", "E3", "E4"}
    asyncio.run(main(pick))
