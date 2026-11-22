"""Before-and-after quiz, confidence ratings, feedback and the session summary."""

from __future__ import annotations

import json
from collections import Counter

from fastapi.testclient import TestClient

from backend.env import REPO_DIR
from backend.main import app

client = TestClient(app)
QUIZ = json.loads((REPO_DIR / "data" / "quiz.json").read_text(encoding="utf-8"))
CONF = {c["id"]: 3 for c in QUIZ["confidence"]}


def key(form: str) -> dict:
    return {i["id"]: i["answer"] for i in QUIZ["forms"][form]}


def test_forms_cover_the_same_eight_concepts_with_spread_answers():
    a, b = QUIZ["forms"]["A"], QUIZ["forms"]["B"]
    assert len(a) == len(b) == 8
    assert [i["concept"] for i in a] == [i["concept"] for i in b] == QUIZ["concepts"]
    assert {i["q"] for i in a}.isdisjoint({i["q"] for i in b})  # different wording
    for form in (a, b):
        assert max(Counter(i["answer"] for i in form).values()) <= 4  # no "always B"


def test_form_hides_answers():
    f = client.get("/api/quiz/pre").json()
    assert f["form"] == "A" and all("answer" not in q for q in f["questions"])
    assert client.get("/api/quiz/post").json()["form"] == "B"


def test_quiz_flow_saves_before_and_after_figures():
    gid = client.post("/api/game", json={"ticker": "LNC"}).json()["id"]
    pre = client.post(f"/api/quiz/{gid}/pre", json={"answers": key("A"), "confidence": CONF}).json()
    assert pre["correct"] == 8 and pre["answers_key"] is None  # no key leaked before the game
    assert client.post(f"/api/quiz/{gid}/pre", json={"answers": {}, "confidence": CONF}).status_code == 409  # once only
    assert client.post(f"/api/quiz/{gid}/post", json={"answers": {}, "confidence": CONF}).status_code == 409  # not yet
    assert "pre" in client.get(f"/api/game/{gid}").json()["quiz_taken"]
    for _ in range(4):
        client.post(f"/api/game/{gid}/advance")
        client.post(f"/api/game/{gid}/explain", json={"text": "", "not_sure": True})
    wrong = {k: ("A" if v != "A" else "B") for k, v in key("B").items()}
    post = client.post(f"/api/quiz/{gid}/post", json={"answers": wrong, "confidence": {k: 5 for k in CONF}}).json()
    assert post["correct"] == 0 and post["answers_key"] is not None
    ba = client.get(f"/api/game/{gid}/debrief").json()["before_after"]
    assert ba["quiz_pre"]["score"] == 100 and ba["quiz_post"]["score"] == 0 and ba["quiz_change_pts"] == -100
    assert ba["confidence_pre_avg"] == 3 and ba["confidence_post_avg"] == 5 and ba["confidence_change"] == 2
    session_file = REPO_DIR / "output" / "sessions" / f"{gid}.json"
    saved = json.loads(session_file.read_text(encoding="utf-8"))
    assert saved["quiz"]["pre"]["correct"] == 8 and saved["confidence"]["post"]["C1"] == 5


def test_confidence_must_be_complete_and_in_range():
    gid = client.post("/api/game", json={"ticker": "MET"}).json()["id"]
    assert client.post(f"/api/quiz/{gid}/pre", json={"answers": {}, "confidence": {"C1": 3}}).status_code == 409
    bad = {**CONF, "C1": 9}
    assert client.post(f"/api/quiz/{gid}/pre", json={"answers": {}, "confidence": bad}).status_code == 409


def test_feedback_and_summary():
    gid = client.post("/api/game", json={"ticker": "PRU"}).json()["id"]
    assert client.post(f"/api/game/{gid}/feedback", json={"text": "Clear and fun"}).json()["count"] == 1
    s = client.get(f"/api/game/{gid}/summary").json()
    assert s["feedback"][0]["text"] == "Clear and fun" and "before_after" in s and s["ticker"] == "PRU"
