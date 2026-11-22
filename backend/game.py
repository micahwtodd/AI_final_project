"""Game sessions: the quarter loop the API drives. Deterministic; no model calls.

Phases per quarter:  position -> (advance) -> explain -> (explain) -> position of next quarter
After the fourth explain the session is "finished".
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from typing import Literal

from pydantic import BaseModel

from backend import audit, engine
from backend.calibration import DISPLAY_NAMES, load_profile
from backend.env import REPO_DIR, redact
from backend.models import Action, CompanyProfile, GameState, QuarterRecord

SESSIONS_DIR = REPO_DIR / "output" / "sessions"
DEFAULT_SEED = 409

Phase = Literal["position", "explain", "finished"]


class Session(BaseModel):
    id: str
    ticker: str
    seed: int
    agent_mode: Literal["solo", "team"] = "team"
    demo: bool = False
    created_at: float
    phase: Phase = "position"
    start_state: GameState  # the book at the very start (for full-campaign comparisons)
    state: GameState  # the book at the start of the current quarter (after the last shock)
    pending: Action | None = None  # signed ticket for this quarter
    last_record: QuarterRecord | None = None
    explanations: dict[int, dict] = {}  # final explain-back result per quarter (presence = revealed)
    explain_attempts: dict[int, list[dict]] = {}  # each attempt: text, checks, follow_up, marker
    understanding: dict[int, dict] = {}  # Understanding points per quarter, summed in code
    timings: dict[str, float] = {}
    # AI usage and budget (Project 3)
    budget_cap_usd: float = 0.25
    spend_usd: float = 0.0
    tokens: dict[str, int] = {"input": 0, "cached": 0, "cache_write": 0, "output": 0, "reasoning": 0, "requests": 0}
    by_agent: dict[str, dict] = {}
    chat: list[dict] = []  # transcript for display (the model's memory is kept in agents.py)
    proposed_ticket: dict | None = None


_SESSIONS: dict[str, Session] = {}
_LOCK = threading.Lock()


class GameError(Exception):
    """A request that does not fit the current phase (returned to the client as 409)."""


# ---------------------------------------------------------------- persistence

def _save(s: Session) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    (SESSIONS_DIR / f"{s.id}.json").write_text(s.model_dump_json(indent=1), encoding="utf-8")


def get(session_id: str) -> Session:
    with _LOCK:
        s = _SESSIONS.get(session_id)
        if s is None:
            path = SESSIONS_DIR / f"{session_id}.json"
            if not path.is_file():
                raise KeyError(session_id)
            s = Session.model_validate_json(path.read_text(encoding="utf-8"))
            _SESSIONS[session_id] = s
        return s


# ---------------------------------------------------------------- views

MOVE_LABELS = [
    ("rate_bp", "Interest rates", "bp"), ("ig_spread_bp", "Investment-grade spreads", "bp"),
    ("hy_spread_bp", "High-yield spreads", "bp"), ("equity_pct", "Stock market", "%"),
    ("fx_pct", "US dollar", "%"), ("lapse_mult", "Surrenders vs normal", "x"),
    ("hy_default_pct", "High-yield defaults", "%"), ("ig_loss_pct", "BBB credit losses", "%"),
    ("mortgage_loss_pct", "Mortgage losses", "%"),
]


def market_moves(shock) -> list[dict]:
    out = []
    for key, label, unit in MOVE_LABELS:
        v = getattr(shock, key)
        if key == "lapse_mult" and abs(v - 1) < 1e-9:
            continue
        if key != "lapse_mult" and not v:
            continue
        out.append({"key": key, "label": label, "value": v, "unit": unit})
    if shock.stress_liquidity:
        out.append({"key": "stress_liquidity", "label": "Market liquidity", "value": None, "unit": "frozen: fire-sale prices"})
    if shock.dealer_default:
        out.append({"key": "dealer_default", "label": "Largest derivatives dealer", "value": None, "unit": "defaulted"})
    return out


def _public_card(quarter: int) -> dict | None:
    if not 1 <= quarter <= 4:
        return None
    c = engine.card_for(quarter)
    return {"quarter": c.quarter, "title": c.title, "era": c.era, "signal_text": c.signal_text,
            "offers_prt_deal": c.offers_prt_deal, "glossary_terms": c.glossary_terms}


def _profile_summary(p: CompanyProfile) -> dict:
    return {"ticker": p.ticker, "name": p.name, "fiscal_year": p.fiscal_year,
            "invested_assets_usd_bn": p.invested_assets_usd_bn, "surplus_usd_bn": p.surplus_usd_bn,
            "equity_to_assets": p.equity_to_assets, "asset_mix": p.asset_mix,
            "liability_mix": p.liability_mix, "guarantee_exposure_usd_bn": p.guarantee_exposure_usd_bn,
            "separate_account_assets_usd_bn": p.separate_account_assets_usd_bn,
            "accession": p.accession, "foreign_share": p.foreign_share,
            "dossier": dossier(p), "reference": {k: v.model_dump() for k, v in p.reference.items()},
            "rejections": p.rejections, "sanitizer": p.sanitizer,
            "dashboard": engine.dashboard(engine.build_state(p, DEFAULT_SEED)).model_dump()}


DOSSIER_FIELDS = [
    ("invested_assets", "Invested assets (incl. cash)", "bn"), ("surplus", "Surplus (equity excl. AOCI)", "bn"),
    ("total_equity", "Stockholders' equity", "bn"), ("aoci", "AOCI (unrealized gains/losses)", "bn"),
    ("bonds_afs", "Fixed maturities (AFS)", "bn"), ("mortgage_loans", "Mortgage loans", "bn"),
    ("other_invested", "Other invested assets", "bn"), ("equity_securities", "Stocks held", "bn"),
    ("cash", "Cash and equivalents", "bn"), ("govt_share_of_bonds", "Government share of bonds", "pct"),
    ("below_ig_share_of_bonds", "Below-investment-grade share of bonds", "pct"),
    ("bbb_share_of_bonds", "BBB share of bonds", "pct"), ("ig_bbb_share", "BBB share of IG corporates", "pct"),
    ("policyholder_account_balances", "Policyholder account balances", "bn"),
    ("future_policy_benefits", "Future policy benefits", "bn"), ("mrb_net", "Net market risk benefits", "bn"),
    ("separate_account_assets", "Separate-account assets", "bn"), ("guaranteed_share_of_sa", "Guaranteed share of separate accounts", "pct"),
    ("foreign_share", "Foreign share", "pct"), ("fx_exposed_share", "Currency-exposed share of assets", "pct"),
    ("life_share_of_fpb", "Life share of future policy benefits", "pct"),
    ("net_investment_yield", "Net investment yield", "pct"),
]


def dossier(p: CompanyProfile) -> list[dict]:
    rows = []
    for key, label, unit in DOSSIER_FIELDS:
        fs = p.fields.get(key)
        if fs is None or fs.value is None:
            continue
        rows.append({"key": key, "label": label, "unit": unit, "value": fs.value, "source": fs.source,
                     "citation": fs.citation, "note": fs.note})
    return rows


def view(s: Session) -> dict:
    return {
        "id": s.id, "ticker": s.ticker, "company": DISPLAY_NAMES.get(s.ticker, s.ticker),
        "seed": s.seed, "agent_mode": s.agent_mode, "demo": s.demo,
        "quarter": min(s.state.quarter, 4) if s.phase != "explain" else s.state.quarter - 1,
        "phase": s.phase,
        "card": _public_card(s.state.quarter) if s.phase == "position" else None,
        "dashboard": engine.dashboard(s.state).model_dump(),
        "action": s.state.action.model_dump(),
        "pending": s.pending.model_dump() if s.pending else None,
        "prt_decided": s.state.prt_decided,
        "history": [_history_row(r, s) for r in s.state.history],
        "start_surplus_usd_bn": round(engine.surplus(s.start_state), 3),
        "usage": usage_view(s),
        "chat": s.chat[-40:],
    }


def usage_view(s: Session) -> dict:
    return {"spend_usd": round(s.spend_usd, 6), "budget_cap_usd": s.budget_cap_usd,
            "blocked": s.spend_usd >= s.budget_cap_usd, "tokens": s.tokens, "by_agent": s.by_agent}


def set_budget(s: Session, cap_usd: float) -> dict:
    s.budget_cap_usd = max(0.0, min(5.0, float(cap_usd)))
    _save(s)
    return usage_view(s)


def save(s: Session) -> None:
    _save(s)


def _history_row(r: QuarterRecord, s: Session) -> dict:
    revealed = r.quarter in s.explanations
    row = {"quarter": r.quarter, "card_id": r.card_id, "title": engine.card_for(r.quarter).title,
           "surplus_before": r.surplus_before, "surplus_after": r.surplus_after,
           "change": round(r.surplus_after - r.surplus_before, 3), "revealed": revealed}
    if revealed:
        row["score"] = round(100 * engine.quarter_score(r), 1)
    return row


# ---------------------------------------------------------------- actions

def new_game(ticker: str, seed: int | None = None, agent_mode: str = "team", demo: bool = False) -> Session:
    profile = load_profile(ticker)
    seed = DEFAULT_SEED if seed is None else int(seed)
    st = engine.build_state(profile, seed)
    s = Session(id=secrets.token_hex(6), ticker=profile.ticker, seed=seed, agent_mode=agent_mode,
                demo=demo, created_at=time.time(), start_state=st, state=st)
    s.timings["started"] = time.time()
    with _LOCK:
        _SESSIONS[s.id] = s
    _save(s)
    return s


def _require(s: Session, phase: Phase) -> None:
    if s.phase != phase:
        raise GameError(f"This step is not available now (game is in the '{s.phase}' phase).")


def preview(s: Session, action: Action) -> dict:
    _require(s, "position")
    return engine.preview_action(s.state, action)


def commit(s: Session, action: Action) -> dict:
    """The human approval step: the learner signs the trade ticket."""
    _require(s, "position")
    card = engine.card_for(s.state.quarter)
    if not card.offers_prt_deal:
        action = action.model_copy(update={"accept_prt": None})
    s.pending = action
    s.timings[f"q{s.state.quarter}_signed"] = time.time()
    _save(s)
    return {"view": view(s), "after": engine.dashboard(engine.apply_action(s.state, action)).model_dump()}


def advance(s: Session) -> dict:
    """End the quarter: apply the shock. Returns only what the learner may see before explaining."""
    _require(s, "position")
    q = s.state.quarter
    card = engine.card_for(q)
    before_dash = engine.dashboard(engine.apply_action(s.state, s.pending) if s.pending else s.state)
    new_state, rec = engine.play_quarter(s.state, s.pending)
    s.state, s.last_record, s.pending, s.phase = new_state, rec, None, "explain"
    s.timings[f"q{q}_shock"] = time.time()
    _save(s)
    return {
        "quarter": q, "title": card.title, "era": card.era, "headline": card.headline,
        "narrative": card.narrative, "severity": rec.severity, "seed": s.seed,
        "market_moves": market_moves(rec.shock),
        "surplus_before": rec.surplus_before, "surplus_after": rec.surplus_after,
        "surplus_change": round(rec.surplus_after - rec.surplus_before, 3),
        "dashboard_before": before_dash.model_dump(), "dashboard_after": engine.dashboard(new_state).model_dump(),
        "question": f"Surplus {'fell' if rec.surplus_after < rec.surplus_before else 'rose'} "
                    f"${abs(rec.surplus_after - rec.surplus_before):.2f} billion. Walk me through why.",
    }


MIN_WORDS = 15


async def explain(s: Session, text: str, not_sure: bool = False) -> dict:
    """Explain-back (plan 5.4). Attempt 1, an optional second try if the main driver was missed,
    or "I'm not sure" (a walkthrough, no points). The breakdown is revealed only at the end."""
    from backend import examiner

    _require(s, "explain")
    rec = s.last_record
    q = rec.quarter
    key = engine.answer_key(rec)
    attempts = s.explain_attempts.setdefault(q, [])
    text = (text or "").strip()[:2000]
    if not not_sure and len(text.split()) < MIN_WORDS:
        raise GameError(f"Please write at least {MIN_WORDS} words, or choose \"I'm not sure\".")

    mode = "walkthrough" if not_sure else "mark"
    attempt = len(attempts) + 1
    flagged = examiner.instruction_attempt(text) if text else False
    review, marker = None, "ai"
    try:
        review = await examiner.review_with_ai(s, rec, key, text, mode, attempt, attempts)
    except Exception as e:  # provider failure: fall back, never block the game
        audit.event(s.id, "examiner", q, "examiner", "error", {"message": redact(f"{type(e).__name__}: {e}")[:300]})
    if review is None:
        review, marker = examiner.review_with_keywords(key, text, mode, attempt), "keywords"
    review.instruction_attempt = review.instruction_attempt or flagged
    if review.instruction_attempt:
        audit.event(s.id, "examiner", q, "examiner", "blocked",
                    {"reason": "instruction_attempt", "message": "Learner text tried to instruct the grader; only the content was marked."})

    if not not_sure:
        attempts.append({"text": text, "checks": review.checks.model_dump(), "follow_up": review.follow_up,
                         "marker": marker, "instruction_attempt": review.instruction_attempt, "ts": time.time()})
    audit.event(s.id, "examiner", q, "examiner", "reply",
                {"mode": mode, "attempt": attempt, "checks": review.checks.model_dump(), "marker": marker,
                 "instruction_attempt": review.instruction_attempt})

    # a second try is allowed once, only when the main driver was missed
    if mode == "mark" and attempt == 1 and not review.checks.main_driver:
        _save(s)
        return {"final": False, "attempt": 1, "review": review.model_dump(), "marker": marker,
                "question": review.follow_up or "Look again at the market moves. Which one hit us hardest, and why?"}

    pts = examiner.quarter_points(attempts, not_sure)
    s.understanding[q] = {**pts, "not_sure": not_sure, "attempts": len(attempts)}
    s.explanations[q] = {"text": text, "not_sure": not_sure, "ts": time.time(), "review": review.model_dump(),
                         "marker": marker}
    s.phase = "finished" if s.state.quarter > 4 else "position"
    if s.phase == "finished":
        s.timings["finished"] = time.time()
    _save(s)
    return {"final": True, **reveal_payload(s, rec)}


def understanding_score(s: Session) -> dict:
    per_q = {q: round(v["points"], 1) for q, v in sorted(s.understanding.items())}
    avg = round(sum(per_q.values()) / len(per_q), 1) if per_q else 0.0
    return {"understanding_score": avg, "per_quarter": per_q}


def reveal_payload(s: Session, rec: QuarterRecord) -> dict:
    card = engine.card_for(rec.quarter)
    key = engine.answer_key(rec)
    exp = s.explanations.get(rec.quarter, {})
    you = rec.surplus_after - rec.surplus_before
    nothing = rec.nothing_surplus_after - rec.surplus_before
    bench = rec.benchmark_surplus_after - rec.surplus_before
    return {
        "quarter": rec.quarter,
        "attribution": [{"key": k, "label": engine.ATTRIBUTION_LABELS[k], "value": v}
                        for k, v in rec.attribution.components().items()],
        "total": rec.attribution.total,
        "comparison": {"you": round(you, 3), "nothing": round(nothing, 3), "benchmark": round(bench, 3)},
        "quarter_score": round(100 * engine.quarter_score(rec), 1),
        "main_driver": key["main_driver"], "second_factor": key["second_factor"],
        "debrief_text": quarter_debrief(rec),
        "lesson": card.lesson, "benchmark_action": card.benchmark_action.model_dump(exclude_none=True),
        "your_action": rec.action.model_dump(exclude_none=True), "source_note": card.source_note,
        "improvement_facts": key["improvement_facts"],
        "review": exp.get("review"), "marker": exp.get("marker"), "not_sure": exp.get("not_sure", False),
        "attempts": s.explain_attempts.get(rec.quarter, []),
        "understanding": s.understanding.get(rec.quarter),
        "finished": s.phase == "finished",
        "view": view(s),
    }


# ---------------------------------------------------------------- deterministic debrief text

def _bn(x: float) -> str:
    return f"${abs(x):.2f} billion"


def quarter_debrief(rec: QuarterRecord) -> list[str]:
    key = engine.answer_key(rec)
    comps = rec.attribution.components()
    you = rec.surplus_after - rec.surplus_before
    pct = 100 * you / rec.surplus_before if rec.surplus_before else 0.0
    hedge, gap = key["hedge_effect_usd_bn"], key["benchmark_change_usd_bn"]
    lines = [
        f"Surplus {'rose' if you >= 0 else 'fell'} {_bn(you)} this quarter ({pct:+.1f}% of starting surplus).",
        f"The biggest driver was {key['main_driver_label']} ({comps[key['main_driver']]:+.2f}bn). "
        + key["mechanism_facts"][0],
        f"The second-largest was {key['second_factor_label']} ({comps[key['second_factor']]:+.2f}bn).",
        f"Compared with doing nothing this quarter, your trades {'added' if hedge >= 0 else 'cost'} {_bn(hedge)}.",
        (f"The benchmark trades would have done {_bn(gap)} better." if gap > 0.005
         else f"You matched or beat the benchmark (by {_bn(-gap)})."),
    ]
    if rec.capital_breach:
        lines.append("Warning: the capital ratio ended below the 100% floor.")
    if rec.liquidity_breach:
        lines.append("Warning: the liquidity ratio ended below the 100% floor.")
    return lines


def _campaign(start: GameState, strategy: str) -> float:
    s = start
    for q in range(1, 5):
        s, _ = engine.play_quarter(s, None if strategy == "nothing" else engine.card_for(q).benchmark_action)
    return engine.surplus(s)


def debrief(s: Session) -> dict:
    if s.phase != "finished":
        raise GameError("The debrief is available after the fourth quarter.")
    hist = s.state.history
    start = engine.surplus(s.start_state)
    end = engine.surplus(s.state)
    nothing_end, bench_end = _campaign(s.start_state, "nothing"), _campaign(s.start_state, "benchmark")
    sc = engine.score(hist)
    best = max(hist, key=lambda r: engine.quarter_score(r))
    worst = min(hist, key=lambda r: engine.quarter_score(r))
    pct = lambda x: 100 * (x - start) / start  # noqa: E731
    text = [
        f"You ran {DISPLAY_NAMES.get(s.ticker, s.ticker)} through four quarters of market stress (seed {s.seed}).",
        f"Surplus went from ${start:.2f}bn to ${end:.2f}bn ({pct(end):+.1f}%).",
        f"Doing nothing all year would have ended at ${nothing_end:.2f}bn ({pct(nothing_end):+.1f}%); "
        f"the benchmark trades at ${bench_end:.2f}bn ({pct(bench_end):+.1f}%).",
        f"Your best quarter was Q{best.quarter} ({engine.card_for(best.quarter).title}); "
        f"the hardest was Q{worst.quarter} ({engine.card_for(worst.quarter).title}).",
    ]
    if sc["penalties"]:
        text.append(f"{sc['penalties']} points were deducted for ending quarters below the capital or liquidity floor.")
    return {
        **{f"understanding_{k}" if k == "per_quarter" else k: v for k, v in understanding_score(s).items()},
        "results_score": sc["results_score"], "per_quarter": sc["per_quarter"], "penalties": sc["penalties"],
        "start_surplus": round(start, 3), "end_surplus": round(end, 3),
        "nothing_end_surplus": round(nothing_end, 3), "benchmark_end_surplus": round(bench_end, 3),
        "text": text, "lessons": [{"quarter": q, "title": engine.card_for(q).title, "lesson": engine.card_for(q).lesson} for q in range(1, 5)],
        "minutes_played": round((s.timings.get("finished", time.time()) - s.timings.get("started", s.created_at)) / 60, 1),
        "history": [_history_row(r, s) for r in hist],
    }


def companies() -> list[dict]:
    from backend.calibration import load_all_profiles
    return [_profile_summary(p) for p in load_all_profiles()]


def dumps(obj) -> str:  # for debugging
    return json.dumps(obj, indent=1, default=str)
