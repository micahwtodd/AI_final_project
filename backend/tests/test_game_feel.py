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
