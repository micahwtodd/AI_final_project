"""End-to-end API test: a full game, plus phase guards."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend import engine
from backend.main import app

client = TestClient(app)


def test_health_and_companies():
    assert client.get("/api/health").json()["ok"] is True
    tickers = [c["ticker"] for c in client.get("/api/companies").json()]
    assert tickers == ["MET", "PRU", "CRBG", "LNC", "EQH", "JXN"]


def test_full_game_end_to_end():
    g = client.post("/api/game", json={"ticker": "JXN", "seed": 409}).json()
    gid = g["id"]
    assert g["phase"] == "position" and g["quarter"] == 1 and g["card"]["title"]
    assert "headline" not in g["card"]  # the shock stays hidden until the quarter ends

    for q in range(1, engine.n_quarters() + 1):
        action = {"rate_hedge_pct": 50, "equity_hedge_pct": 40, "fx_hedge_pct": 50, "cash_buffer_pct": 8,
                  "collateralized": True, "dealers": 3, "accept_prt": q == 2}
        pv = client.post(f"/api/game/{gid}/preview", json={"action": action}).json()
        assert "before" in pv and "after" in pv
        c = client.post(f"/api/game/{gid}/commit", json={"actions": action}).json()
        assert c["view"]["pending"]["rate_hedge_pct"] == 50

        shock = client.post(f"/api/game/{gid}/advance").json()
        assert shock["quarter"] == q and shock["headline"] and shock["market_moves"]
        assert "attribution" not in shock  # breakdown hidden until the explanation
        assert client.post(f"/api/game/{gid}/advance").status_code == 409  # cannot skip explaining

        long_text = ("Interest rates and credit spreads moved, and because our liabilities are longer than our assets "
                     "surplus changed; our hedges and cash buffer helped a little this quarter.")
        rev = client.post(f"/api/game/{gid}/explain", json={"text": long_text}).json()
        if not rev["final"]:  # main driver missed: one more try
            rev = client.post(f"/api/game/{gid}/explain", json={"text": long_text + " Stocks and the dollar also moved."}).json()
        assert rev["final"] and rev["understanding"] is not None
        assert abs(sum(a["value"] for a in rev["attribution"]) - rev["total"]) < 1e-3
        assert set(rev["comparison"]) == {"you", "nothing", "benchmark"}
        assert rev["debrief_text"] and rev["lesson"]
        assert rev["finished"] == (q == engine.n_quarters() or rev["collapsed"]["you"])

    d = client.get(f"/api/game/{gid}/debrief").json()
    assert 0 <= d["results_score"] <= 100 and len(d["per_quarter"]) == engine.n_quarters() and d["text"]
    assert client.get(f"/api/game/{gid}").json()["phase"] == "finished"


def test_debrief_not_available_early_and_unknown_game():
    gid = client.post("/api/game", json={"ticker": "MET"}).json()["id"]
    assert client.get(f"/api/game/{gid}/debrief").status_code == 409
    assert client.get("/api/game/nope").status_code == 404
