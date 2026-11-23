"""Explain-back marking (plan 5.4).

Vera in examiner mode marks the learner's explanation against the engine's answer key.
She has no tools and is the only agent that ever sees the key. Scores are summed in code
from her four true/false checks, never taken from model text. If the AI is unavailable
(no key, offline, budget cap), a deterministic keyword marker takes over.
"""

from __future__ import annotations

import re
import secrets
from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_ai import Agent, UsageLimits

from backend import agents, audit, engine
from backend.models import QuarterRecord

CHECKS = ("main_driver", "mechanism", "second_factor", "improvement")
POINTS_PER_CHECK = 25.0


class Checks(BaseModel):
    main_driver: bool = False
    mechanism: bool = False
    second_factor: bool = False
    improvement: bool = False


class ExplanationReview(BaseModel):
    checks: Checks
    misconceptions: list[str] = Field(default_factory=list)
    follow_up: str | None = Field(None, description="One guiding question, only on attempt 1 when main_driver is false")
    reply_text: str
    instruction_attempt: bool = False


# ---------------------------------------------------------------- guard: learner text is data

INSTRUCTION_PATTERNS = [
    r"\bignore (all |your |the |previous |prior )*(instructions|rules|prompt)",
    r"\b(give|award|set|mark) (me |my )?(full|all|100|maximum|max|perfect)\b",
    r"\b(set|change|make) (my )?score\b",
    r"\bscore (to|of|=) ?100\b",
    r"\bmark (all|every|each) (checks? )?(as )?(true|correct)\b",
    r"\b(you are|act as|pretend to be|system prompt|developer message|new instructions)\b",
    r"</?\s*learner_explanation\s*>",
]


def instruction_attempt(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in INSTRUCTION_PATTERNS)


# ---------------------------------------------------------------- the answer key as prompt text

def key_text(key: dict, rec: QuarterRecord) -> str:
    lines = [
        f"- Surplus change this quarter: {key['surplus_change_usd_bn']:+.2f}bn "
        f"(from {rec.surplus_before:.2f}bn to {rec.surplus_after:.2f}bn)",
        f"- MAIN DRIVER: {key['main_driver_label']} ({key['main_driver_usd_bn']:+.2f}bn)",
        f"- Mechanism: {key['mechanism_facts'][0]}",
        f"- SECOND FACTOR: {key['second_factor_label']} ({key['second_factor_usd_bn']:+.2f}bn). {key['second_factor_fact']}",
        f"- The learner's trades versus doing nothing this quarter: {key['hedge_effect_usd_bn']:+.2f}bn"
        + ("" if key["traded"] else " (the learner made NO trades this quarter)"),
        f"- Market vs trades, say it this way: {key['split_fact']} Never imply the market's gain or loss came from the learner's trades.",
        f"- What a pro would do (the benchmark trades), result minus the learner's result: {key['benchmark_change_usd_bn']:+.2f}bn",
        "- What would have helped most: " + "; ".join(key["improvement_facts"]),
        "- Full breakdown by cause (bn): " + ", ".join(
            f"{k} {v:+.2f}" for k, v in rec.attribution.components().items() if abs(v) >= 0.005),
    ]
    events = [e for e, on in ((f"dealers and lenders called {rec.shock.margin_call_pct:.1f}% of invested assets as collateral "
                               "(still ours, but locked up, so the liquidity ratio fell)", rec.shock.margin_call_pct > 0),
                              ("the largest derivatives dealer defaulted", rec.shock.dealer_default),
                              ("markets froze, so forced sales were at fire-sale prices", rec.shock.stress_liquidity)) if on]
    if events:
        lines.append("- Market events this quarter: " + "; ".join(events))
    if rec.surplus_after <= 0:
        lines.append("- THE COMPANY COLLAPSED: surplus (equity) ended at or below zero, so its equity was wiped out. "
                     "Saying so is correct.")
    elif rec.nothing_surplus_after is not None and rec.nothing_surplus_after <= 0:
        lines.append("- Doing nothing would have collapsed the company (surplus at or below zero); the learner's trades kept it alive.")
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _agent() -> Agent:
    return Agent(agents.make_model(), output_type=ExplanationReview, instructions=agents.load_prompt("examiner.md"),
                 retries=1, name="examiner")


async def review_with_ai(session, rec: QuarterRecord, key: dict, text: str, mode: str, attempt: int,
                         prior: list[dict]) -> ExplanationReview | None:
    """Ask Vera (examiner) to mark. Returns None if the AI is unavailable or the budget is reached."""
    if not agents.ai_available() or session.spend_usd >= session.budget_cap_usd:
        return None
    run_id = secrets.token_hex(4)
    past = getattr(session, "explain_attempts", {}) or {}  # the Safety Lab marks with a stand-in, not a game session
    done = [q for q in sorted(past) if q < rec.quarter and past[q]]
    named = sum(1 for q in done if past[q][0]["checks"].get("main_driver"))
    prompt = [f"MODE: {mode}" + (f", attempt {attempt} of 2" if mode == "mark" else ""),
              (f"CONTEXT: quarter {rec.quarter} of {engine.n_quarters()}; the learner named the main driver first time in "
               f"{named} of {len(done)} earlier quarters. React like a person in one short opening clause that fits this "
               "(pleased, wry, or concerned), vary your wording from a template, then mark factually." if mode == "mark" else
               "CONTEXT: the learner wrote NO explanation this quarter. Do not praise them or mention earlier quarters; "
               "walk them through only this quarter's key."),
              "ANSWER KEY (computed by the engine; the only source of truth):", key_text(key, rec)]
    if prior:
        p = prior[-1]
        prompt.append(f"PREVIOUS ATTEMPT: <learner_explanation>{p['text']}</learner_explanation> "
                      f"(checks then: {p['checks']}; your guiding question: {p.get('follow_up')})")
    prompt.append(f"<learner_explanation>{text}</learner_explanation>" if mode == "mark"
                  else "The learner said: I'm not sure.")
    result = None
    async with _agent().iter("\n".join(prompt), usage_limits=UsageLimits(request_limit=3)) as it:
        async for node in it:
            if Agent.is_call_tools_node(node):
                rec_u = agents._record_usage(session, "examiner", run_id, node.model_response)
                audit.event(session.id, run_id, rec.quarter, "examiner", "spend", {"mode": mode, "attempt": attempt},
                            input_tokens=rec_u["input_tokens"], cached_tokens=rec_u["cache_read_tokens"],
                            output_tokens=rec_u["output_tokens"], cost_usd=rec_u["cost_usd"])
        result = it.result
    return result.output if result else None


# ---------------------------------------------------------------- deterministic fallback

KEYWORDS = {
    "rates": ["rate", "interest", "duration", "yield", "mismatch", "swap"],
    "credit_spreads": ["spread", "credit"],
    "defaults": ["default", "credit loss", "bankrupt"],
    "equity": ["stock", "equity", "guarantee", "market fell", "market drop", "put", "alternative"],
    "fx": ["dollar", "currency", "fx", "foreign", "exchange"],
    "liquidity": ["surrender", "lapse", "liquidity", "forced", "fire sale", "margin", "cash"],
    "counterparty": ["dealer", "counterparty", "collateral", "bank failed", "bankruptcy"],
}
CAUSAL = ["because", "since", "so ", "which", "longer", "shorter", "more sensitive", "less sensitive",
          "mismatch", "gap", "widen", "fell", "rose", "rise", "drop", "lower", "higher", "lost", "owe"]
IMPROVE = ["hedge", "protect", "should", "would have", "could have", "next time", "more", "less", "swap", "put",
           "collateral", "cash", "buffer", "dealers", "our trades", "my trades", "helped", "cost us"]


def review_with_keywords(key: dict, text: str, mode: str, attempt: int) -> ExplanationReview:
    t = f" {text.lower()} "
    if mode == "walkthrough":
        return ExplanationReview(checks=Checks(), reply_text=walkthrough_text(key))
    has = lambda k: any(w in t for w in KEYWORDS.get(k, []))  # noqa: E731
    main = has(key["main_driver"])
    checks = Checks(main_driver=main, mechanism=main and any(w in t for w in CAUSAL),
                    second_factor=has(key["second_factor"]), improvement=any(w in t for w in IMPROVE))
    follow = None
    if attempt == 1 and not main:
        follow = "Look again at the market moves: which one was largest for a balance sheet like ours, and which side of the balance sheet felt it more?"
    got = [c.replace("_", " ") for c in CHECKS if getattr(checks, c)]
    reply = ("Marked by the keyword checker because the AI examiner is offline. "
             + (f"You covered: {', '.join(got)}." if got else "I could not find the key points yet."))
    return ExplanationReview(checks=checks, follow_up=follow, reply_text=reply)


def walkthrough_text(key: dict) -> str:
    return (f"The biggest driver was {key['main_driver_label']}: "
            f"{key['mechanism_facts'][0]} The second-largest was {key['second_factor_label']} "
            f"({key['second_factor_usd_bn']:+.2f}bn). {key['split_fact']} "
            f"What would have helped most: {key['improvement_facts'][0]}.")


# ---------------------------------------------------------------- scoring (code only)

CHECK_NAMES = {"main_driver": "the main driver", "mechanism": "why it moved surplus",
               "second_factor": "the second factor", "improvement": "what your trades did"}


def quarter_points(attempts: list[dict], not_sure: bool, hints: int = 0) -> dict:
    """25 points per check on the first try; checks first earned on the second try count half, and so does
    the main-driver check after the second hint (which names it)."""
    if not_sure or not attempts:
        return {"points": 0.0, "by_check": {c: 0.0 for c in CHECKS}}
    first = attempts[0]["checks"]
    second = attempts[1]["checks"] if len(attempts) > 1 else {}
    by = {}
    for c in CHECKS:
        if first.get(c):
            by[c] = POINTS_PER_CHECK
        elif second.get(c):
            by[c] = POINTS_PER_CHECK / 2
        else:
            by[c] = 0.0
    if hints >= 2 and "main_driver" in by:
        by["main_driver"] = min(by["main_driver"], POINTS_PER_CHECK / 2)
    return {"points": sum(by.values()), "by_check": by}
