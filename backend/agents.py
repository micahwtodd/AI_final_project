"""Agent wiring. Every model call goes to gpt-6-luna through Portkey."""

from __future__ import annotations

from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from backend.env import MODEL_NAME, PORTKEY_BASE_URL, portkey_key


def make_model() -> OpenAIResponsesModel:
    """The one model the app uses. Raises if no key is configured."""
    key = portkey_key()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY not found in environment, ./.env or ../.env")
    provider = OpenAIProvider(base_url=PORTKEY_BASE_URL, api_key=key)
    return OpenAIResponsesModel(MODEL_NAME, provider=provider)
