"""Agent wiring. Every model call goes to gpt-6-luna, through Portkey or OpenAI."""

from __future__ import annotations

from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from backend.env import MODEL_NAME, provider_config


def make_model() -> OpenAIResponsesModel:
    """The one model the app uses. Raises if no key is configured."""
    cfg = provider_config()
    if cfg is None:
        raise RuntimeError(
            "No API key found. Set PORTKEY_API_KEY or OPENAI_API_KEY in ./.env or ../.env"
        )
    _, base_url, key = cfg
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(base_url=base_url, api_key=key))
