"""Game sessions: the quarter loop the API drives. Deterministic; no model calls.

Phases per quarter:  position -> (advance) -> explain -> (explain) -> position of next quarter
After the last quarter's explain (or once the company collapses) the session is "finished".
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from typing import Literal

from pydantic import BaseModel

from backend import achievements, audit, engine
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
    # learning measures (Project 8)
    quiz: dict[str, dict] = {}  # "pre" / "post" -> {answers, score, correct, total, by_concept, ts}
    confidence: dict[str, dict] = {}  # "pre" / "post" -> {C1: 1-5, ...}
    feedback: list[dict] = []
    proposed_ticket: dict | None = None
    overrides: dict[str, float] = {}  # learner edits to the game inputs (Advanced options)
    quiz_checked: dict[str, dict[str, str]] = {}  # 'pre'/'post' -> {question id: the choice that was checked}
    hints: dict[int, int] = {}  # hints taken per quarter (the second one names the main driver: that check counts half)
    predictions: dict[int, dict] = {}  # per quarter: {pick, answer, correct}; for fun, never scored


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
    ("margin_call_pct", "Collateral calls (% of assets)", "%"),
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
    if not 1 <= quarter <= engine.n_quarters():
        return None
    c = engine.card_for(quarter)
    return {"quarter": c.quarter, "title": c.title, "era": c.era, "signal_text": c.signal_text, "boss": c.boss,
            "offers_prt_deal": c.offers_prt_deal, "glossary_terms": c.glossary_terms}


def _profile_summary(p: CompanyProfile) -> dict:
    return {"ticker": p.ticker, "name": p.name, "fiscal_year": p.fiscal_year,
            "invested_assets_usd_bn": p.invested_assets_usd_bn, "surplus_usd_bn": p.surplus_usd_bn,
            "equity_to_assets": p.equity_to_assets, "asset_mix": p.asset_mix,
            "liability_mix": p.liability_mix, "guarantee_exposure_usd_bn": p.guarantee_exposure_usd_bn,
            "separate_account_assets_usd_bn": p.separate_account_assets_usd_bn,
            "accession": p.accession, "foreign_share": p.foreign_share,
            "dossier": dossier(p), "inputs": game_inputs(p), "reference": {k: v.model_dump() for k, v in p.reference.items()},
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
    ("life_share_of_fpb", "Life share of future policy benefits", "pct"),
    ("net_investment_yield", "Net investment yield", "pct"),
]


# ---------------------------------------------------------------- editable game inputs
# The figures the engine actually runs on (derived by Seamore and code from the 10-K). The learner may
# override them under "Advanced options"; mixes are re-scaled to sum to 100%.

INPUT_FIELDS: list[tuple[str, str, str, float, float]] = [  # key, label, unit, min, max
    ("invested_assets_usd_bn", "Invested assets", "bn", 1, 3000),
    ("surplus_usd_bn", "Surplus (equity excl. AOCI)", "bn", 0.1, 500),
    ("guarantee_exposure_usd_bn", "Account value with stock-market guarantees", "bn", 0, 3000),
    ("guarantee_value_usd_bn", "Net guarantee liability (negative = asset)", "bn", -200, 200),
    ("net_investment_yield", "Net investment yield", "pct", 0, 0.15),
    ("ig_aaa_share", "AAA share of investment-grade corporates", "pct", 0, 1),
    ("ig_bbb_share", "BBB share of investment-grade corporates", "pct", 0, 1),
    ("alts_beta", "Stock-market sensitivity of alternatives", "x", 0, 1.5),
]
MIX_LABELS = {"asset_mix": "Asset mix", "liability_mix": "Liability mix"}


def _effective(p: CompanyProfile, key: str) -> float:
    d = engine.assumptions()["defaults_when_untagged"]
    if key == "fx_exposed_share":
        return p.fx_exposed_share if p.fx_exposed_share is not None else p.foreign_share
    if key == "ig_aaa_share":
        return p.ig_aaa_share if p.ig_aaa_share is not None else d["aaa_share_of_ig"]
    if key == "ig_bbb_share":
        return p.ig_bbb_share if p.ig_bbb_share is not None else d["bbb_share_of_ig"]
    return float(getattr(p, key))


def game_inputs(p: CompanyProfile) -> list[dict]:
    """Editable inputs with their current values. Mix keys look like 'asset_mix.govt'."""
    from backend.models import ASSET_LABELS, LIABILITY_LABELS
    rows = [{"key": k, "label": lbl, "unit": u, "min": lo, "max": hi, "value": round(_effective(p, k), 6), "group": "Company"}
            for k, lbl, u, lo, hi in INPUT_FIELDS]
    for mix, labels in (("asset_mix", ASSET_LABELS), ("liability_mix", LIABILITY_LABELS)):
        for b, v in getattr(p, mix).items():
            rows.append({"key": f"{mix}.{b}", "label": labels.get(b, b), "unit": "pct", "min": 0, "max": 1,
                         "value": round(v, 6), "group": MIX_LABELS[mix]})
    return rows


def apply_overrides(p: CompanyProfile, overrides: dict[str, float] | None) -> CompanyProfile:
    """A copy of the profile with the learner's edits applied and checked. Raises GameError on bad input."""
    if not overrides:
        return p
    known = {r["key"]: r for r in game_inputs(p)}
    upd: dict = {}
    mixes = {"asset_mix": dict(p.asset_mix), "liability_mix": dict(p.liability_mix)}
    for key, val in overrides.items():
        if key not in known:
            raise GameError(f"Unknown input: {key}")
        r = known[key]
        try:
            v = float(val)
        except (TypeError, ValueError):
            raise GameError(f"{r['label']}: not a number")
        if not r["min"] <= v <= r["max"]:
            raise GameError(f"{r['label']} must be between {r['min']} and {r['max']}.")
        if "." in key:
            mix, b = key.split(".", 1)
            mixes[mix][b] = v
        else:
            upd[key] = v
    for mix, m in mixes.items():
        tot = sum(m.values())
        if tot <= 0:
            raise GameError(f"{MIX_LABELS[mix]} must add up to more than zero.")
        upd[mix] = {b: v / tot for b, v in m.items()}
    q = p.model_copy(update=upd)
    if _effective(q, "ig_aaa_share") + _effective(q, "ig_bbb_share") > 1:
        raise GameError("AAA and BBB shares of investment-grade corporates cannot add up to more than 100%.")
    if q.invested_assets_usd_bn - q.surplus_usd_bn - q.guarantee_value_usd_bn <= 0:
        raise GameError("Surplus is too large for these assets: liabilities would be zero or negative.")
    return q.model_copy(update={"equity_to_assets": q.surplus_usd_bn / q.invested_assets_usd_bn})


def preview_profile(ticker: str, overrides: dict[str, float] | None) -> dict:
    from backend.calibration import TICKERS
    if ticker not in TICKERS:
        raise FileNotFoundError(ticker)
    p = apply_overrides(load_profile(ticker), overrides)
    return {"dashboard": engine.dashboard(engine.build_state(p, DEFAULT_SEED)).model_dump(), "inputs": game_inputs(p)}


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
        "quarter": min(s.state.quarter, engine.n_quarters()) if s.phase != "explain" else s.state.quarter - 1,
        "n_quarters": engine.n_quarters(), "collapsed": engine.collapsed(s.state),
        "phase": s.phase,
        "card": _public_card(s.state.quarter) if s.phase == "position" else None,
        "dashboard": engine.dashboard(s.state).model_dump(),
        "action": s.state.action.model_dump(),
        "pending": s.pending.model_dump() if s.pending else None,
        "prt_decided": s.state.prt_decided,
        "history": [_history_row(r, s) for r in s.state.history],
        "start_surplus_usd_bn": round(engine.surplus(s.start_state), 3),
        "usage": usage_view(s),
        "chat": s.chat[-200:],
        "quiz_taken": sorted(s.quiz),
        "custom_inputs": sorted(s.overrides),
        "achievements": achievements.evaluate(s),
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

def new_game(ticker: str, seed: int | None = None, agent_mode: str = "team", demo: bool = False,
             overrides: dict[str, float] | None = None) -> Session:
    profile = apply_overrides(load_profile(ticker), overrides)
    seed = DEFAULT_SEED if seed is None else int(seed)
    st = engine.build_state(profile, seed)
    s = Session(id=secrets.token_hex(6), ticker=profile.ticker, seed=seed, agent_mode=agent_mode,
                demo=demo, created_at=time.time(), start_state=st, state=st, overrides=dict(overrides or {}))
    s.timings["started"] = time.time()
    with _LOCK:
        _SESSIONS[s.id] = s
    if s.overrides:
        audit.event(s.id, "setup", 0, "learner", "input_overrides", s.overrides)
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


PREDICTIONS = {"rates_up": "Rates jump", "rates_down": "Rates fall", "stocks_down": "Stocks crash",
               "credit": "Bonds default", "everything": "Everything at once"}


def advance(s: Session, prediction: str | None = None) -> dict:
    """End the quarter: apply the shock. Returns only what the learner may see before explaining."""
    _require(s, "position")
    q = s.state.quarter
    card = engine.card_for(q)
    before_dash = engine.dashboard(engine.apply_action(s.state, s.pending) if s.pending else s.state)
    new_state, rec = engine.play_quarter(s.state, s.pending)
    if prediction in PREDICTIONS and card.predict_answer:
        s.predictions[q] = {"pick": prediction, "answer": card.predict_answer, "correct": prediction == card.predict_answer}
    s.state, s.last_record, s.pending, s.phase = new_state, rec, None, "explain"
    s.timings[f"q{q}_shock"] = time.time()
    _save(s)
    change = round(rec.surplus_after - rec.surplus_before, 2)  # one rounded figure for the headline and the question
    return {
        "quarter": q, "title": card.title, "era": card.era, "headline": card.headline,
        "narrative": card.narrative, "severity": rec.severity, "seed": s.seed,
        "market_moves": market_moves(rec.shock),
        "surplus_before": rec.surplus_before, "surplus_after": rec.surplus_after,
        "surplus_change": change,
        "dashboard_before": before_dash.model_dump(), "dashboard_after": engine.dashboard(new_state).model_dump(),
        "sample_answer": card.sample_answer if s.demo else None,
        "real_world": card.real_world, "boss": card.boss,
        "prediction": ({**s.predictions[q], "pick_label": PREDICTIONS[s.predictions[q]["pick"]],
                        "answer_label": PREDICTIONS[s.predictions[q]["answer"]]} if q in s.predictions else None),
        "collapsed": rec.surplus_after <= 0, "nothing_collapsed": rec.nothing_surplus_after <= 0,
        "question": f"Surplus {'fell' if rec.surplus_after < rec.surplus_before else 'rose'} "
                    f"${abs(change):.2f} billion. Name the main two drivers, why they moved surplus, "
                    f"and what your trades did or could have done.",
    }


MIN_WORDS = 1  # any answer is accepted; the examiner marks what is there


def hint(s: Session) -> dict:
    """A hint ladder before answering: hint 1 says where to look; hint 2 names the main driver, and the
    main-driver check then counts half."""
    _require(s, "explain")
    rec = s.last_record
    q = rec.quarter
    key = engine.answer_key(rec)
    level = min(2, s.hints.get(q, 0) + 1)
    s.hints[q] = level
    _save(s)
    if level == 1:
        text = ("Start with the Capital Market Summary: which move was biggest compared with a normal quarter? "
                "Then ask which side of our balance sheet is more exposed to it: the bonds we own, or the long "
                "promises we made to policyholders.")
    else:
        verb = "helped" if key["main_driver_usd_bn"] >= 0 else "hurt"
        text = (f"The biggest effect came from {key['main_driver_label']} ({verb} surplus). Explain why it {verb}, "
                f"then name the second factor and what your trades did. (Using this hint, the main-driver check counts half.)")
    return {"level": level, "max": 2, "hint": text}


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
        raise GameError("Please write an answer, or choose \"I'm not sure\".")

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

    # a second try is allowed once, only when the main driver was missed; the reply must not give it away
    if mode == "mark" and attempt == 1 and not review.checks.main_driver:
        got = [examiner.CHECK_NAMES[c] for c, ok in review.checks.model_dump().items() if ok]
        review.reply_text = ((f"You did cover: {', '.join(got)}. " if got else "")
                             + "But you haven't named what moved surplus the most this quarter yet. One more try.")
    if mode == "mark" and attempt == 1 and not review.checks.main_driver:
        _save(s)
        return {"final": False, "attempt": 1, "review": review.model_dump(), "marker": marker,
                "question": review.follow_up or "Look again at the market moves. Which one hit us hardest, and why?"}

    pts = examiner.quarter_points(attempts, not_sure, s.hints.get(q, 0))
    s.understanding[q] = {**pts, "not_sure": not_sure, "attempts": len(attempts)}
    s.explanations[q] = {"text": text, "not_sure": not_sure, "ts": time.time(), "review": review.model_dump(),
                         "marker": marker}
    s.phase = "finished" if s.state.quarter > engine.n_quarters() or engine.collapsed(s.state) else "position"
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
                        for k, v in rec.attribution.components().items() if k != "fx" or engine.fx_enabled()],
        "total": rec.attribution.total,
        "comparison": {"you": round(you, 3), "nothing": round(nothing, 3), "benchmark": round(bench, 3)},
        "collapsed": {"you": rec.surplus_after <= 0, "nothing": rec.nothing_surplus_after <= 0,
                      "benchmark": (rec.benchmark_surplus_after or 1) <= 0},
        "surplus_before": rec.surplus_before, "lever_gains": rec.lever_gains,
        "title": card.title, "boss": card.boss, "n_quarters": engine.n_quarters(),
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
        "badges_new": achievements.new_badges(s, rec.quarter),
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
    gap = key["benchmark_change_usd_bn"]
    lines = [
        key["split_fact"].replace(_bn(you), f"{_bn(you)} ({pct:+.1f}%)", 1),
        f"The biggest driver was {key['main_driver_label']} ({comps[key['main_driver']]:+.2f}bn). "
        + key["mechanism_facts"][0],
        f"The second-largest was {key['second_factor_label']} ({comps[key['second_factor']]:+.2f}bn).",
        (f"A pro's trades would have done {_bn(gap)} better." if gap > 0.005
         else f"You matched or beat what a pro would do (by {_bn(-gap)})."),
    ]
    if rec.capital_breach:
        lines.append("Warning: the capital ratio ended below the 100% floor.")
    if rec.liquidity_breach:
        lines.append("Warning: the liquidity ratio ended below the 100% floor.")
    return lines


def _campaign(start: GameState, strategy: str) -> float:
    s = start
    for q in range(1, engine.n_quarters() + 1):
        s, _ = engine.play_quarter(s, None if strategy == "nothing" else engine.card_for(q).benchmark_action)
    return engine.surplus(s)


def debrief(s: Session) -> dict:
    if s.phase != "finished":
        raise GameError("The debrief is available when the game is over.")
    hist = s.state.history
    start = engine.surplus(s.start_state)
    end = engine.surplus(s.state)
    nothing_end, bench_end = _campaign(s.start_state, "nothing"), _campaign(s.start_state, "benchmark")
    sc = engine.score(hist)
    best = max(hist, key=lambda r: engine.quarter_score(r))
    worst = min(hist, key=lambda r: engine.quarter_score(r))
    pct = lambda x: 100 * (x - start) / start  # noqa: E731
    money = lambda x: f"{'−' if x < 0 else ''}${abs(x):.2f}bn"  # noqa: E731
    text = [
        (f"{DISPLAY_NAMES.get(s.ticker, s.ticker)} collapsed in Q{hist[-1].quarter}: its equity was wiped out (seed {s.seed})."
         if engine.collapsed(s.state) else
         f"You ran {DISPLAY_NAMES.get(s.ticker, s.ticker)} through {len(hist)} quarters of market stress (seed {s.seed})."),
        f"Surplus went from {money(start)} to {money(end)} ({pct(end):+.1f}%).",
        f"Doing nothing all game would have ended at {money(nothing_end)} ({pct(nothing_end):+.1f}%"
        f"{', a collapse' if nothing_end <= 0 else ''}); "
        f"a pro's trades at {money(bench_end)} ({pct(bench_end):+.1f}%).",
    ]
    if engine.quarter_score(best) > engine.quarter_score(worst) + 1e-9:
        text.append(f"Your best quarter was Q{best.quarter} ({engine.card_for(best.quarter).title}); "
                    f"the hardest was Q{worst.quarter} ({engine.card_for(worst.quarter).title}).")
    if sc["penalties"]:
        text.append(f"{sc['penalties']} points were deducted for ending quarters below the capital or liquidity floor.")
    facts = engine.answer_key(worst)["improvement_facts"]
    try_next = (f"In Q{worst.quarter} ({engine.card_for(worst.quarter).title}): {facts[0]}." if facts else None)
    return {
        **{f"understanding_{k}" if k == "per_quarter" else k: v for k, v in understanding_score(s).items()},
        "results_score": sc["results_score"], "per_quarter": sc["per_quarter"], "penalties": sc["penalties"],
        "start_surplus": round(start, 3), "end_surplus": round(end, 3),
        "nothing_end_surplus": round(nothing_end, 3), "benchmark_end_surplus": round(bench_end, 3),
        "collapsed": engine.collapsed(s.state), "n_quarters": engine.n_quarters(),
        "try_next": try_next,
        "predictions": {"made": len(s.predictions), "correct": sum(p["correct"] for p in s.predictions.values())},
        "text": text, "lessons": [{"quarter": r.quarter, "title": engine.card_for(r.quarter).title, "lesson": engine.card_for(r.quarter).lesson} for r in hist],
        "minutes_played": round((s.timings.get("finished", time.time()) - s.timings.get("started", s.created_at)) / 60, 1),
        "history": [_history_row(r, s) for r in hist],
        "before_after": before_after(s),
        "achievements": achievements.evaluate(s),
        "badge_catalog": [{"id": k, **v} for k, v in achievements.BADGES.items()],
        "report_card": achievements.report_card(s, sc["results_score"], understanding_score(s)["understanding_score"]),
    }


def companies() -> list[dict]:
    from backend.calibration import load_all_profiles
    return [_profile_summary(p) for p in load_all_profiles()]


def dumps(obj) -> str:  # for debugging
    return json.dumps(obj, indent=1, default=str)


# ---------------------------------------------------------------- quiz, confidence, feedback (Project 8)

QUIZ_PATH = REPO_DIR / "data" / "quiz.json"
FORM_FOR = {"pre": "A", "post": "B"}


def _quiz_data() -> dict:
    return json.loads(QUIZ_PATH.read_text(encoding="utf-8"))


def quiz_form(when: str) -> dict:
    """The questions for 'pre' (form A) or 'post' (form B), without the answers."""
    q = _quiz_data()
    form = FORM_FOR[when]
    return {"when": when, "form": form,
            "questions": [{k: v for k, v in item.items() if k not in ("answer", "explain")} for item in q["forms"][form]],
            "confidence": q["confidence"]}


def check_quiz_answer(s: Session, when: str, qid: str, choice: str) -> dict:
    """Reveal whether one answer is right, with a short explanation. The first checked choice is locked,
    so checking cannot be used to improve the saved score."""
    if when not in FORM_FOR:
        raise GameError("Unknown quiz.")
    if when in s.quiz:
        raise GameError("This quiz was already submitted.")
    item = next((i for i in _quiz_data()["forms"][FORM_FOR[when]] if i["id"] == qid), None)
    if item is None or choice not in item["options"]:
        raise GameError("Unknown question or option.")
    locked = s.quiz_checked.setdefault(when, {}).setdefault(qid, choice)
    _save(s)
    return {"id": qid, "choice": locked, "correct": locked == item["answer"], "answer": item["answer"],
            "explain": item.get("explain", "")}


def submit_quiz(s: Session, when: str, answers: dict[str, str], confidence: dict[str, int]) -> dict:
    """Marked in code. Each form can be taken once per session."""
    if when not in FORM_FOR:
        raise GameError("Unknown quiz.")
    if when in s.quiz:
        raise GameError("This quiz was already taken.")
    if when == "post" and s.phase != "finished":
        raise GameError("The after-game quiz opens once the game is over.")
    q = _quiz_data()
    items = q["forms"][FORM_FOR[when]]
    answers = {**answers, **s.quiz_checked.get(when, {})}  # a checked answer cannot be changed afterwards
    by_concept = {i["concept"]: answers.get(i["id"]) == i["answer"] for i in items}
    correct = sum(by_concept.values())
    conf = {c["id"]: int(confidence[c["id"]]) for c in q["confidence"] if c["id"] in confidence}
    if any(not 1 <= v <= 5 for v in conf.values()) or len(conf) != len(q["confidence"]):
        raise GameError(f"Please rate all {len(q['confidence'])} statements from 1 to 5.")
    s.quiz[when] = {"answers": {k: v for k, v in answers.items() if k in {i["id"] for i in items}},
                    "correct": correct, "total": len(items), "score": round(100 * correct / len(items), 1),
                    "by_concept": by_concept, "ts": time.time()}
    s.confidence[when] = conf
    s.timings[f"quiz_{when}"] = time.time()
    _save(s)
    return {"when": when, **{k: v for k, v in s.quiz[when].items() if k != "answers"},
            "confidence_avg": round(sum(conf.values()) / len(conf), 2),
            "answers_key": {i["id"]: i["answer"] for i in items} if when == "post" else None}


def add_feedback(s: Session, text: str) -> dict:
    text = (text or "").strip()[:2000]
    if not text:
        raise GameError("Feedback is empty.")
    s.feedback.append({"text": text, "ts": time.time()})
    _save(s)
    return {"ok": True, "count": len(s.feedback)}


def before_after(s: Session) -> dict:
    """The learning figures saved per session: quiz and confidence before and after, and time played."""
    q = _quiz_data()
    pre, post = s.quiz.get("pre"), s.quiz.get("post")
    cp, co = s.confidence.get("pre", {}), s.confidence.get("post", {})
    avg = lambda d: round(sum(d.values()) / len(d), 2) if d else None  # noqa: E731
    concepts = []
    for c in q["concepts"]:
        concepts.append({"concept": c, "pre": (pre or {}).get("by_concept", {}).get(c), "post": (post or {}).get("by_concept", {}).get(c)})
    items = []
    for c in q["confidence"]:
        items.append({"id": c["id"], "text": c["text"], "pre": cp.get(c["id"]), "post": co.get(c["id"])})
    start = s.timings.get("started", s.created_at)
    end = s.timings.get("finished", time.time())
    return {
        "quiz_pre": pre and {k: pre[k] for k in ("correct", "total", "score")},
        "quiz_post": post and {k: post[k] for k in ("correct", "total", "score")},
        "quiz_change_pts": round(post["score"] - pre["score"], 1) if pre and post else None,
        "confidence_pre_avg": avg(cp), "confidence_post_avg": avg(co),
        "confidence_change": round(avg(co) - avg(cp), 2) if cp and co else None,
        "concepts": concepts, "confidence_items": items,
        "minutes_played": round((end - start) / 60, 1),
    }


def summary(s: Session) -> dict:
    """Printable session summary: everything the impact section needs for one learner."""
    out = {"session_id": s.id, "company": DISPLAY_NAMES.get(s.ticker, s.ticker), "ticker": s.ticker, "seed": s.seed,
           "agent_mode": s.agent_mode, "phase": s.phase, "before_after": before_after(s),
           "usage": usage_view(s), "feedback": s.feedback}
    if s.phase == "finished":
        d = debrief(s)
        out.update({k: d[k] for k in ("results_score", "understanding_score", "understanding_per_quarter", "per_quarter",
                                       "start_surplus", "end_surplus", "nothing_end_surplus", "benchmark_end_surplus")})
    return out
