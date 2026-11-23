"""Engine tests: accounting identities, hedge behaviour, reproducibility.

Run from the repo folder:  python -m pytest -q
"""

from __future__ import annotations

import pytest

from backend import engine
from backend.calibration import TICKERS, load_all_profiles, load_profile
from backend.models import Action, ShockVector

SEED = 409
PROFILES = load_all_profiles()


def fresh(ticker: str = "JXN"):
    return engine.build_state(load_profile(ticker), SEED)


def test_six_profiles_cached():
    assert [p.ticker for p in PROFILES] == TICKERS


@pytest.mark.parametrize("p", PROFILES, ids=lambda p: p.ticker)
def test_start_surplus_matches_profile(p):
    s = engine.build_state(p, SEED)
    assert engine.surplus(s) == pytest.approx(p.surplus_usd_bn, abs=0.02)


@pytest.mark.parametrize("p", PROFILES, ids=lambda p: p.ticker)
@pytest.mark.parametrize("strategy", ["nothing", "benchmark", "max", "uncollateralized"])
def test_attribution_sums_to_surplus_change_every_quarter(p, strategy):
    """Assets - liabilities = surplus after every step: each quarter's P&L by cause adds up exactly."""
    s = engine.build_state(p, SEED)
    for q in range(1, engine.n_quarters() + 1):
        card = engine.card_for(q)
        act = {
            "nothing": None,
            "benchmark": card.benchmark_action,
            "max": Action(rate_hedge_pct=120, credit_shift_pct=30, equity_hedge_pct=100, fx_hedge_pct=100,
                          cash_buffer_pct=15, collateralized=True, dealers=3, accept_prt=True),
            "uncollateralized": Action(rate_hedge_pct=100, equity_hedge_pct=100, fx_hedge_pct=100,
                                       collateralized=False, dealers=1, accept_prt=True),
        }[strategy]
        traded = engine.apply_action(s, act) if act else s
        before = engine.surplus(traded)
        _, shock = engine.realize_shock(card, SEED)
        after, att = engine.apply_shock(traded, shock)
        assert engine.surplus(after) - before == pytest.approx(att.total, abs=1e-3)
        assert sum(att.components().values()) == pytest.approx(att.total, abs=1e-3)
        assert all(v >= -1e-9 for v in after.assets.values()), "no negative asset buckets"
        s, _ = engine.play_quarter(s, act)


def test_trading_does_not_create_or_destroy_value_without_a_deal():
    s = fresh("MET")
    after = engine.apply_action(s, Action(rate_hedge_pct=80, credit_shift_pct=25, equity_hedge_pct=50,
                                          fx_hedge_pct=50, cash_buffer_pct=10, collateralized=True, dealers=3))
    assert engine.surplus(after) == pytest.approx(engine.surplus(s), abs=1e-9)
    assert engine.total_assets(after) == pytest.approx(engine.total_assets(s), abs=1e-9)


def test_zero_shock_gives_carry_only():
    s = fresh("PRU")
    after, att = engine.apply_shock(s, ShockVector())
    for k, v in att.components().items():
        if k != "carry":
            assert v == pytest.approx(0.0, abs=1e-9), k
    assert att.carry > 0
    assert engine.surplus(after) - engine.surplus(s) == pytest.approx(att.carry, abs=1e-3)


@pytest.mark.parametrize("p", PROFILES, ids=lambda p: p.ticker)
@pytest.mark.parametrize("bp", [100, -100])
def test_full_rate_hedge_neutralises_rates(p, bp):
    s = engine.build_state(p, SEED)
    _, unhedged = engine.apply_shock(s, ShockVector(rate_bp=bp))
    hedged_state = engine.apply_action(s, Action(rate_hedge_pct=100, cash_buffer_pct=s.action.cash_buffer_pct))
    assert engine.dashboard(hedged_state).net_dv01_usd_mn == pytest.approx(0.0, abs=1e-6)
    _, hedged = engine.apply_shock(hedged_state, ShockVector(rate_bp=bp))
    assert abs(hedged.rates) < 0.05 * abs(unhedged.rates) + 0.01  # only convexity is left


def test_full_fx_hedge_neutralises_fx():
    # FX is switched off in play (assumptions.json); the machinery is still tested with an explicit exposure
    s = fresh("MET").model_copy(update={"foreign_share": 0.1})
    _, unhedged = engine.apply_shock(s, ShockVector(fx_pct=10))
    _, hedged = engine.apply_shock(engine.apply_action(s, Action(fx_hedge_pct=100, cash_buffer_pct=4.5)),
                                   ShockVector(fx_pct=10))
    assert unhedged.fx < 0
    assert hedged.fx == pytest.approx(0.0, abs=1e-9)


def test_same_seed_same_result_and_different_seed_differs():
    def run(seed):
        s = engine.build_state(load_profile("LNC"), seed)
        for q in range(1, engine.n_quarters() + 1):
            s, _ = engine.play_quarter(s, engine.card_for(q).benchmark_action)
        return [r.model_dump() for r in s.history]

    assert run(SEED) == run(SEED)
    shocks = {tuple(engine.realize_shock(engine.card_for(1), seed)[1].model_dump().values()) for seed in range(20)}
    assert len(shocks) > 1


def test_shock_does_not_depend_on_play_path():
    card = engine.card_for(3)
    assert engine.realize_shock(card, SEED) == engine.realize_shock(card, SEED)


def test_collateral_and_more_dealers_cut_counterparty_loss():
    s = fresh("JXN")
    shock = ShockVector(rate_bp=-50, equity_pct=-10, dealer_default=True)
    losses = {}
    for collat, dealers in [(False, 1), (False, 3), (True, 1)]:
        st = engine.apply_action(s, Action(rate_hedge_pct=100, equity_hedge_pct=100, cash_buffer_pct=8,
                                           collateralized=collat, dealers=dealers))
        _, att = engine.apply_shock(st, shock)
        losses[(collat, dealers)] = -att.counterparty
    assert losses[(False, 1)] > losses[(False, 3)] > losses[(True, 1)] >= 0


def test_credit_shift_reduces_credit_losses():
    s = fresh("CRBG")
    shock = engine.card_for(4).base_shock  # the credit quarter
    _, base = engine.apply_shock(s, shock)
    _, shifted = engine.apply_shock(engine.apply_action(s, Action(credit_shift_pct=30, cash_buffer_pct=1)), shock)
    assert shifted.defaults > base.defaults
    assert shifted.credit_spreads > base.credit_spreads


def test_pension_deal_adds_premium_margin_and_long_liabilities():
    s = fresh("MET")
    s.quarter = 2
    took = engine.apply_action(s, Action(cash_buffer_pct=s.action.cash_buffer_pct, accept_prt=True), True)
    assert took.prt_decided and took.liabilities["prt"] > s.liabilities["prt"]
    assert engine.surplus(took) > engine.surplus(s)
    assert engine.dashboard(took).capital_ratio_pct < engine.dashboard(s).capital_ratio_pct
    again = engine.apply_action(took, Action(cash_buffer_pct=s.action.cash_buffer_pct, accept_prt=True), True)
    assert again.liabilities["prt"] == pytest.approx(took.liabilities["prt"])  # offered once


def test_scores_and_answer_key():
    s = fresh("MET")
    for q in range(1, engine.n_quarters() + 1):
        s, rec = engine.play_quarter(s, engine.card_for(q).benchmark_action)
        key = engine.answer_key(rec)
        assert key["main_driver"] in engine.ATTRIBUTION_LABELS and key["mechanism_facts"]
    sc = engine.score(s.history)
    assert 0 <= sc["results_score"] <= 100
    assert len(sc["per_quarter"]) == engine.n_quarters()
    assert s.quarter == engine.n_quarters() + 1


def test_benchmark_beats_doing_nothing_for_most_companies():
    better = 0
    for p in PROFILES:
        res = {}
        for name in ("nothing", "benchmark"):
            s = engine.build_state(p, SEED)
            for q in range(1, engine.n_quarters() + 1):
                s, _ = engine.play_quarter(s, None if name == "nothing" else engine.card_for(q).benchmark_action)
            res[name] = engine.surplus(s)
        better += res["benchmark"] > res["nothing"]
    assert better == len(PROFILES)


def test_boss_round_collapses_doing_nothing_but_not_a_pro():
    """Every company collapses if it does nothing all game; a pro's trades survive the boss round."""
    for p in PROFILES:
        for name in ("nothing", "benchmark"):
            s = engine.build_state(p, SEED)
            for q in range(1, engine.n_quarters() + 1):
                s, _ = engine.play_quarter(s, None if name == "nothing" else engine.card_for(q).benchmark_action)
            assert engine.collapsed(s) == (name == "nothing"), (p.ticker, name, engine.surplus(s))


def test_a_collapse_scores_zero_for_quarters_never_reached():
    s = fresh("EQH")
    s, rec = engine.play_quarter(s, None)
    rec.surplus_after = -1.0
    assert engine.score([rec])["per_quarter"][1:] == [0.0] * (engine.n_quarters() - 1)


def test_collateral_call_locks_up_cash_without_losing_it_and_comes_back():
    s = fresh("JXN")
    calm = ShockVector()
    called = ShockVector(margin_call_pct=2)
    a, _ = engine.apply_shock(s, calm)
    b, att = engine.apply_shock(s, called)
    assert b.collateral_posted == pytest.approx(0.02 * engine.total_assets(s))
    assert engine.dashboard(b).liquidity_ratio_pct < engine.dashboard(a).liquidity_ratio_pct
    assert engine.surplus(b) == pytest.approx(engine.surplus(a) + att.liquidity, abs=1e-6)  # only fire-sale haircuts cost money
    c, _ = engine.apply_shock(b, calm)  # returned the next quarter
    assert c.collateral_posted == 0


def test_market_and_trade_effects_are_said_separately():
    s = fresh("JXN")
    _, idle = engine.play_quarter(s, None)
    key = engine.answer_key(idle)
    assert not key["traded"] and "no trades" in key["split_fact"] and "all of it from the market" in key["split_fact"]
    _, busy = engine.play_quarter(s, engine.card_for(1).benchmark_action)
    key = engine.answer_key(busy)
    assert key["traded"] and "your trades added" in key["split_fact"]
    assert "positions behaved the same as doing nothing" in engine.split_fact(1.0, 1.0, True)
