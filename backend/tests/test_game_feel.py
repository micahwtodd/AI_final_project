"""Badges, streaks and the report card: deterministic, revealed only after explaining, and graded in code."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend import achievements, engine
from backend.main import app

client = TestClient(app)
GOOD = ("Interest rates moved the most. Because our liabilities are longer than our assets, surplus changed with rates; "
        "stocks and credit spreads were the second factor, and our hedges and cash buffer helped.")


def _play(strategy: str) -> tuple[str, list[dict], dict]:
    gid = client.post("/api/game", json={"ticker": "JXN", "seed": 409}).json()["id"]
    reveals = []
    for q in range(1, 5):
        act = engine.card_for(q).benchmark_action.model_dump() if strategy == "benchmark" else {"cash_buffer_pct": 3}
        client.post(f"/api/game/{gid}/commit", json={"actions": act})
        client.post(f"/api/game/{gid}/advance")
        r = client.post(f"/api/game/{gid}/explain", json={"text": GOOD}).json()
        if not r["final"]:
            r = client.post(f"/api/game/{gid}/explain", json={"text": GOOD}).json()
        reveals.append(r)
    return gid, reveals, client.get(f"/api/game/{gid}/debrief").json()


def test_badges_only_after_reveal_and_once_each():
    gid = client.post("/api/game", json={"ticker": "JXN", "seed": 409}).json()["id"]
    client.post(f"/api/game/{gid}/commit", json={"actions": {"cash_buffer_pct": 5}})
    client.post(f"/api/game/{gid}/advance")
    assert client.get(f"/api/game/{gid}").json()["achievements"]["earned"] == []  # nothing before explaining
    _, reveals, deb = _play("benchmark")
    ids = [b["id"] for b in deb["achievements"]["earned"]]
    assert len(ids) == len(set(ids))
    assert all(b["id"] in achievements.BADGES for r in reveals for b in r["badges_new"])


def test_benchmark_player_earns_benchmark_badges_and_a_grade():
    _, reveals, deb = _play("benchmark")
    ids = {b["id"] for b in deb["achievements"]["earned"]}
    assert "beat_benchmark" in ids
    rc = deb["report_card"]
    assert rc["grade"] in {"A+", "A", "B+", "B", "C+", "C", "D", "F"} and rc["title"] and rc["why"]
    assert abs(rc["overall"] - (0.6 * deb["results_score"] + 0.4 * deb["understanding_score"])) < 0.11


def test_grade_cutoffs():
    assert achievements.grade_for(95) == "A+" and achievements.grade_for(70) == "B" and achievements.grade_for(10) == "F"


# ---------------------------------------------------------------- scoring fix (benchmark below doing nothing)

def _campaign(ticker: str, strategy: str):
    from backend.calibration import load_profile
    st = engine.build_state(load_profile(ticker), 409)
    for q in range(1, 5):
        st, _ = engine.play_quarter(st, engine.card_for(q).benchmark_action if strategy == "benchmark" else None)
    return st.history


def test_copying_the_benchmark_scores_well_for_every_company():
    for t in ["MET", "PRU", "CRBG", "LNC", "EQH", "JXN"]:
        hist = _campaign(t, "benchmark")
        assert engine.score(hist)["results_score"] >= 85, t
        assert all(engine.quarter_score(r) >= 0.9 - 1e-9 for r in hist), t
        assert engine.score(hist)["penalties"] == 0, t  # breaches the benchmark shares are not penalized


def test_fallback_is_graded_not_a_cliff():
    from backend.models import Attribution, QuarterRecord, ShockVector, Action
    base = dict(quarter=4, card_id="x", severity=1.0, shock=ShockVector(), action=Action(), attribution=Attribution(),
                surplus_before=10.0, nothing_surplus_after=10.0, benchmark_surplus_after=9.9)
    score = lambda after: engine.quarter_score(QuarterRecord(surplus_after=after, **base))  # noqa: E731
    assert score(10.0) == 1.0 and abs(score(9.9) - 0.9) < 1e-9
    assert 0.9 < score(9.95) < 1.0
    assert 0 < score(9.8) < 0.9 and score(9.0) == 0.0
