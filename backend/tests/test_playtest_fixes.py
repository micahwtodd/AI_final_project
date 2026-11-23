"""Fixes from the two playtests: hint ladder, no answer leak on a missed first try, predictions,
positions re-measured after each quarter, "try this next time"."""
from fastapi.testclient import TestClient

from backend import engine, examiner
from backend.calibration import load_profile
from backend.main import app
from backend.models import Action

client = TestClient(app)


def _new(ticker="JXN"):
    return client.post("/api/game", json={"ticker": ticker, "seed": 409}).json()["id"]


def test_prediction_is_saved_and_reported_on_the_shock():
    gid = _new()
    s = client.post(f"/api/game/{gid}/advance", json={"prediction": "rates_up"}).json()
    assert s["prediction"]["correct"] is True and s["prediction"]["answer_label"] == "Rates jump"
    client.post(f"/api/game/{gid}/explain", json={"text": "", "not_sure": True})
    s2 = client.post(f"/api/game/{gid}/advance").json()  # no prediction is fine
    assert s2["prediction"] is None


def test_hint_ladder_names_the_driver_only_on_the_second_hint_and_halves_that_check():
    gid = _new()
    client.post(f"/api/game/{gid}/advance")
    h1 = client.post(f"/api/game/{gid}/hint").json()
    assert h1["level"] == 1 and "interest rates" not in h1["hint"]
    h2 = client.post(f"/api/game/{gid}/hint").json()
    assert h2["level"] == 2 and "interest rates" in h2["hint"]
    assert examiner.quarter_points([{"checks": {c: True for c in examiner.CHECKS}}], False, 2)["by_check"]["main_driver"] \
        == examiner.POINTS_PER_CHECK / 2


def test_a_missed_first_try_does_not_reveal_the_main_driver():
    gid = _new()
    client.post(f"/api/game/{gid}/advance")
    r = client.post(f"/api/game/{gid}/explain", json={"text": "idk"}).json()
    assert r["final"] is False
    assert "interest rates" not in r["review"]["reply_text"].lower()


def test_an_unchanged_ticket_trades_nothing_after_a_quarter():
    s = engine.build_state(load_profile("LNC"), 409)
    s, _ = engine.play_quarter(s, Action(rate_hedge_pct=-50, equity_hedge_pct=60, cash_buffer_pct=8))
    again = engine.apply_action(s, s.action)
    assert engine.dashboard(again).model_dump() == engine.dashboard(s).model_dump()


def test_debrief_has_a_try_next_line_and_prediction_tally():
    gid = _new()
    for q in range(1, engine.n_quarters() + 1):
        client.post(f"/api/game/{gid}/advance", json={"prediction": "everything"})
        client.post(f"/api/game/{gid}/explain", json={"text": "", "not_sure": True})
    d = client.get(f"/api/game/{gid}/debrief").json()
    assert d["predictions"]["made"] == engine.n_quarters() and d["predictions"]["correct"] == 1
    assert d["try_next"]
