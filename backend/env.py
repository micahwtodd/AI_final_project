"""Environment loading.

Looks for `.env` in the repo folder first, then one folder up (where the
teaching staff keep theirs). The first value found wins.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

REPO_DIR = Path(__file__).resolve().parent.parent
ENV_CANDIDATES = [REPO_DIR / ".env", REPO_DIR.parent / ".env"]

KEY_NAME = "PORTKEY_API_KEY"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MODEL_NAME = "gpt-6-luna"


@dataclass(frozen=True)
class EnvStatus:
    key_found: bool
    key_source: str | None  # "environment", "repo folder", "parent folder", or None


_status: EnvStatus | None = None


def load_env() -> EnvStatus:
    """Load .env files once and report where the Portkey key came from."""
    global _status
    if _status is not None:
        return _status

    source: str | None = "environment" if os.environ.get(KEY_NAME) else None

    for path, label in zip(ENV_CANDIDATES, ["repo folder", "parent folder"]):
        if not path.is_file():
            continue
        if source is None and dotenv_values(path).get(KEY_NAME):
            source = label
        load_dotenv(path, override=False)  # earlier files and real env vars win

    _status = EnvStatus(key_found=bool(os.environ.get(KEY_NAME)), key_source=source)
    return _status


def portkey_key() -> str | None:
    load_env()
    return os.environ.get(KEY_NAME) or None
