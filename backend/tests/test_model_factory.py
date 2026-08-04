"""Provider factory tests.

The factory is the swappable seam for the riskiest dependency, so its failure
modes need to be loud and specific rather than a generic crash at request time.

LIGHTRON runs two tiers — reasoning decides, voice speaks — and both are on Groq.
Gemini keeps embeddings only, because its 20-requests-a-day free tier cannot be
the path a real customer's question takes.
"""

from __future__ import annotations

import pytest

from agents import OpenAIChatCompletionsModel

from app.core.config import Settings, get_settings
from app.core.mock_model import MockModel
from app.core.model import reasoning_model, voice_model


def _reset(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    reasoning_model.cache_clear()
    voice_model.cache_clear()


class TestTheMockPath:
    """Still available, never the shipped answer path.

    `ENVIRONMENT=production` refuses to start on it; it exists so the repo boots
    unconfigured and so tool wiring can be exercised without spending a request.
    """

    def test_both_tiers_default_to_mock_so_the_app_boots_unconfigured(
        self, monkeypatch
    ):
        _reset(monkeypatch, MODEL_PROVIDER="mock")
        assert isinstance(reasoning_model(), MockModel)
        assert isinstance(voice_model(), MockModel)


class TestTheGroqTiers:
    def test_reasoning_without_a_key_says_which_key(self, monkeypatch):
        _reset(monkeypatch, MODEL_PROVIDER="gemini", GROQ_API_KEY="")
        with pytest.raises(ValueError, match="GROQ_API_KEY is empty"):
            reasoning_model()

    def test_voice_without_a_key_says_which_key(self, monkeypatch):
        _reset(monkeypatch, MODEL_PROVIDER="gemini", GROQ_API_KEY="")
        with pytest.raises(ValueError, match="GROQ_API_KEY is empty"):
            voice_model()

    def test_both_tiers_build_against_groq(self, monkeypatch):
        _reset(monkeypatch, MODEL_PROVIDER="gemini", GROQ_API_KEY="test-key-not-real")
        assert isinstance(reasoning_model(), OpenAIChatCompletionsModel)
        assert isinstance(voice_model(), OpenAIChatCompletionsModel)

    def test_the_tiers_can_run_different_models(self, monkeypatch):
        """The reason they are separate factories.

        Changing how the product *sounds* must not require touching how it
        *thinks*.
        """
        _reset(
            monkeypatch,
            MODEL_PROVIDER="gemini",
            GROQ_API_KEY="test-key-not-real",
            GROQ_REASONING_MODEL="reasoning-model-id",
            GROQ_VOICE_MODEL="voice-model-id",
        )
        assert reasoning_model().model == "reasoning-model-id"
        assert voice_model().model == "voice-model-id"

    def test_model_ids_are_configuration_not_code(self):
        """Groq retires model IDs without notice, so neither is pinned in code."""
        settings = Settings(
            groq_reasoning_model="something-new",
            groq_voice_model="something-else",
            _env_file=None,
        )
        assert settings.groq_reasoning_model == "something-new"
        assert settings.groq_voice_model == "something-else"


class TestStoreSelection:
    def test_empty_database_url_means_mock_store(self):
        assert Settings(database_url="", _env_file=None).store_kind == "mock"

    def test_a_dsn_means_postgres(self):
        assert (
            Settings(
                database_url="postgresql://u:p@host:5432/db", _env_file=None
            ).store_kind
            == "postgres"
        )

    def test_whitespace_is_not_a_dsn(self):
        assert Settings(database_url="   ", _env_file=None).store_kind == "mock"
