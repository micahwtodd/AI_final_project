"""Risk Desk engine: deterministic, no model calls. The source of every number in the app.

All values are in $ billions unless a name says otherwise. Rates are decimals
inside the engine; shocks arrive in basis points and percent, as on the cards.
"""

from __future__ import annotations

import json
import random
from functools import lru_cache

from backend.env import REPO_DIR
from backend.models import (
    ASSET_BUCKETS, LIABILITY_BUCKETS, Action, Attribution, CompanyProfile, Dashboard,
    EventCard, GameState, QuarterRecord, ShockVector,
)

DATA_DIR = REPO_DIR / "data"
BP = 1e-4


# ---------------------------------------------------------------- data files

@lru_cache(maxsize=1)
def assumptions() -> dict:
    return json.loads((DATA_DIR / "assumptions.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def campaign() -> list[EventCard]:
    raw = json.loads((DATA_DIR / "events.json").read_text(encoding="utf-8"))
    return sorted((EventCard.model_validate(c) for c in raw["cards"]), key=lambda c: c.quarter)


def card_for(quarter: int) -> EventCard:
    return campaign()[quarter - 1]


def reload_data() -> None:
    assumptions.cache_clear()
    campaign.cache_clear()


# ---------------------------------------------------------------- helpers

def _ab(b: str) -> dict:
    return assumptions()["asset_buckets"][b]


def _lb(b: str) -> dict:
    return assumptions()["liability_buckets"][b]


def total_assets(s: GameState) -> float:
    return sum(s.assets.values())


def total_liabilities(s: GameState) -> float:
    return sum(s.liabilities.values())


def surplus(s: GameState) -> float:
    return total_assets(s) + s.uncollateralized_mtm - total_liabilities(s) - s.guarantee_value


def asset_dv01(s: GameState) -> float:
    """Asset value gained if rates fall 1bp, $bn."""
    return sum(s.assets[b] * _ab(b)["duration"] for b in ASSET_BUCKETS) * BP


def liability_dv01(s: GameState) -> float:
    """Liability value gained if rates fall 1bp (a loss to surplus), $bn. Includes guarantees."""
    g = assumptions()["guarantee"]
    return (sum(s.liabilities[b] * liab_duration(s, b) for b in LIABILITY_BUCKETS)
            + s.guarantee_exposure * g["k_rate"]) * BP


def liab_duration(s: GameState, b: str) -> float:
    return _lb(b)["duration"] * s.liability_duration_scale


def guarantee_equity_sensitivity(s: GameState) -> float:
    """Increase in guarantee value for a 100% equity fall, $bn."""
    return s.guarantee_exposure * assumptions()["guarantee"]["k_eq"]


def equity_holdings_exposure(s: GameState) -> float:
    """Loss on stocks and alternatives held for a 100% equity fall, $bn. Deliberately not hedged:
    insurers keep this equity risk premium to help fund future claims."""
    return s.assets["alts"] * s.alts_beta


def fx_enabled() -> bool:
    return bool(assumptions().get("fx", {}).get("enabled", True))


def foreign_assets(s: GameState) -> float:
    return s.foreign_share * sum(v for b, v in s.assets.items() if b != "cash")


def _hedge_on(a: Action, s: GameState) -> bool:
    return bool(abs(s.swap_dv01) > 0 or a.equity_hedge_pct or a.fx_hedge_pct)


def capital_requirement(s: GameState) -> float:
    g = assumptions()["guarantee"]
    req = sum(s.assets[b] * _ab(b)["capital_factor"] for b in ASSET_BUCKETS)
    req += sum(s.liabilities[b] * _lb(b)["capital_factor"] for b in LIABILITY_BUCKETS)
    req += s.guarantee_exposure * g["capital_factor"] * (1 - 0.5 * s.action.equity_hedge_pct / 100)
    return req


def stressed_outflow(s: GameState) -> float:
    m, so = assumptions()["market"], assumptions()["stressed_outflow"]
    run = m["stress_run_share"] * sum(s.liabilities[b] * _lb(b)["surrenderable"] for b in LIABILITY_BUCKETS)
    margin = abs(s.swap_dv01) * so["margin_rate_bp"] if s.action.collateralized else 0.0
    return run + margin


def liquid_assets_stressed(s: GameState) -> float:
    mult = assumptions()["stress_haircut_mult"]
    return s.assets["cash"] + s.assets["govt"] * (1 - _ab("govt")["haircut"] * mult)


# ---------------------------------------------------------------- build

def build_state(profile: CompanyProfile, seed: int) -> GameState:
    a = assumptions()
    A = profile.invested_assets_usd_bn
    assets = {b: A * profile.asset_mix.get(b, 0.0) for b in ASSET_BUCKETS}
    liab_total = A - profile.surplus_usd_bn - profile.guarantee_value_usd_bn
    liabilities = {b: liab_total * profile.liability_mix.get(b, 0.0) for b in LIABILITY_BUCKETS}

    weights = {b: a["asset_buckets"][b]["yield_weight"] for b in ASSET_BUCKETS}
    avg_w = sum(profile.asset_mix.get(b, 0.0) * weights[b] for b in ASSET_BUCKETS) or 1.0
    yields = {b: profile.net_investment_yield * weights[b] / avg_w for b in ASSET_BUCKETS}

    cash_pct = min(15.0, max(1.0, 100 * assets["cash"] / A))
    s = GameState(
        ticker=profile.ticker, seed=seed, assets=assets, liabilities=liabilities,
        annuity_account_value=liabilities["annuities"],
        guarantee_exposure=profile.guarantee_exposure_usd_bn,
        guarantee_value=profile.guarantee_value_usd_bn,
        market_rate=a["market"]["base_rate"], asset_yields=yields,
        portfolio_yield=profile.net_investment_yield, foreign_share=(profile.fx_exposed_share if profile.fx_exposed_share is not None else profile.foreign_share) if fx_enabled() else 0.0,
        action=Action(cash_buffer_pct=round(cash_pct, 1), collateralized=False, dealers=1),
        ig_aaa_share=profile.ig_aaa_share if profile.ig_aaa_share is not None else a["defaults_when_untagged"]["aaa_share_of_ig"],
        alts_beta=profile.alts_beta,
        ig_bbb_share=profile.ig_bbb_share if profile.ig_bbb_share is not None else a["defaults_when_untagged"]["bbb_share_of_ig"],
    )
    # scale liability durations so the starting unhedged gap is near the target (bounded)
    sg = a["starting_gap"]
    base_l = sum(liabilities[b] * a["liability_buckets"][b]["duration"] for b in LIABILITY_BUCKETS) * BP
    guar = s.guarantee_exposure * a["guarantee"]["k_rate"] * BP
    target_l = asset_dv01(s) + sg["target_years"] * A * BP - guar
    if base_l > 0:
        s.liability_duration_scale = round(min(sg["scale_max"], max(sg["scale_min"], target_l / base_l)), 4)
    # bring cash to the 1% floor if the profile has less
    return _set_cash(s, s.action.cash_buffer_pct)


# ---------------------------------------------------------------- dashboard

def dashboard(s: GameState) -> Dashboard:
    fl = assumptions()["floors"]
    A, L = total_assets(s), total_liabilities(s) + s.guarantee_value
    da = asset_dv01(s) / BP / A if A else 0.0
    dl = liability_dv01(s) / BP / L if L else 0.0
    net = asset_dv01(s) - liability_dv01(s) + s.swap_dv01  # surplus gain if rates fall 1bp
    gap = net / BP / A if A else 0.0
    cap = 100 * surplus(s) / capital_requirement(s)
    liq = 100 * liquid_assets_stressed(s) / max(stressed_outflow(s), 1e-9)
    eq = equity_holdings_exposure(s) + guarantee_equity_sensitivity(s) * (
        1 - s.action.equity_hedge_pct / 100 * (1 - s.hedges_lost_share))
    fx = foreign_assets(s) * (1 - s.action.fx_hedge_pct / 100 * (1 - s.hedges_lost_share))

    def band(v: float, red: float, amber: float) -> str:
        return "red" if v < red else "amber" if v < amber else "green"

    status = {
        "capital": band(cap, fl["capital_ratio_pct"], fl["capital_amber_pct"]),
        "liquidity": band(liq, fl["liquidity_ratio_pct"], fl["liquidity_amber_pct"]),
        "duration_gap": "green" if abs(gap) < 0.5 else "amber" if abs(gap) < 1.0 else "red",
    }
    return Dashboard(
        surplus_usd_bn=round(surplus(s), 3), assets_usd_bn=round(A, 2),
        liabilities_usd_bn=round(L, 2), asset_duration_years=round(da, 2),
        liability_duration_years=round(dl, 2), duration_gap_years=round(gap, 2),
        net_dv01_usd_mn=round(net * 1000, 1), liquidity_ratio_pct=round(liq, 1),
        capital_ratio_pct=round(cap, 1), net_equity_exposure_usd_bn=round(eq, 2),
        fx_exposure_usd_bn=round(fx, 2),
        counterparty_exposure_usd_bn=round(max(0.0, s.uncollateralized_mtm), 3),
        derivatives_mtm_usd_bn=round(s.uncollateralized_mtm, 3),
        asset_values={b: round(v, 2) for b, v in s.assets.items()},
        liability_values={**{b: round(v, 2) for b, v in s.liabilities.items()},
                          "guarantee": round(s.guarantee_value, 2)},
        status=status,
    )


# ---------------------------------------------------------------- trades

def _move(s: GameState, src: str, dst: str, amount: float) -> float:
    amount = max(0.0, min(amount, s.assets[src]))
    s.assets[src] -= amount
    s.assets[dst] += amount
    return amount


def _set_cash(s: GameState, pct: float) -> GameState:
    target = pct / 100 * total_assets(s)
    diff = target - s.assets["cash"]
    if diff > 0:
        diff -= _move(s, "govt", "cash", diff)
        _move(s, "ig_corp", "cash", diff)
    elif diff < 0:
        _move(s, "cash", "govt", -diff)
    return s


def quarterly_hedge_cost(s: GameState, a: Action) -> float:
    hc = assumptions()["hedge_costs_quarterly"]
    live = 1 - s.hedges_lost_share
    cost = abs(s.swap_dv01) * hc["swap_per_dv01"]
    cost += a.equity_hedge_pct / 100 * live * guarantee_equity_sensitivity(s) * hc["put_premium"]
    cost += a.fx_hedge_pct / 100 * live * foreign_assets(s) * hc["fx_forward"]
    if _hedge_on(a, s):
        A = total_assets(s)
        if a.dealers == 3:
            cost += A * hc["three_dealers"]
        if a.collateralized:
            cost += A * hc["collateral_ops"]
    return cost


def apply_action(state: GameState, action: Action, offers_prt: bool | None = None) -> GameState:
    """Trade the book to match the learner's signed ticket. Returns a new state."""
    a = assumptions()
    s = state.model_copy(deep=True)
    old = s.action

    # pension risk transfer deal (only when this quarter's card offers it)
    if offers_prt is None:
        offers_prt = 1 <= s.quarter <= 4 and card_for(s.quarter).offers_prt_deal
    if offers_prt and not s.prt_decided and action.accept_prt is not None:
        s.prt_decided = True
        if action.accept_prt:
            p = a["prt_deal"]
            size = p["size_share_of_invested"] * total_assets(s)
            s.liabilities["prt"] += size
            s.assets[p["assets_received_as"]] += size * (1 + p["premium_margin"])

    # credit shift: move below-IG and BBB into governments (or back, if negative)
    delta = (action.credit_shift_pct - old.credit_shift_pct) / 100
    if delta:
        bbb_val = s.assets["ig_corp"] * s.ig_bbb_share
        aaa_val = s.assets["ig_corp"] * s.ig_aaa_share
        a_val = s.assets["ig_corp"] - bbb_val  # AAA and A together; unchanged by the shift
        pool_hy = s.assets["below_ig"]
        pool = pool_hy + bbb_val
        if pool > 0 and delta > 0:
            amt = delta * pool
            _move(s, "below_ig", "govt", amt * pool_hy / pool)
            moved = _move(s, "ig_corp", "govt", amt * bbb_val / pool)
            bbb_val -= moved
        elif pool > 0:
            amt = min(-delta * pool, s.assets["govt"])
            s.assets["govt"] -= amt
            s.assets["below_ig"] += amt * pool_hy / pool
            s.assets["ig_corp"] += amt * bbb_val / pool
            bbb_val += amt * bbb_val / pool
        total_ig = a_val + bbb_val
        s.ig_bbb_share = bbb_val / total_ig if total_ig > 0 else 0.0
        s.ig_aaa_share = aaa_val / total_ig if total_ig > 0 else 0.0

    # cash buffer
    _set_cash(s, action.cash_buffer_pct)

    # collateral: switching it on settles what dealers owe us into cash
    if action.collateralized and not old.collateralized and s.uncollateralized_mtm:
        s.assets["cash"] += s.uncollateralized_mtm
        s.uncollateralized_mtm = 0.0

    # rate hedge sized to the current gap; signing a ticket re-establishes lost hedges
    s.action = action
    gap = asset_dv01(s) - liability_dv01(s)
    s.swap_dv01 = -action.rate_hedge_pct / 100 * gap
    s.hedges_lost_share = 0.0
    return s


def preview_action(state: GameState, action: Action) -> dict:
    after = apply_action(state, action)
    return {
        "before": dashboard(state).model_dump(),
        "after": dashboard(after).model_dump(),
        "hedge_cost_per_quarter_usd_bn": round(quarterly_hedge_cost(after, action), 4),
        "carry_per_quarter_usd_bn": round(_carry(after), 4),
    }


# ---------------------------------------------------------------- shocks

def realize_shock(card: EventCard, seed: int) -> tuple[float, ShockVector]:
    """actual = base x severity x (1 + small noise). Seeded by (seed, quarter): reproducible and path-independent."""
    a = assumptions()
    rng = random.Random(f"{seed}-{card.quarter}")
    sev = rng.choice(a["severity_levels"])
    base = card.base_shock.model_dump()
    out = {}
    for k, v in base.items():
        if isinstance(v, bool):
            out[k] = v
        elif k == "lapse_mult":
            out[k] = round(1 + (v - 1) * sev * (1 + rng.gauss(0, a["noise_sd"])), 3)
        else:
            out[k] = round(v * sev * (1 + rng.gauss(0, a["noise_sd"])), 2)
    if not fx_enabled():
        out["fx_pct"] = 0.0  # the random draw above still happens, so other moves are unchanged
    return sev, ShockVector(**out)


def _carry(s: GameState) -> float:
    c = assumptions()["carry"]
    income = sum(s.assets[b] * s.asset_yields[b] for b in ASSET_BUCKETS) / 4
    cost = c["liability_cost_ratio"] * s.portfolio_yield * total_liabilities(s) / 4
    expenses = c["expense_ratio_annual"] * total_assets(s) / 4
    return income - cost - expenses


def _raise_cash(s: GameState, need: float, stress: bool) -> float:
    """Pay `need` from cash, then sell assets in order at a haircut. Returns the haircut loss."""
    a = assumptions()
    mult = a["stress_haircut_mult"] if stress else 1.0
    loss = 0.0
    for b in a["sell_order"] + ["below_ig", "mortgage", "alts"]:
        if need <= 1e-12:
            break
        h = _ab(b)["haircut"] * mult if b != "cash" else 0.0
        proceeds_avail = s.assets[b] * (1 - h)
        take = min(need, proceeds_avail)
        sold = take / (1 - h) if h < 1 else 0.0
        s.assets[b] -= sold
        loss += sold - take
        need -= take
    return loss


def apply_shock(state: GameState, shock: ShockVector) -> tuple[GameState, Attribution]:
    """Apply one quarter's market moves to the book. Returns the new state and the P&L by cause."""
    a = assumptions()
    s = state.model_copy(deep=True)
    act = s.action
    live = 1 - s.hedges_lost_share
    dy, ds_ig, ds_hy = shock.rate_bp * BP, shock.ig_spread_bp * BP, shock.hy_spread_bp * BP
    eq = shock.equity_pct / 100
    att = dict(rates=0.0, credit_spreads=0.0, defaults=0.0, equity=0.0, fx=0.0,
               liquidity=0.0, counterparty=0.0, carry=0.0, hedge_cost=0.0)

    # carry and hedge costs are earned on the book held during the quarter
    carry = _carry(s)
    hcost = quarterly_hedge_cost(s, act)
    att["carry"], att["hedge_cost"] = carry, -hcost
    fx_base = foreign_assets(s)
    guar_eq_sens = guarantee_equity_sensitivity(s)
    a_share = max(0.0, 1 - s.ig_aaa_share - s.ig_bbb_share)

    # ---- assets
    spread_marks = {"aaa": 0.0, "a": 0.0, "bbb": 0.0, "mortgage": 0.0, "below_ig": 0.0}
    for b in ASSET_BUCKETS:
        mv, p = s.assets[b], _ab(b)
        d = p["duration"]
        r = mv * (-d * dy + 0.5 * (d * d / 100) * dy * dy)
        spread = ds_hy if b == "below_ig" else ds_ig if b in ("ig_corp", "mortgage") else 0.0
        cs = -mv * p["spread_duration"] * spread
        if b == "ig_corp":
            spread_marks["bbb"] += cs * s.ig_bbb_share
            spread_marks["aaa"] += cs * s.ig_aaa_share
            spread_marks["a"] += cs * a_share
        elif b == "mortgage":
            spread_marks["mortgage"] += cs
        elif b == "below_ig":
            spread_marks["below_ig"] += cs
        loss = 0.0
        if b == "ig_corp":
            # BBB lose the card's rate, A-rated a fraction of it, AAA nothing
            a_ratio = a["credit_tiers"]["a_default_ratio_to_bbb"]
            loss = mv * (s.ig_bbb_share + a_ratio * a_share) * shock.ig_loss_pct / 100
        elif b == "below_ig":
            loss = mv * shock.hy_default_pct / 100 * (1 - a["market"]["hy_recovery"])
        elif b == "mortgage":
            loss = mv * shock.mortgage_loss_pct / 100
        e = mv * (s.alts_beta if b == "alts" else p["beta"]) * eq
        fx = -mv * s.foreign_share * shock.fx_pct / 100 if b != "cash" else 0.0
        s.assets[b] = mv + r + cs - loss + e + fx
        att["rates"] += r
        att["credit_spreads"] += cs
        att["defaults"] -= loss
        att["equity"] += e
        att["fx"] += fx

    # ---- liabilities (a rise in value is a loss to surplus)
    for b in LIABILITY_BUCKETS:
        v, d = s.liabilities[b], liab_duration(s, b)
        dr = v * (-d * dy + 0.5 * (d * d / 100) * dy * dy)
        s.liabilities[b] = v + dr
        att["rates"] -= dr
    # liabilities absorb a share of the asset spread mark (buy-and-hold / matching adjustment)
    phi = a["liability_spread_offset"]
    offset = -sum(phi[k] * spread_marks[k] for k in spread_marks)  # liabilities fall when spreads widen
    L = total_liabilities(s)
    if L > 0 and offset:
        for b in LIABILITY_BUCKETS:
            s.liabilities[b] -= offset * s.liabilities[b] / L
        att["credit_spreads"] += offset

    # ---- variable annuity guarantees
    g = a["guarantee"]
    dg_eq = s.guarantee_exposure * g["k_eq"] * (-eq)
    dg_rate = s.guarantee_exposure * g["k_rate"] * (-dy)
    s.guarantee_value += dg_eq + dg_rate
    att["equity"] -= dg_eq
    att["rates"] -= dg_rate
    s.guarantee_exposure *= max(0.0, 1 + eq)  # account values fall with the market

    # ---- hedges (derivatives)
    swap_pnl = s.swap_dv01 * (-shock.rate_bp)
    put_pnl = act.equity_hedge_pct / 100 * live * guar_eq_sens * max(0.0, -eq)
    fx_pnl = act.fx_hedge_pct / 100 * live * fx_base * shock.fx_pct / 100
    att["rates"] += swap_pnl
    att["equity"] += put_pnl
    att["fx"] += fx_pnl
    hedge_mtm = swap_pnl + put_pnl + fx_pnl

    cash_need = hcost - carry
    if act.collateralized:
        cash_need -= hedge_mtm  # gains received in cash, losses paid as margin calls
    else:
        s.uncollateralized_mtm += hedge_mtm

    # ---- counterparty default
    if shock.dealer_default and _hedge_on(act, s):
        share = a["counterparty"]["largest_dealer_share"][str(act.dealers)]
        if act.collateralized:
            loss = a["counterparty"]["collateralized_loss_share"] * share * max(0.0, hedge_mtm)
            cash_need += loss
        else:
            loss = share * max(0.0, s.uncollateralized_mtm)
            s.uncollateralized_mtm -= loss
        att["counterparty"] -= loss
        s.hedges_lost_share = share

    # ---- surrenders (only the excess over normal lapses drains cash; normal lapses are refilled by new sales)
    m = a["market"]
    s.market_rate += dy
    excess_pp = max(0.0, s.market_rate - m["annuity_crediting_rate"]) * 100
    mult = shock.lapse_mult * (1 + m["lapse_rate_sensitivity"] * excess_pp) - 1
    if mult > 0:
        f = m["base_lapse_quarterly"] * mult
        for b in LIABILITY_BUCKETS:
            frac = f * _lb(b)["surrenderable"]
            if not frac:
                continue
            if b == "annuities":
                book = frac * s.annuity_account_value
                released = frac * s.liabilities[b]
                # surrender charges / market value adjustments recover part of a book-over-market loss
                payout = book - m["surrender_charge_offset"] * max(0.0, book - released)
                s.annuity_account_value -= book
            else:
                payout = released = frac * s.liabilities[b]
            s.liabilities[b] -= released
            att["liquidity"] -= payout - released  # paying book value for a liability marked lower
            cash_need += payout

    # ---- pay what is owed this quarter; forced sales lose a haircut
    if cash_need >= 0:
        att["liquidity"] -= _raise_cash(s, cash_need, shock.stress_liquidity)
    else:
        s.assets["cash"] += -cash_need

    att["total"] = sum(att.values())
    return s, Attribution(**{k: round(v, 4) for k, v in att.items()})


# ---------------------------------------------------------------- a full quarter

def play_quarter(state: GameState, action: Action | None) -> tuple[GameState, QuarterRecord]:
    """Sign the ticket (or do nothing if None), apply this quarter's shock, record the result."""
    card = card_for(state.quarter)
    start = state
    traded = apply_action(start, action) if action is not None else start
    sev, shock = realize_shock(card, state.seed)
    before = surplus(start)
    after_state, att = apply_shock(traded, shock)
    cf = counterfactual(start, card, state.seed)
    fl = assumptions()["floors"]
    d = dashboard(after_state)
    rec = QuarterRecord(
        quarter=card.quarter, card_id=card.id, severity=sev, shock=shock,
        action=traded.action, surplus_before=round(before, 4),
        surplus_after=round(surplus(after_state), 4), attribution=att,
        nothing_surplus_after=cf["nothing"]["surplus_after"],
        benchmark_surplus_after=cf["benchmark"]["surplus_after"],
        capital_breach=d.capital_ratio_pct < fl["capital_ratio_pct"],
        liquidity_breach=d.liquidity_ratio_pct < fl["liquidity_ratio_pct"],
        benchmark_capital_breach=cf["benchmark"]["capital_breach"],
        benchmark_liquidity_breach=cf["benchmark"]["liquidity_breach"],
    )
    rec.lever_gains = lever_gains(start, traded.action, card, shock, rec.surplus_after)
    after_state.history = [*start.history, rec]
    after_state.quarter = start.quarter + 1
    return after_state, rec


LEVERS = ["rate_hedge_pct", "credit_shift_pct", "equity_hedge_pct", "fx_hedge_pct", "cash_buffer_pct",
          "collateralized", "dealers"]


def lever_gains(start: GameState, action: Action, card: EventCard, shock: ShockVector, actual_after: float) -> dict:
    """For each lever, the surplus the learner would have had with only that lever at the benchmark's setting."""
    bench = card.benchmark_action
    out = {}
    for k in LEVERS:
        if getattr(action, k) == getattr(bench, k):
            continue
        alt = action.model_copy(update={k: getattr(bench, k)})
        after, _ = apply_shock(apply_action(start, alt, card.offers_prt_deal), shock)
        out[k] = round(surplus(after) - actual_after, 4)
    return out


def counterfactual(start_state: GameState, card: EventCard, seed: int) -> dict:
    """The same quarter and seed, rerun twice: doing nothing, and with the card's benchmark action."""
    _, shock = realize_shock(card, seed)
    out = {}
    for name, st in (("nothing", start_state),
                     ("benchmark", apply_action(start_state, card.benchmark_action, card.offers_prt_deal))):
        after, att = apply_shock(st, shock)
        d, fl = dashboard(after), assumptions()["floors"]
        out[name] = {"surplus_after": round(surplus(after), 4), "attribution": att.model_dump(),
                     "capital_breach": d.capital_ratio_pct < fl["capital_ratio_pct"],
                     "liquidity_breach": d.liquidity_ratio_pct < fl["liquidity_ratio_pct"]}
    return out


# ---------------------------------------------------------------- scoring and answer key

def quarter_score(rec: QuarterRecord) -> float:
    c = assumptions()["score"]
    you = rec.surplus_after - rec.surplus_before
    nothing = rec.nothing_surplus_after - rec.surplus_before
    bench = rec.benchmark_surplus_after - rec.surplus_before
    denom = bench - nothing
    tol = 0.005 * abs(rec.surplus_before)
    if denom > tol:
        ratio = (you - nothing) / denom
    else:
        # The benchmark did not beat doing nothing this quarter (e.g. a hedge gave up a small gain).
        # Both are defensible: matching the benchmark earns the band floor (0.9), matching the better
        # of the two earns full marks, and doing worse than both falls off over a band of a few percent
        # of surplus instead of dropping straight to zero.
        lo, hi = min(bench, nothing), max(bench, nothing)
        floor = c.get("fallback_band_floor", 0.9)
        scale = max(hi - lo, c.get("fallback_scale_pct_of_surplus", 0.03) * abs(rec.surplus_before), tol)
        if you >= hi - tol:
            ratio = 1.0 + max(0.0, you - hi) / scale
        elif you >= lo - tol:
            ratio = floor + (1.0 - floor) * (you - lo) / max(hi - lo, 1e-9)
        else:
            ratio = floor * max(0.0, 1.0 - (lo - you) / scale)
    return max(0.0, min(c["clip_max"], ratio))


def penalized_breaches(r: QuarterRecord) -> int:
    return int(r.capital_breach and not r.benchmark_capital_breach) + int(r.liquidity_breach and not r.benchmark_liquidity_breach)


def score(history: list[QuarterRecord]) -> dict:
    """Results score, 0 to 100, computed in code only."""
    if not history:
        return {"results_score": 0, "per_quarter": [], "penalties": 0}
    c = assumptions()["score"]
    per_q = [quarter_score(r) for r in history]
    # a breach the benchmark trades would also have suffered that quarter is not penalized
    penalties = c["breach_penalty"] * sum(penalized_breaches(r) for r in history)
    raw = 100 * sum(per_q) / len(per_q) - penalties
    return {"results_score": round(max(0.0, min(100.0, raw)), 1),
            "per_quarter": [round(100 * x, 1) for x in per_q], "penalties": penalties}


ATTRIBUTION_LABELS = {
    "rates": "interest rates", "credit_spreads": "credit spreads", "defaults": "defaults and credit losses",
    "equity": "equity markets", "fx": "foreign exchange", "liquidity": "surrenders and forced selling",
    "counterparty": "counterparty default", "carry": "carry (investment income less costs)",
    "hedge_cost": "hedge costs",
}


def answer_key(rec: QuarterRecord) -> dict:
    """What a correct explanation of this quarter must contain, built from the engine's own numbers."""
    comps = rec.attribution.components()
    market = {k: v for k, v in comps.items() if k not in ("carry", "hedge_cost")}
    ranked = sorted(market.items(), key=lambda kv: abs(kv[1]), reverse=True)
    main, second = ranked[0], ranked[1]
    you = rec.surplus_after - rec.surplus_before
    nothing = rec.nothing_surplus_after - rec.surplus_before
    bench = rec.benchmark_surplus_after - rec.surplus_before
    sh = rec.shock
    if sh.rate_bp and comps["rates"]:
        longer = "liabilities" if (sh.rate_bp < 0) == (comps["rates"] < 0) else "assets"
        shorter = "assets" if longer == "liabilities" else "liabilities"
        rate_why = (f"the {longer} are more rate-sensitive (longer duration) than the {shorter}, so "
                    f"{'falling' if sh.rate_bp < 0 else 'rising'} rates {'hurt' if comps['rates'] < 0 else 'helped'} surplus")
    else:
        rate_why = "rates barely moved"
    facts = {
        "rates": f"Rates moved {sh.rate_bp:+.0f}bp; {rate_why}: {comps['rates']:+.2f}bn from rates, including swaps and guarantees.",
        "credit_spreads": f"Investment-grade spreads moved {sh.ig_spread_bp:+.0f}bp and high-yield {sh.hy_spread_bp:+.0f}bp, lowering bond prices; liabilities absorb most but not all of that, so surplus changed by {comps['credit_spreads']:+.2f}bn.",
        "defaults": f"Defaults and credit losses cost {comps['defaults']:+.2f}bn: a permanent loss, unlike spread moves.",
        "equity": f"Stocks moved {sh.equity_pct:+.1f}%; alternatives (incl. stocks) and the stock-market guarantees changed surplus by {comps['equity']:+.2f}bn, net of any puts.",
        "fx": f"The dollar moved {sh.fx_pct:+.1f}%; foreign assets net of currency hedges changed by {comps['fx']:+.2f}bn.",
        "liquidity": f"Surrenders ran at {sh.lapse_mult:.2f}x normal; paying them and any forced selling cost {comps['liquidity']:+.2f}bn.",
        "counterparty": f"A dealer default cost {comps['counterparty']:+.2f}bn of hedge value owed without collateral.",
    }
    return {
        "main_driver": main[0],
        "main_driver_label": ATTRIBUTION_LABELS[main[0]],
        "main_driver_usd_bn": round(main[1], 3),
        "mechanism_facts": [facts[main[0]]],
        "second_factor": second[0],
        "second_factor_label": ATTRIBUTION_LABELS[second[0]],
        "second_factor_usd_bn": round(second[1], 3),
        "second_factor_fact": facts[second[0]],
        "hedge_effect_usd_bn": round(you - nothing, 3),
        "benchmark_change_usd_bn": round(bench - you, 3),
        "surplus_change_usd_bn": round(you, 3),
        "improvement_facts": improvement_facts(rec),
    }


LEVER_LABELS = {
    "rate_hedge_pct": "rate protection (swaps)", "credit_shift_pct": "moving risky bonds to government bonds",
    "equity_hedge_pct": "stock-market insurance (puts)", "fx_hedge_pct": "currency protection",
    "cash_buffer_pct": "cash on hand",
}


def _lever_setting(k: str, a: Action) -> str:
    v = getattr(a, k)
    if k == "collateralized":
        return "daily collateral on" if v else "no collateral"
    if k == "dealers":
        return f"{v} dealer{'s' if v == 3 else ''}"
    return f"{v:g}%"


def improvement_facts(rec: QuarterRecord) -> list[str]:
    """The levers that would have helped most this quarter, each moved alone to the benchmark's setting."""
    bench = card_for(rec.quarter).benchmark_action
    tol = max(0.005, 0.002 * abs(rec.surplus_before))
    helpful = sorted(((g, k) for k, g in rec.lever_gains.items() if g > tol), reverse=True)
    labels = {**LEVER_LABELS, "collateralized": "counterparty collateral", "dealers": "number of dealers"}
    out = [f"{labels[k]}: you had {_lever_setting(k, rec.action)}, the benchmark {_lever_setting(k, bench)}; "
           f"that change alone would have added {g:+.2f}bn" for g, k in helpful[:2]]
    return out or ["no single lever change would have helped much this quarter: your trades held up"]
