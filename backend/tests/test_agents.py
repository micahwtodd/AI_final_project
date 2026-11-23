"""Agent harness tests that make no model calls: tools, permissions, budget cap, usage routes."""

from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from backend import agents, audit, engine, game, tools
from backend.calibration import load_profile
from backend.main import app

client = TestClient(app)


def _state():
    return engine.build_state(load_profile("JXN"), 409)


def test_every_tool_returns_small_json():
    s = _state()
    for fn in (tools.get_risk_dashboard, tools.get_liability_summary, tools.get_surrender_projection,
               tools.get_guarantee_exposure, tools.get_asset_summary, tools.get_credit_exposure,
               tools.get_liquidity_ladder, tools.get_hedge_costs, tools.get_news_signal):
        out = fn(s)
        assert isinstance(out, dict) and len(json.dumps(out)) < 2000, fn.__name__


def test_tools_never_reveal_this_quarters_shock_or_benchmark():
    s = _state()
    blob = json.dumps([tools.get_news_signal(s), tools.get_risk_dashboard(s), tools.get_hedge_costs(s)]).lower()
    card = engine.card_for(1)
    assert card.headline.lower() not in blob
    assert "benchmark" not in blob and "severity" not in blob


def test_past_quarter_breakdown_hidden_until_revealed():
    s = _state()
    s, _ = engine.play_quarter(s, None)
    assert "hidden" in str(tools.get_past_quarter(s, 1, revealed=set())["change_by_cause_usd_bn"])
    assert isinstance(tools.get_past_quarter(s, 1, revealed={1})["change_by_cause_usd_bn"], dict)


def test_stress_test_matches_engine_and_changes_nothing():
    s = _state()
    before = s.model_dump()
    out = tools.stress_test(s, rate_bp=-100)
    assert out["surplus_change_usd_bn"] < 0  # Jackson's liabilities are longer than its assets
    assert s.model_dump() == before


def test_ticket_validation_rejects_out_of_range():
    s = _state()
    assert tools.validate_ticket({"rate_hedge_pct": 50}, s).rate_hedge_pct == 50
    try:
        tools.validate_ticket({"rate_hedge_pct": 500}, s)
        raise AssertionError("should reject")
    except Exception as e:
        assert "rate_hedge_pct" in str(e)


def test_glossary_has_every_card_term():
    g = tools.glossary()
    for c in engine.campaign():
        for t in c.glossary_terms:
            assert t in g, t


def test_solo_agent_tools_are_read_only_plus_propose():
    assert "propose_trade" in agents.SOLO_TOOLS
    assert not any(t.startswith(("set_", "execute", "commit", "score")) for t in agents.SOLO_TOOLS)


def test_budget_cap_blocks_before_any_model_call():
    s = game.new_game("MET", 409)
    s.budget_cap_usd = 0.0
    q: asyncio.Queue = asyncio.Queue()
    asyncio.run(agents.ask(s, "What is our biggest risk?", q, game.save))
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    types = [e["type"] for e in events]
    assert "blocked" in types and "spend" not in types and "tool_call" not in types
    assert s.tokens["requests"] == 0 and s.spend_usd == 0
    reply = next(e for e in events if e["type"] == "reply")
    assert reply["detail"]["stopped"] in ("budget", "no_key")
    logged = audit.read_session(audit.AUDIT, s.id)
    assert any(e["type"] == "blocked" for e in logged)


def test_usage_and_budget_routes():
    gid = client.post("/api/game", json={"ticker": "LNC"}).json()["id"]
    u = client.get(f"/api/usage/{gid}").json()
    assert u["spend_usd"] == 0 and u["budget_cap_usd"] == 0.25 and u["blocked"] is False
    assert client.post(f"/api/budget/{gid}", json={"cap_usd": 0.002}).json()["budget_cap_usd"] == 0.002
    assert client.post(f"/api/budget/{gid}", json={"cap_usd": -1}).status_code == 422
    assert "events" in client.get(f"/api/audit/{gid}").json()


def test_ask_route_streams_blocked_reply_when_capped():
    gid = client.post("/api/game", json={"ticker": "PRU"}).json()["id"]
    client.post(f"/api/budget/{gid}", json={"cap_usd": 0})
    with client.stream("POST", f"/api/game/{gid}/ask", json={"message": "hello"}) as r:
        body = "".join(r.iter_text())
    events = [json.loads(line[6:]) for line in body.split("\n") if line.startswith("data: ")]
    assert events[-1]["type"] == "usage" and any(e["type"] == "reply" for e in events)


# ---------------------------------------------------------------- Team mode (Project 4)

def test_permissions_match_plan():
    T = agents.TOOLSETS
    # only the Trader (and Solo) can write a ticket
    assert {k for k, v in T.items() if "propose_trade" in v} == {"trader", "solo"}
    # only the CRO delegates
    assert {k for k, v in T.items() if any(t.startswith("ask_") for t in v)} == {"cro"}
    # specialists see only their own area
    assert T["actuary"].isdisjoint({"get_asset_summary", "get_credit_exposure", "get_hedge_costs"})
    assert T["portfolio_manager"].isdisjoint({"get_liability_summary", "get_hedge_costs", "propose_trade"})
    assert T["trader"].isdisjoint({"get_liability_summary", "get_credit_exposure"})
    # the coach reads the dashboard but not the specialists' detail
    assert T["cro"].isdisjoint({"get_liability_summary", "get_asset_summary", "get_hedge_costs", "propose_trade"})
    # no agent has a tool that changes positions, scores or the budget
    every = set().union(*T.values())
    assert not any(t.startswith(("set_", "execute", "commit", "score", "update_")) for t in every)


def test_prompts_load_with_rules_and_glossary():
    for kind in agents.PROMPT_FILES:
        text = agents.load_prompt(agents.PROMPT_FILES[kind])
        assert "{RULES}" not in text and "{GLOSSARY}" not in text
        assert "Numbers only from tools" in text and "Duration" in text


def test_mode_switch_route():
    gid = client.post("/api/game", json={"ticker": "EQH"}).json()["id"]
    assert client.get(f"/api/game/{gid}").json()["agent_mode"] == "team"
    assert client.post(f"/api/game/{gid}/mode", json={"agent_mode": "solo"}).json()["agent_mode"] == "solo"
    assert client.get(f"/api/game/{gid}").json()["agent_mode"] == "solo"
    assert client.post(f"/api/game/{gid}/mode", json={"agent_mode": "boss"}).status_code == 422


def test_delegation_cap_and_budget_stop_without_model_calls():
    s = game.new_game("MET", 409)
    events = []
    run = agents.RunCtx(session=s, run_id="t", emit=lambda *a, **k: events.append(a) or {})

    class Ctx:  # minimal stand-in for RunContext
        deps = agents.Deps(run=run, agent="cro")

    run.delegations = agents.MAX_DELEGATIONS
    out = asyncio.run(agents._delegate(Ctx(), "actuary", "anything"))
    assert "limit" in out["error"]
    run.delegations, run.stopped = 0, "budget"
    out = asyncio.run(agents._delegate(Ctx(), "trader", "anything"))
    assert "budget" in out["error"] and s.tokens["requests"] == 0


def test_replies_drop_stock_opener_and_questions_back_to_the_learner():
    from backend.agents import strip_opener
    out = strip_opener("Walk me through it: rates rose 77bp. Which risk would you rather carry? Cash is 7.6% of assets.")
    assert out == "Rates rose 77bp. Cash is 7.6% of assets."
    assert strip_opener("Liquidity is 1.5x the need. Is 1.5x enough?") == "Liquidity is 1.5x the need."
    assert strip_opener("Is that a hedge?") == "Is that a hedge?"  # never blank a reply
