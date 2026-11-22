"""FastAPI app. Routes live under /api/... ; the built frontend (frontend/dist) is served at /."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import game
from backend.env import MODEL_NAME, REPO_DIR, load_env
from backend.models import Action

app = FastAPI(title="Risk Desk")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- request bodies

class NewGame(BaseModel):
    ticker: str
    seed: int | None = None
    agent_mode: Literal["solo", "team"] = "team"
    demo: bool = False


class ActionBody(BaseModel):
    action: Action


class CommitBody(BaseModel):
    actions: Action


class ExplainBody(BaseModel):
    text: str = ""
    not_sure: bool = False


def _session(session_id: str) -> game.Session:
    try:
        return game.get(session_id)
    except KeyError:
        raise HTTPException(404, "Game not found")


def _run(fn, *args):
    try:
        return fn(*args)
    except game.GameError as e:
        raise HTTPException(409, str(e))


# ---------------------------------------------------------------- routes

@app.get("/api/health")
def health() -> dict:
    status = load_env()
    return {
        "ok": True,
        "key_found": status.key_found,
        "provider": status.provider,
        "key_name": status.key_name,
        "key_source": status.key_source,
        "model": MODEL_NAME,
    }


@app.get("/api/companies")
def companies() -> list[dict]:
    return game.companies()


@app.post("/api/game")
def new_game(body: NewGame) -> dict:
    try:
        s = game.new_game(body.ticker, body.seed, body.agent_mode, body.demo)
    except FileNotFoundError:
        raise HTTPException(404, f"No cached profile for {body.ticker}")
    return game.view(s)


@app.get("/api/game/{session_id}")
def get_game(session_id: str) -> dict:
    return game.view(_session(session_id))


@app.post("/api/game/{session_id}/preview")
def preview(session_id: str, body: ActionBody) -> dict:
    return _run(game.preview, _session(session_id), body.action)


@app.post("/api/game/{session_id}/commit")
def commit(session_id: str, body: CommitBody) -> dict:
    return _run(game.commit, _session(session_id), body.actions)


@app.post("/api/game/{session_id}/advance")
def advance(session_id: str) -> dict:
    return _run(game.advance, _session(session_id))


@app.post("/api/game/{session_id}/explain")
def explain(session_id: str, body: ExplainBody) -> dict:
    return _run(game.explain, _session(session_id), body.text, body.not_sure)


@app.get("/api/game/{session_id}/debrief")
def debrief(session_id: str) -> dict:
    return _run(game.debrief, _session(session_id))


# ---------------------------------------------------------------- frontend

DIST = REPO_DIR / "frontend" / "dist"

if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "Not found")
    target = DIST / path
    if path and target.is_file():
        return FileResponse(target)
    index = DIST / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {"message": "Frontend not built yet. Run: cd frontend && npm install && npm run build"}
