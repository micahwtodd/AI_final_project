"""Environment loading.

Looks for `.env` in the repo folder first, then one folder up (where the
teaching staff keep theirs). The first value found wins.

Two keys are supported, with these exact names:
  PORTKEY_API_KEY  -> Yale Portkey gateway (used when present)
  OPENAI_API_KEY   -> OpenAI directly (used when there is no Portkey key)
With both keys, a request that fails on Portkey is retried on OpenAI (see fallback_config).

Keys are never printed or logged. Only "found / not found" and the source
folder are ever reported.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

REPO_DIR = Path(__file__).resolve().parent.parent
ENV_CANDIDATES = [(REPO_DIR / ".env", "repo folder"), (REPO_DIR.parent / ".env", "parent folder")]

MODEL_NAME = "gpt-6-luna"

PROVIDERS = {
    # provider: (key name, base URL)
    "portkey": ("PORTKEY_API_KEY", "https://api.portkey.ai/v1"),
    "openai": ("OPENAI_API_KEY", "https://api.openai.com/v1"),
}
PROVIDER_ORDER = ["portkey", "openai"]


@dataclass(frozen=True)
class EnvStatus:
    key_found: bool
    provider: str | None  # "portkey", "openai", or None
    key_name: str | None
    key_source: str | None  # "environment", "repo folder", "parent folder", or None


_status: EnvStatus | None = None


def _source_of(key_name: str, preset: set[str]) -> str | None:
    if key_name in preset:
        return "environment"
    for path, label in ENV_CANDIDATES:
        if path.is_file() and dotenv_values(path).get(key_name):
            return label
    return None


def load_env() -> EnvStatus:
    """Load .env files once and report which provider and key will be used."""
    global _status
    if _status is not None:
        return _status

    preset = {name for name, _ in PROVIDERS.values() if os.environ.get(name)}
    for path, _ in ENV_CANDIDATES:
        if path.is_file():
            load_dotenv(path, override=False)  # real env vars and earlier files win

    for provider in PROVIDER_ORDER:
        key_name, _ = PROVIDERS[provider]
        if os.environ.get(key_name):
            _status = EnvStatus(True, provider, key_name, _source_of(key_name, preset))
            return _status

    _status = EnvStatus(False, None, None, None)
    return _status


# Anything that looks like an API key, including the masked forms providers echo
# back in error messages (e.g. "sk-proj-****...abcd").
_KEY_PATTERN = re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_\-*]{6,}")


def redact(text: object) -> str:
    """Remove key values and key-like strings from text before it is shown or logged."""
    s = str(text)
    for key_name, _ in PROVIDERS.values():
        value = os.environ.get(key_name)
        if value:
            s = s.replace(value, "[REDACTED]")
    return _KEY_PATTERN.sub("[REDACTED]", s)


def provider_config() -> tuple[str, str, str] | None:
    """(provider, base_url, api_key) for the active provider, or None if no key."""
    status = load_env()
    if not status.key_found or status.provider is None:
        return None
    key_name, base_url = PROVIDERS[status.provider]
    return status.provider, base_url, os.environ[key_name]


def fallback_config() -> tuple[str, str] | None:
    """(base_url, api_key) for OpenAI when Portkey is the primary provider and an OpenAI key is also set.
    A request that fails on Portkey (bad key, gateway error, outage) is then retried on OpenAI."""
    status = load_env()
    key_name, base_url = PROVIDERS["openai"]
    if status.provider == "portkey" and os.environ.get(key_name):
        return base_url, os.environ[key_name]
    return None
