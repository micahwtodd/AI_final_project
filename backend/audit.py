"""Audit trail and usage log. Append-only JSON Lines; never wiped.

output/audit_trail.jsonl  one line per event (delegation, tool_call, tool_result, reply, blocked, spend, stop)
output/usage_log.jsonl    one line per model call, with API-reported token counts and cost
"""

from __future__ import annotations

import json
import threading
import time

from backend.env import REPO_DIR, redact

OUT = REPO_DIR / "output"
AUDIT = OUT / "audit_trail.jsonl"
USAGE = OUT / "usage_log.jsonl"
_lock = threading.Lock()


def _append(path, record: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    line = redact(json.dumps(record, default=str))  # keys never reach the logs
    with _lock, path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def event(session_id: str, run_id: str, quarter: int, agent: str, type_: str, detail, *,
          input_tokens: int = 0, cached_tokens: int = 0, output_tokens: int = 0, cost_usd: float = 0.0) -> dict:
    ev = {"ts": round(time.time(), 3), "session_id": session_id, "run_id": run_id, "quarter": quarter,
          "agent": agent, "type": type_, "detail": detail, "input_tokens": input_tokens,
          "cached_tokens": cached_tokens, "output_tokens": output_tokens, "cost_usd": round(cost_usd, 6)}
    _append(AUDIT, ev)
    return ev


FLAGS = OUT / "flags.jsonl"


def flag(record: dict) -> None:
    _append(FLAGS, {"ts": round(time.time(), 3), **record})


def usage(record: dict) -> None:
    _append(USAGE, {"ts": round(time.time(), 3), **record})


def read_session(path, session_id: str, limit: int = 500) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if f'"session_id": "{session_id}"' in line:
                out.append(json.loads(line))
    return out[-limit:]
