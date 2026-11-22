"""FastAPI app. Routes live under /api/..."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.env import MODEL_NAME, load_env

app = FastAPI(title="Risk Desk")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    status = load_env()
    return {
        "ok": True,
        "key_found": status.key_found,
        "key_source": status.key_source,
        "model": MODEL_NAME,
    }
