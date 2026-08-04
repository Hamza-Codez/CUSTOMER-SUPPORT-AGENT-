"""The provider factories — the single place a model is constructed.

Two tiers, because they are asked for different things:

- **Reasoning** decides. Triage, tool selection, handoffs, rulings. It needs
  reliable tool-calling far more than it needs elegant prose.
- **Voice** speaks. It turns facts that have already been decided into something
  a person would actually say. It never calls a tool, so it cannot invent an
  order or a policy — by the time it runs, every fact is settled.

Both run on **Groq**. The spec originally put reasoning on Gemini, and that
separation is architecturally cleaner, but Gemini's free tier is 20 requests a
day: at one to two calls per turn that is roughly ten conversations for the
entire platform, which makes a live product impossible before it makes a clean
architecture possible. Groq's free tier is large enough to actually run on, its
tool-calling is solid, and keeping both tiers on one provider removes a
cross-provider hop from every turn.

Gemini keeps embeddings, which draw on a **separate quota** — so retrieval stays
real on a day the chat budget is gone. That is the one place the split earns its
keep.

`mock` remains available and is never the shipped answer path: `ENVIRONMENT=
production` refuses to start on it. It exists so the repo boots unconfigured and
so tool wiring can be exercised without spending a request.
"""

from __future__ import annotations

from functools import lru_cache

from agents import AsyncOpenAI, OpenAIChatCompletionsModel, set_tracing_disabled
from agents.models.interface import Model

from app.core.config import get_settings

# Groq's OpenAI-compatible endpoint. Both tiers use the same SDK pattern —
# AsyncOpenAI client into OpenAIChatCompletionsModel, never a bare model string,
# which would send the call to OpenAI instead.
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def _groq_client() -> AsyncOpenAI:
    settings = get_settings()
    if not settings.groq_api_key:
        raise ValueError(
            "GROQ_API_KEY is empty. LIGHTRON runs on Groq for both reasoning and "
            "voice — set it in backend/.env, or use MODEL_PROVIDER=mock for "
            "wiring-only work."
        )
    # The SDK's tracing uploads to OpenAI's backend, which we never authenticate
    # against. With a third-party provider that would both fail auth and ship
    # conversation content somewhere it does not belong.
    set_tracing_disabled(True)
    return AsyncOpenAI(api_key=settings.groq_api_key, base_url=GROQ_BASE_URL)


@lru_cache
def reasoning_model() -> Model:
    """The tier that decides. Tool-calling and handoffs run here."""
    settings = get_settings()

    if settings.model_provider == "mock":
        from app.core.mock_model import MockModel

        set_tracing_disabled(True)
        return MockModel()

    return OpenAIChatCompletionsModel(
        model=settings.groq_reasoning_model,
        openai_client=_groq_client(),
    )


@lru_cache
def voice_model() -> Model:
    """The tier that speaks.

    Deliberately a separate factory even though it currently points at the same
    provider: the two are tuned independently, and the voice tier is the one that
    would move to a different model to change how the product *sounds* without
    touching how it *thinks*.
    """
    settings = get_settings()

    if settings.model_provider == "mock":
        from app.core.mock_model import MockModel

        set_tracing_disabled(True)
        return MockModel()

    return OpenAIChatCompletionsModel(
        model=settings.groq_voice_model,
        openai_client=_groq_client(),
    )


# Kept so existing imports resolve while the agents are migrated onto the two
# tiers above. New code should ask for the tier it means.
gemini_model = reasoning_model
