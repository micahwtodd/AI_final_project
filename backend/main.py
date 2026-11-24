"""FastAPI app. Routes live under /api/... ; the built frontend (frontend/dist) is served at /."""

from __future__ import annotations

import asyncio
import json
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import agents, audit, game
from backend.env import MODEL_NAME, REPO_DIR, fallback_config, load_env
from backend.models import Action

app = FastAPI(title="Surplus or Bust")
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
    overrides: dict[str, float] = {}


class OverridesBody(BaseModel):
    overrides: dict[str, float] = {}


class ActionBody(BaseModel):
    action: Action


class CommitBody(BaseModel):
    actions: Action


class AdvanceBody(BaseModel):
    prediction: str | None = None


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
        "fallback": "openai" if fallback_config() else None,
        "model": MODEL_NAME,
    }


@app.get("/api/glossary")
def glossary() -> dict:
    """The approved plain-English glossary (the only source of definitions, for people and agents)."""
    from backend import tools
    return tools.glossary()


@app.get("/api/companies")
def companies() -> list[dict]:
    return game.companies()


@app.post("/api/companies/{ticker}/preview")
def preview_company(ticker: str, body: OverridesBody) -> dict:
    """Balance sheet for a company with the learner's edited inputs (nothing is saved)."""
    try:
        return game.preview_profile(ticker.upper(), body.overrides)
    except game.GameError as e:
        raise HTTPException(422, str(e))
    except FileNotFoundError:
        raise HTTPException(404, f"No cached profile for {ticker}")


@app.post("/api/game")
def new_game(body: NewGame) -> dict:
    try:
        s = game.new_game(body.ticker, body.seed, body.agent_mode, body.demo, body.overrides)
    except game.GameError as e:
        raise HTTPException(422, str(e))
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
def advance(session_id: str, body: AdvanceBody | None = None) -> dict:
    return _run(game.advance, _session(session_id), body.prediction if body else None)


@app.post("/api/game/{session_id}/whatif")
def whatif(session_id: str, body: ActionBody) -> dict:
    return _run(game.whatif, _session(session_id), body.action)


@app.post("/api/game/{session_id}/hint")
def hint(session_id: str) -> dict:
    return _run(game.hint, _session(session_id))


@app.post("/api/game/{session_id}/explain")
async def explain(session_id: str, body: ExplainBody) -> dict:
    """Examiner review. Returns {final: false, question} for a second try, or the full reveal when final."""
    try:
        return await game.explain(_session(session_id), body.text, body.not_sure)
    except game.GameError as e:
        raise HTTPException(409, str(e))


@app.get("/api/game/{session_id}/debrief")
def debrief(session_id: str) -> dict:
    return _run(game.debrief, _session(session_id))


# ---------------------------------------------------------------- AI colleagues

class AskBody(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    to: str | None = None


class BudgetBody(BaseModel):
    cap_usd: float = Field(ge=0, le=0.25)  # the per-game cap can be lowered, never raised


@app.post("/api/game/{session_id}/ask")
async def ask(session_id: str, body: AskBody):
    """Streams agent events (Server-Sent Events) and ends with the reply."""
    s = _session(session_id)
    queue: asyncio.Queue = asyncio.Queue()

    async def produce() -> None:
        try:
            await agents.ask(s, body.message.strip(), queue, game.save, to=body.to)
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(produce())

    async def stream():
        while True:
            ev = await queue.get()
            if ev is None:
                break
            yield f"data: {json.dumps(ev, default=str)}\n\n"
        await task

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class ModeBody(BaseModel):
    agent_mode: Literal["solo", "team"]


@app.post("/api/game/{session_id}/mode")
def set_mode(session_id: str, body: ModeBody) -> dict:
    """Switch between Solo (one agent) and Team (CRO plus specialists). The examiner is the same in both."""
    s = _session(session_id)
    s.agent_mode = body.agent_mode
    game.save(s)
    return {"agent_mode": s.agent_mode}


@app.get("/api/usage/{session_id}")
def usage(session_id: str) -> dict:
    return game.usage_view(_session(session_id))


@app.post("/api/budget/{session_id}")
def budget(session_id: str, body: BudgetBody) -> dict:
    return game.set_budget(_session(session_id), body.cap_usd)


class QuizBody(BaseModel):
    answers: dict[str, str] = {}
    confidence: dict[str, int] = {}


class FeedbackBody(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@app.get("/api/quiz/{when}")
def quiz_form(when: Literal["pre", "post"]) -> dict:
    """Form A (before) or form B (after), without the answers."""
    return game.quiz_form(when)


class QuizCheckBody(BaseModel):
    qid: str
    choice: str


@app.post("/api/quiz/{session_id}/{when}/check")
def quiz_check(session_id: str, when: Literal["pre", "post"], body: QuizCheckBody) -> dict:
    return _run(game.check_quiz_answer, _session(session_id), when, body.qid, body.choice)


@app.post("/api/quiz/{session_id}/{when}")
def quiz_submit(session_id: str, when: Literal["pre", "post"], body: QuizBody) -> dict:
    return _run(game.submit_quiz, _session(session_id), when, body.answers, body.confidence)


@app.post("/api/game/{session_id}/feedback")
def feedback(session_id: str, body: FeedbackBody) -> dict:
    return _run(game.add_feedback, _session(session_id), body.text)


@app.get("/api/game/{session_id}/summary")
def summary(session_id: str) -> dict:
    return game.summary(_session(session_id))


class FlagBody(BaseModel):
    event_id: str = Field(min_length=1, max_length=64)
    session_id: str | None = None
    note: str = Field("", max_length=1000)
    text: str = Field("", max_length=4000)


@app.post("/api/flag")
def flag(body: FlagBody) -> dict:
    """The learner flags a reply as wrong. Appended to output/flags.jsonl for review."""
    audit.flag(body.model_dump())
    return {"ok": True}


@app.get("/api/experiments")
def experiments() -> dict:
    """Results of scripts/experiments.py (E1 to E4 and the cost projections)."""
    import json
    p = REPO_DIR / "evidence" / "experiments.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"generated": None}


@app.get("/api/safety")
def safety_latest() -> dict:
    from backend import safety_lab
    return safety_lab.latest() or {"generated": None}


@app.post("/api/safety/run")
async def safety_run() -> dict:
    """Locked: the Safety Lab spends AI budget outside any game's cap, so it is not run from the app.
    Re-run it from the command line with `python scripts/safety_lab.py`; the saved results are shown here."""
    raise HTTPException(403, "The Safety Lab is not run from the app. Re-run it with: python scripts/safety_lab.py")


@app.get("/api/audit/{session_id}")
def audit_trail(session_id: str) -> dict:
    _session(session_id)
    return {"events": audit.read_session(audit.AUDIT, session_id),
            "usage": audit.read_session(audit.USAGE, session_id)}


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
    if index.is_file():  # never cache the page itself, so a rebuilt bundle is always picked up
        return FileResponse(index, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return {"message": "Frontend not built yet. Run: cd frontend && npm install && npm run build"}
