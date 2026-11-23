"""Badges, streaks and the year-end report card. Computed in code from the engine's records and the
examiner's checks, so they are deterministic and cannot be talked into existence through the chat."""

from __future__ import annotations

from backend import engine

BADGES: dict[str, dict] = {
    "called_it": {"name": "Called It", "icon": "🎯", "text": "Named the main driver of the quarter."},
    "full_marks": {"name": "Full Marks", "icon": "💯", "text": "Scored 100 on the Executive Summary in a quarter."},
    "better_than_nothing": {"name": "Better Than Nothing", "icon": "👍", "text": "Your trades beat doing nothing."},
    "beat_benchmark": {"name": "Beat the Pro", "icon": "🏆", "text": "Matched or beat what a pro would do."},
    "three_above_floor": {"name": "Three Above the Floor", "icon": "🛡️",
                          "text": "Three quarters in a row above the capital and liquidity floors."},
    "hat_trick": {"name": "Hat Trick", "icon": "🎩", "text": "Named the main driver three quarters in a row."},
    "boss_beaten": {"name": "Boss Beaten", "icon": "👑",
                    "text": "Final quarter: stayed above both floors and beat doing nothing."},
    "clean_sheet": {"name": "Clean Sheet", "icon": "🧼", "text": "Every quarter above both floors."},
}


def _above_floors(r) -> bool:
    return not (r.capital_breach or r.liquidity_breach)


def _called_main(s, q: int) -> bool:
    exp = s.explanations.get(q, {})
    if exp.get("not_sure"):
        return False
    return any(a["checks"].get("main_driver") for a in s.explain_attempts.get(q, []))


def evaluate(s) -> dict:
    """Badges earned so far (only quarters already explained and revealed) and current streaks."""
    revealed = [r for r in s.state.history if r.quarter in s.explanations]
    earned: list[dict] = []

    def award(bid: str, q: int) -> None:
        if not any(e["id"] == bid for e in earned):  # each badge once per game
            earned.append({"id": bid, "quarter": q, **BADGES[bid]})

    floor_run = explain_run = 0
    for r in revealed:
        q = r.quarter
        floor_run = floor_run + 1 if _above_floors(r) else 0
        explain_run = explain_run + 1 if _called_main(s, q) else 0
        if _called_main(s, q):
            award("called_it", q)
        if s.understanding.get(q, {}).get("points", 0) >= 99.95:
            award("full_marks", q)
        if r.surplus_after > (r.nothing_surplus_after or 0) + 0.005:
            award("better_than_nothing", q)
        if r.benchmark_surplus_after is not None and r.surplus_after >= r.benchmark_surplus_after - 0.005:
            award("beat_benchmark", q)
        if floor_run >= 3:
            award("three_above_floor", q)
        if explain_run >= 3:
            award("hat_trick", q)
        if q == engine.n_quarters() and _above_floors(r) and r.surplus_after > (r.nothing_surplus_after or 0) + 0.005:
            award("boss_beaten", q)
    if len(revealed) == engine.n_quarters() and all(_above_floors(r) for r in revealed):
        award("clean_sheet", engine.n_quarters())
    return {"earned": earned, "streaks": {"floor": floor_run, "explain": explain_run},
            "available": len(BADGES)}


def new_badges(s, quarter: int) -> list[dict]:
    return [b for b in evaluate(s)["earned"] if b["quarter"] == quarter]


# ---------------------------------------------------------------- year-end report card

GRADES = [(93, "A+"), (85, "A"), (78, "B+"), (70, "B"), (62, "C+"), (55, "C"), (45, "D")]


def grade_for(overall: float) -> str:
    return next((g for cut, g in GRADES if overall >= cut), "F")


def report_card(s, results: float, understanding: float) -> dict:
    """A letter grade (60% results, 40% Executive Summary, stored as "understanding") and a title that describes how you played."""
    hist = s.state.history
    overall = round(0.6 * results + 0.4 * understanding, 1)
    breaches = sum(r.capital_breach + r.liquidity_breach for r in hist)
    acts = [r.action for r in hist]
    n = max(1, len(acts))
    avg_hedge = sum((a.rate_hedge_pct / 1.2 + a.equity_hedge_pct) / 2 for a in acts) / n  # FX is switched off
    if results >= 85 and understanding >= 85:
        title, why = "Risk Whisperer", "Strong results and you could explain every one of them."
    elif breaches and avg_hedge < 25:
        title, why = "Cowboy Hedger", "You rode the market with little protection and got thrown below a floor."
    elif avg_hedge >= 70 and results < 70:
        title, why = "Fortress Builder", "So much protection that its cost ate the gains. Hedging is not free."
    elif breaches == 0 and results >= 70:
        title, why = "Steady Hand", "Never below a floor, and you kept most of what the year could have cost."
    elif understanding >= 80:
        title, why = "Sharp Explainer", "You read the market well; the trades can catch up with the thinking."
    elif breaches == 0:
        title, why = "Lucky Survivor", "You stayed above the floors, but left money on the table."
    else:
        title, why = "Rookie on the Rise", "A rough first year. Every risk manager has one."
    return {"grade": grade_for(overall), "overall": overall, "title": title, "why": why,
            "weights": {"results": 0.6, "understanding": 0.4}, "breaches": breaches,
            "avg_hedge_pct": round(avg_hedge, 1)}


__all__ = ["BADGES", "evaluate", "new_badges", "report_card", "grade_for", "engine"]
