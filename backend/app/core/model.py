"""The provider factory — the single place a model is constructed.

Keeping every agent behind one factory is what makes the riskiest dependency
swappable: changing provider is a config change here, not an edit across five
agent definitions.
"""

from __future__ import annotations

from functools import lru_cache

from agents import AsyncOpenAI, OpenAIChatCompletionsModel, set_tracing_disabled
from agents.models.interface import Model

from app.core.config import get_settings


@lru_cache
def gemini_model() -> Model:
    """Build the configured model. `mock` by default so the app boots unconfigured."""
    settings = get_settings()

    if settings.model_provider == "mock":
        from app.core.mock_model import MockModel

        # Tracing uploads to OpenAI's backend, which we never authenticate against.
        set_tracing_disabled(True)
        return MockModel()

    if settings.model_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError(
                "MODEL_PROVIDER=gemini but GEMINI_API_KEY is empty. "
                "Set it in backend/.env, or use MODEL_PROVIDER=mock."
            )
        if not settings.gemini_model:
            raise ValueError("MODEL_PROVIDER=gemini but GEMINI_MODEL is empty.")

        client = AsyncOpenAI(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url,
        )
        # The SDK's built-in tracing targets OpenAI's backend. With Gemini that
        # would both fail auth and leak conversation data, so it stays off.
        set_tracing_disabled(True)
        return OpenAIChatCompletionsModel(
            model=settings.gemini_model,
            openai_client=client,
        )

    raise ValueError(
        f"Unknown MODEL_PROVIDER {settings.model_provider!r}. Expected 'mock' or 'gemini'."
    )
