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
