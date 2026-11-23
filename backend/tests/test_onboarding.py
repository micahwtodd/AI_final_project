"""Project 9: glossary route, demo mode, the shock question's numbers, and the sprite sheet."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from backend import engine
from backend.main import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]


def _play_to_shock(demo: bool) -> dict:
    g = client.post("/api/game", json={"ticker": "JXN", "seed": 409, "demo": demo}).json()
    assert g["demo"] is demo
    client.post(f"/api/game/{g['id']}/commit", json={"actions": {"cash_buffer_pct": 10}})
    return client.post(f"/api/game/{g['id']}/advance").json()


def test_glossary_route_has_definitions():
    gl = client.get("/api/glossary").json()
    assert len(gl) >= 30
    assert all(isinstance(v, dict) and v.get("label") and v.get("plain") for v in gl.values())


def test_sample_answer_only_in_demo():
    assert _play_to_shock(demo=True)["sample_answer"]
    assert _play_to_shock(demo=False)["sample_answer"] is None


def test_question_matches_headline_change():
    shock = _play_to_shock(demo=False)
    amount = float(re.search(r"\$(\d+\.\d\d) billion", shock["question"]).group(1))
    assert amount == round(abs(shock["surplus_change"]), 2)


def _png_size(path: Path) -> tuple[int, int]:
    head = path.read_bytes()[:24]
    assert head[1:4] == b"PNG"
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def test_art_files_exist_with_the_right_sizes():
    art = ROOT / "frontend/public/art"
    for who in ["vera", "morty", "bonnie", "swap", "seamore"]:
        for mood in ["neutral", "pleased", "concerned"]:
            assert _png_size(art / f"{who}_{mood}.png") == (64, 64)
    for state in ["nap", "alert", "hide"]:
        assert _png_size(art / f"cat_{state}.png") == (48, 48)
    for v in ["day"] + [f"{s}{st}" for s in ("spring", "summer", "fall", "winter") for st in ("", "_storm")]:
        assert _png_size(art / f"office_{v}.png") == (480, 270)


# ---------------------------------------------------------------- Gate 1 changes: editable game inputs, 5-item quiz

def test_companies_list_editable_inputs():
    jxn = next(c for c in client.get("/api/companies").json() if c["ticker"] == "JXN")
    keys = {r["key"] for r in jxn["inputs"]}
    assert {"surplus_usd_bn", "invested_assets_usd_bn", "asset_mix.govt", "liability_mix.annuities"} <= keys


def test_preview_with_overrides_changes_balance_sheet():
    base = client.post("/api/companies/JXN/preview", json={"overrides": {}}).json()["dashboard"]
    r = client.post("/api/companies/JXN/preview", json={"overrides": {"surplus_usd_bn": 8.0, "asset_mix.govt": 0.2}})
    assert r.status_code == 200
    d = r.json()["dashboard"]
    assert abs(d["surplus_usd_bn"] - 8.0) < 0.05 and d["asset_values"]["govt"] > 3 * base["asset_values"]["govt"]


def test_bad_overrides_rejected():
    assert client.post("/api/companies/JXN/preview", json={"overrides": {"surplus_usd_bn": 400}}).status_code == 422
    assert client.post("/api/companies/JXN/preview", json={"overrides": {"not_a_field": 1}}).status_code == 422
    assert client.post("/api/companies/XYZ/preview", json={"overrides": {}}).status_code == 404
    assert client.post("/api/game", json={"ticker": "JXN", "overrides": {"alts_beta": 9}}).status_code == 422


def test_new_game_uses_overrides():
    g = client.post("/api/game", json={"ticker": "JXN", "seed": 409, "overrides": {"surplus_usd_bn": 9.5}}).json()
    assert g["custom_inputs"] == ["surplus_usd_bn"]
    assert abs(g["dashboard"]["surplus_usd_bn"] - 9.5) < 0.2  # cash top-up to the floor can move it slightly


def test_quiz_has_five_questions_and_five_ratings():
    for when in ("pre", "post"):
        f = client.get(f"/api/quiz/{when}").json()
        assert len(f["questions"]) == 5 and len(f["confidence"]) == 5


# ---------------------------------------------------------------- Knowledge Check answers; FX switched off

def test_quiz_form_hides_answers_and_explanations():
    for item in client.get("/api/quiz/pre").json()["questions"]:
        assert "answer" not in item and "explain" not in item


def test_check_answer_explains_and_locks_the_choice():
    gid = client.post("/api/game", json={"ticker": "JXN", "seed": 409}).json()["id"]
    q = client.get("/api/quiz/pre").json()["questions"][0]
    wrong = next(k for k in q["options"] if k != "B")  # A1's answer is B
    r = client.post(f"/api/quiz/{gid}/pre/check", json={"qid": q["id"], "choice": wrong}).json()
    assert r["correct"] is False and r["answer"] == "B" and r["explain"]
    again = client.post(f"/api/quiz/{gid}/pre/check", json={"qid": q["id"], "choice": "B"}).json()
    assert again["choice"] == wrong  # the first checked choice is locked
    form = client.get("/api/quiz/pre").json()
    answers = {x["id"]: "B" for x in form["questions"]}  # tries to switch A1 to the right answer
    res = client.post(f"/api/quiz/{gid}/pre", json={"answers": answers, "confidence": {c["id"]: 3 for c in form["confidence"]}}).json()
    assert res["by_concept"]["duration_gap"] is False


def test_fx_is_switched_off_everywhere():
    from backend.calibration import load_profile
    for t in ["MET", "PRU", "JXN"]:
        st = engine.build_state(load_profile(t), 409)
        assert st.foreign_share == 0 and engine.dashboard(st).fx_exposure_usd_bn == 0
    for q in range(1, engine.n_quarters() + 1):
        _, shock = engine.realize_shock(engine.card_for(q), 409)
        assert shock.fx_pct == 0
        assert engine.card_for(q).benchmark_action.fx_hedge_pct == 0
    jxn = next(c for c in client.get("/api/companies").json() if c["ticker"] == "JXN")
    assert not any("fx" in r["key"] or "foreign" in r["key"] for r in jxn["inputs"] + jxn["dossier"])
