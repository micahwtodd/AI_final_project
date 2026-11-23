"""Agent tools: small, typed reads of the engine. Every number an agent may quote comes from here.

These are plain functions over a GameState so they can be tested without a model.
No tool can change positions, scores, the budget or the quiz; propose_trade only
writes a ticket for the learner to sign. No tool sees this quarter's shock,
benchmark or answer key.
"""

from __future__ import annotations

import json
from functools import lru_cache

from backend import engine
from backend.env import REPO_DIR
from backend.models import ASSET_BUCKETS, ASSET_LABELS, LIABILITY_BUCKETS, LIABILITY_LABELS, Action, GameState

BN = "USD bn"


@lru_cache(maxsize=1)
def glossary() -> dict:
    raw = json.loads((REPO_DIR / "data" / "glossary.json").read_text(encoding="utf-8"))
    return raw["terms"]


def glossary_text() -> str:
    """The whole glossary as stable prompt text (placed early in prompts so it can be cached)."""
    return "\n".join(f"- {v['label']} [{k}]: {v['plain']}" for k, v in glossary().items())


def _r(x: float, n: int = 2) -> float:
    return round(float(x), n)


# ---------------------------------------------------------------- shared reads

def get_risk_dashboard(s: GameState) -> dict:
    d = engine.dashboard(s)
    return {
        "surplus_usd_bn": d.surplus_usd_bn, "invested_assets_usd_bn": d.assets_usd_bn,
        "capital_ratio_pct": d.capital_ratio_pct, "capital_floor_pct": 100,
        "liquidity_ratio_pct": d.liquidity_ratio_pct, "liquidity_floor_pct": 100,
        "duration_gap_years": d.duration_gap_years,
        "surplus_change_if_rates_fall_1bp_usd_mn": d.net_dv01_usd_mn,
        "equity_exposure_usd_bn_per_100pct_fall": d.net_equity_exposure_usd_bn,
        "uncollateralized_dealer_exposure_usd_bn": d.counterparty_exposure_usd_bn,
        "status": d.status, "quarter": min(s.quarter, engine.n_quarters()),
        "this_quarter_rule": ((engine.card_for(s.quarter).rule or {}).get("text") or "none: normal prices")
        if 1 <= s.quarter <= engine.n_quarters() else "none: normal prices",
    }


def get_past_quarter(s: GameState, n: int, revealed: set[int]) -> dict:
    rec = next((r for r in s.history if r.quarter == n), None)
    if rec is None:
        return {"error": f"Quarter {n} has not been played yet."}
    out = {"quarter": n, "event": engine.card_for(n).title,
           "surplus_before_usd_bn": rec.surplus_before, "surplus_after_usd_bn": rec.surplus_after,
           "surplus_change_usd_bn": _r(rec.surplus_after - rec.surplus_before, 3),
           "market_moves": {k: v for k, v in rec.shock.model_dump().items() if v not in (0, False)}}
    if n in revealed:
        out["change_by_cause_usd_bn"] = {k: _r(v, 3) for k, v in rec.attribution.components().items()}
    else:
        out["change_by_cause_usd_bn"] = "hidden until the learner explains the quarter to the CRO"
    return out


def get_news_signal(s: GameState) -> dict:
    if s.quarter > engine.n_quarters():
        return {"error": "The game is over."}
    c = engine.card_for(s.quarter)
    return {"quarter": c.quarter, "title": c.title, "wire": c.signal_text,
            "pension_deal_on_offer": c.offers_prt_deal and not s.prt_decided,
            "note": "A hint, not a forecast."}


def glossary_lookup(term: str) -> dict:
    g = glossary()
    key = term.strip().lower().replace(" ", "_").replace("-", "_")
    if key in g:
        return {"term": g[key]["label"], "definition": g[key]["plain"]}
    for k, v in g.items():
        if term.lower() in v["label"].lower() or term.lower() in k:
            return {"term": v["label"], "definition": v["plain"]}
    return {"error": f"'{term}' is not in the approved glossary.", "available": sorted(g)}


# ---------------------------------------------------------------- liabilities (Actuary)

def get_liability_summary(s: GameState) -> dict:
    m = engine.assumptions()["market"]
    d = engine.dashboard(s)
    return {
        "rate_mismatch_duration_gap_years": d.duration_gap_years,
        "asset_duration_years": d.asset_duration_years,
        "surplus_change_if_rates_fall_1bp_usd_mn": d.net_dv01_usd_mn,
        "rate_mismatch_note": ("Whole-company, net of bonds and hedges. A negative gap means liabilities are more "
                               "rate-sensitive than assets, so falling rates cut surplus and rising rates help it."),
        "buckets": [{"name": LIABILITY_LABELS[b], "value_usd_bn": _r(s.liabilities[b]),
                     "duration_years": _r(engine.liab_duration(s, b)),
                     "surrenderable_share": engine._lb(b)["surrenderable"]} for b in LIABILITY_BUCKETS],
        "annuity_account_value_usd_bn": _r(s.annuity_account_value),
        "annuity_market_value_usd_bn": _r(s.liabilities["annuities"]),
        "crediting_rate_pct": _r(100 * m["annuity_crediting_rate"]),
        "market_rate_pct": _r(100 * s.market_rate),
        "liability_duration_years": d.liability_duration_years,
    }


def get_surrender_projection(s: GameState, rate_rise_bp: float = 100, lapse_multiple: float = 1.5) -> dict:
    m = engine.assumptions()["market"]
    market = s.market_rate + rate_rise_bp / 1e4
    excess_pp = max(0.0, market - m["annuity_crediting_rate"]) * 100
    mult = max(0.0, lapse_multiple * (1 + m["lapse_rate_sensitivity"] * excess_pp) - 1)
    f = m["base_lapse_quarterly"] * mult
    outflow = sum(f * engine._lb(b)["surrenderable"] *
                  (s.annuity_account_value if b == "annuities" else s.liabilities[b]) for b in LIABILITY_BUCKETS)
    return {
        "scenario": f"rates +{rate_rise_bp:.0f}bp, surrenders {lapse_multiple:.1f}x normal",
        "extra_surrender_outflow_usd_bn": _r(outflow),
        "cash_on_hand_usd_bn": _r(s.assets["cash"]),
        "government_bonds_usd_bn": _r(s.assets["govt"]),
        "covered_by_cash": outflow <= s.assets["cash"],
        "rule": "Surrenders rise 50% for each 1 point market rates exceed the crediting rate.",
    }


def get_guarantee_exposure(s: GameState) -> dict:
    g = engine.assumptions()["guarantee"]
    h = s.action.equity_hedge_pct / 100 * (1 - s.hedges_lost_share)
    sens = engine.guarantee_equity_sensitivity(s)
    return {
        "guaranteed_account_value_usd_bn": _r(s.guarantee_exposure),
        "guarantee_liability_value_usd_bn": _r(s.guarantee_value),
        "guarantee_cost_if_stocks_fall_10pct_usd_bn": _r(sens * 0.10),
        "guarantee_rise_if_rates_fall_100bp_usd_bn": _r(s.guarantee_exposure * g["k_rate"] * 0.01),
        "equity_puts_hedge_pct": _r(100 * h, 1),
        "unhedged_guarantee_cost_if_stocks_fall_10pct_usd_bn": _r(sens * 0.10 * (1 - h)),
        "note": ("These are the guarantees only (gross). They are NOT the change in company surplus: when rates fall, "
                 "bonds gain too, and when stocks fall, the stocks and alternatives we own fall as well. For the "
                 "whole-company effect use the dashboard's net rate sensitivity (surplus change per 0.01% fall) or a stress test."),
    }


# ---------------------------------------------------------------- assets (Portfolio Manager)

def get_asset_summary(s: GameState) -> dict:
    return {
        "buckets": [{"name": ASSET_LABELS[b], "value_usd_bn": _r(s.assets[b]),
                     "duration_years": engine._ab(b)["duration"],
                     "yield_pct": _r(100 * s.asset_yields[b]),
                     "capital_factor_pct": _r(100 * engine._ab(b)["capital_factor"], 1)} for b in ASSET_BUCKETS],
        "portfolio_yield_pct": _r(100 * sum(s.assets[b] * s.asset_yields[b] for b in ASSET_BUCKETS) / engine.total_assets(s)),
        "asset_duration_years": engine.dashboard(s).asset_duration_years,
        "alternatives_stock_market_beta": s.alts_beta,
    }


def get_credit_exposure(s: GameState) -> dict:
    ig = s.assets["ig_corp"]
    a_share = max(0.0, 1 - s.ig_aaa_share - s.ig_bbb_share)
    off = engine.assumptions()["liability_spread_offset"]
    ig_sd, m_sd, hy_sd = (engine._ab(b)["spread_duration"] for b in ("ig_corp", "mortgage", "below_ig"))
    gross = (ig * ig_sd + s.assets["mortgage"] * m_sd) * 0.01 + s.assets["below_ig"] * hy_sd * 0.01
    net = (ig * ig_sd * (s.ig_aaa_share * (1 - off["aaa"]) + a_share * (1 - off["a"]) + s.ig_bbb_share * (1 - off["bbb"]))
           + s.assets["mortgage"] * m_sd * (1 - off["mortgage"])) * 0.01 + s.assets["below_ig"] * hy_sd * 0.01 * (1 - off["below_ig"])
    return {
        "aaa_usd_bn": _r(ig * s.ig_aaa_share), "a_usd_bn": _r(ig * a_share), "bbb_usd_bn": _r(ig * s.ig_bbb_share),
        "below_investment_grade_usd_bn": _r(s.assets["below_ig"]), "mortgage_loans_usd_bn": _r(s.assets["mortgage"]),
        "bond_price_loss_if_all_spreads_widen_100bp_usd_bn": _r(gross),
        "surplus_loss_after_liability_offset_usd_bn": _r(net),
        "default_rule": "AAA never defaults; A loses 15% of the BBB loss rate; junk bonds recover 40% on default.",
        "credit_shift_pct_now": s.action.credit_shift_pct,
    }


def get_liquidity_ladder(s: GameState) -> dict:
    a = engine.assumptions()
    mult = a["stress_haircut_mult"]
    rows = []
    for b in a["sell_order"] + ["below_ig", "mortgage", "alts"]:
        h = engine._ab(b)["haircut"] if b != "cash" else 0.0
        rows.append({"name": ASSET_LABELS[b], "value_usd_bn": _r(s.assets[b]),
                     "haircut_normal_pct": _r(100 * h, 1), "haircut_stressed_pct": _r(100 * h * mult, 1)})
    return {"sell_order": rows, "stressed_90_day_outflow_usd_bn": _r(engine.stressed_outflow(s)),
            "liquid_assets_after_stress_haircut_usd_bn": _r(engine.liquid_assets_stressed(s)),
            "liquidity_ratio_pct": engine.dashboard(s).liquidity_ratio_pct,
            "liquidity_ratio_definition": ("cash plus government bonds after stressed sale discounts, divided by the cash "
                                           "that could be needed in a 90-day stress (surrenders plus collateral calls). Only cash "
                                           "and government bonds count; the rest of the sell order is what we would sell next, "
                                           "at bigger discounts, if that ran out.")}


# ---------------------------------------------------------------- hedges (Trader)

def get_hedge_costs(s: GameState) -> dict:
    hc = engine.assumptions()["hedge_costs_quarterly"]
    gap = engine.asset_dv01(s) - engine.liability_dv01(s)
    rule = engine.card_for(s.quarter).rule if 1 <= s.quarter <= engine.n_quarters() else {}
    swap_m, put_m = rule.get("swap_cost_mult", 1.0), rule.get("put_cost_mult", 1.0)
    return {
        "this_quarter_rule": (rule.get("text") + " The costs below already include it.") if rule else "none: normal prices",
        "current": {"rate_hedge_pct": s.action.rate_hedge_pct, "equity_hedge_pct": s.action.equity_hedge_pct,
                    "collateralized": s.action.collateralized,
                    "dealers": s.action.dealers,
                    "hedge_cost_this_quarter_usd_bn": _r(engine.quarterly_hedge_cost(s, s.action), 4)},
        "cost_per_quarter_of_each_extra_10pct_usd_bn": {
            "rate_hedge": _r(abs(gap) * 0.10 * hc["swap_per_dv01"] * swap_m, 4),
            "equity_puts": _r(engine.guarantee_equity_sensitivity(s) * 0.10 * hc["put_premium"] * put_m, 4),
        },
        "three_dealers_extra_cost_usd_bn": _r(engine.total_assets(s) * hc["three_dealers"], 4),
        "daily_collateral_extra_cost_usd_bn": _r(engine.total_assets(s) * hc["collateral_ops"], 4),
        "unhedged_rate_gap_usd_mn_per_bp": _r(gap * 1000, 1),
    }


def preview_trade(s: GameState, action: Action) -> dict:
    p = engine.preview_action(s, action)
    keys = ["surplus_usd_bn", "capital_ratio_pct", "liquidity_ratio_pct", "duration_gap_years",
            "net_dv01_usd_mn", "net_equity_exposure_usd_bn"]
    return {"before": {k: p["before"][k] for k in keys}, "after": {k: p["after"][k] for k in keys},
            "hedge_cost_per_quarter_usd_bn": p["hedge_cost_per_quarter_usd_bn"],
            "carry_per_quarter_usd_bn": p["carry_per_quarter_usd_bn"]}


def stress_test(s: GameState, rate_bp: float = 0, ig_spread_bp: float = 0, equity_pct: float = 0, fx_pct: float = 0) -> dict:
    """What-if on the current book (no surrender or liquidity effects). Not a forecast of this quarter."""
    from backend.models import ShockVector
    _, att = engine.apply_shock(s, ShockVector(rate_bp=rate_bp, ig_spread_bp=ig_spread_bp,
                                               hy_spread_bp=ig_spread_bp * 2.5, equity_pct=equity_pct, fx_pct=fx_pct))
    hidden = ("carry", "hedge_cost") if engine.fx_enabled() else ("carry", "hedge_cost", "fx")
    comps = {k: _r(v, 3) for k, v in att.components().items() if k not in hidden}
    scenario = {"rate_bp": rate_bp, "ig_spread_bp": ig_spread_bp, "high_yield_spread_bp": ig_spread_bp * 2.5, "equity_pct": equity_pct}
    if engine.fx_enabled():
        scenario["usd_pct"] = fx_pct
    return {"scenario": scenario,
            "surplus_change_by_cause_usd_bn": comps, "surplus_change_usd_bn": _r(sum(comps.values()), 3),
            "note": "Hypothetical what-if on today's book. Not this quarter's shock."}


def validate_ticket(raw: dict, s: GameState) -> Action:
    """Fill unspecified levers from current positions, then validate ranges."""
    base = s.action.model_dump()
    base.update({k: v for k, v in raw.items() if v is not None and k in base})
    return Action.model_validate(base)
