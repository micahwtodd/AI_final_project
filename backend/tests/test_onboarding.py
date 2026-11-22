"""Project 9: glossary route, demo mode, the shock question's numbers, and the sprite sheet."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

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


def test_sprite_sheet_shape():
    data = json.loads((ROOT / "frontend/src/sprites/sprites.json").read_text(encoding="utf-8"))
    assert len(data["palette"]) == 16
    sprites = data["sprites"]
    for who in ["amara", "walt", "priya", "teo", "sam"]:
        for mood in ["neutral", "pleased", "concerned"]:
            rows = sprites[f"{who}_{mood}"]
            assert len(rows) == len(rows[0]) and len({len(r) for r in rows}) == 1
    for state in ["nap", "alert", "hide"]:
        assert f"cat_{state}" in sprites
    for rows in sprites.values():
        assert all(re.fullmatch(r"[0-9a-f]+", r) for r in rows)


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
