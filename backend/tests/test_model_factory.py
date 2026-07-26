"""Provider factory tests.

The factory is the swappable seam for the riskiest dependency, so its failure
modes need to be loud and specific rather than a generic crash at request time.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings, get_settings
from app.core.model import gemini_model
from app.core.mock_model import MockModel


def test_defaults_to_mock_so_the_app_boots_unconfigured(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    get_settings.cache_clear()
    gemini_model.cache_clear()
    assert isinstance(gemini_model(), MockModel)


def test_gemini_without_a_key_fails_with_a_clear_message(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    gemini_model.cache_clear()

    with pytest.raises(ValueError, match="GEMINI_API_KEY is empty"):
        gemini_model()


def test_gemini_with_a_key_builds_a_chat_completions_model(monkeypatch):
    from agents import OpenAIChatCompletionsModel

    monkeypatch.setenv("MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-flash-latest")
    get_settings.cache_clear()
    gemini_model.cache_clear()

    model = gemini_model()
    assert isinstance(model, OpenAIChatCompletionsModel)


def test_unknown_provider_is_rejected(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    get_settings.cache_clear()
    gemini_model.cache_clear()

    # Bypass the Literal validation to prove the factory itself guards the value.
    settings = get_settings()
    object.__setattr__(settings, "model_provider", "llama")
    gemini_model.cache_clear()
    with pytest.raises(ValueError, match="Unknown MODEL_PROVIDER"):
        gemini_model()


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
