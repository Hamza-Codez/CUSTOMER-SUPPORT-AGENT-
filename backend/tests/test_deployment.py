"""Refusing to deploy a configuration that would fail quietly.

Every default in this app is chosen so it boots with zero setup: mock provider,
in-memory store, generated signing key, wildcard CORS, demo tokens. That is the
right trade for `uv run uvicorn` and the wrong one for anything with a public
URL — and the failure mode is the dangerous kind, because none of it errors. A
deployed instance on the mock provider answers every question from a lookup
table and reports itself healthy.

So `ENVIRONMENT=production` turns each of those defaults into a startup failure.
These tests are about that refusal, and about it listing everything at once
rather than one item per redeploy.
"""

from __future__ import annotations

import pytest

from app.core.config import _DEMO_TOKENS, Settings

PROD = {"environment": "production"}

# The minimum that is actually deployable, used as the base for the negative
# cases so each one isolates a single problem.
DEPLOYABLE = {
    "environment": "production",
    "database_url": "postgresql://user:pw@host:6543/db",
    "model_provider": "gemini",
    "gemini_api_key": "AIza-not-a-real-key",
    "jwt_secret": "a-real-secret-set-by-the-operator",
    "dev_tokens": "",
    "allowed_origins": "https://app.example.com",
    "public_base_url": "https://api.example.com",
}


class TestDevelopmentIsUntouched:
    def test_the_zero_setup_defaults_are_not_a_problem_in_development(self):
        assert Settings().deployment_problems() == []

    def test_the_signing_key_is_stable_within_a_process(self):
        """A key regenerated per call would sign tokens nothing could verify."""
        settings = Settings(jwt_secret="")
        assert settings.signing_key == settings.signing_key
        assert settings.signing_key

    def test_two_instances_get_different_keys(self):
        """Which is exactly why production has to set one.

        Each serverless instance is its own process, so an unset secret means a
        token minted by one is rejected by the next.
        """
        assert Settings(jwt_secret="").signing_key != Settings(jwt_secret="").signing_key

    def test_a_configured_secret_is_used_verbatim(self):
        assert Settings(jwt_secret="  chosen  ").signing_key == "chosen"


class TestProductionRefusals:
    def test_a_fully_configured_production_setup_passes(self):
        assert Settings(**DEPLOYABLE).deployment_problems() == []

    def test_every_problem_is_reported_at_once(self):
        """Not one per redeploy.

        Someone deploying wants the whole list on the first attempt. Fixing one
        variable, redeploying, and discovering the next is how a ten-minute task
        becomes an afternoon.
        """
        problems = Settings(**PROD).deployment_problems()
        assert len(problems) >= 4

    def test_the_in_memory_store_is_refused(self):
        problems = Settings(**{**DEPLOYABLE, "database_url": ""}).deployment_problems()
        assert any("DATABASE_URL" in p for p in problems)

    def test_the_mock_provider_is_refused(self):
        problems = Settings(
            **{**DEPLOYABLE, "model_provider": "mock"}
        ).deployment_problems()
        assert any("lookup table" in p for p in problems)

    def test_gemini_without_a_key_is_refused(self):
        problems = Settings(
            **{**DEPLOYABLE, "gemini_api_key": ""}
        ).deployment_problems()
        assert any("GEMINI_API_KEY" in p for p in problems)

    def test_an_unset_signing_secret_is_refused(self):
        problems = Settings(**{**DEPLOYABLE, "jwt_secret": ""}).deployment_problems()
        assert any("JWT_SECRET" in p for p in problems)

    def test_the_demo_tokens_are_refused(self):
        """The one that would actually be exploited.

        `ops-token` is a documented string that resolves to an operator. A
        deployment keeping it is one request away from handing a stranger the
        refund queue.
        """
        # The constant the check compares against, not `Settings().dev_tokens` —
        # a local .env may already override it, which would make this test pass
        # by measuring nothing.
        problems = Settings(
            **{**DEPLOYABLE, "dev_tokens": _DEMO_TOKENS}
        ).deployment_problems()
        assert any("ops-token" in p for p in problems)

    def test_replacing_the_demo_tokens_satisfies_it(self):
        assert (
            Settings(
                **{**DEPLOYABLE, "dev_tokens": "s3cr3t-xyz:biz_demo:operator"}
            ).deployment_problems()
            == []
        )

    def test_wildcard_cors_is_refused(self):
        problems = Settings(
            **{**DEPLOYABLE, "allowed_origins": "*"}
        ).deployment_problems()
        assert any("ALLOWED_ORIGINS" in p for p in problems)

    def test_a_plaintext_public_base_url_is_refused(self):
        """It is baked into widget.js and into email links."""
        problems = Settings(
            **{**DEPLOYABLE, "public_base_url": "http://localhost:8000"}
        ).deployment_problems()
        assert any("PUBLIC_BASE_URL" in p for p in problems)

    def test_smtp_without_a_host_is_refused(self):
        problems = Settings(
            **{**DEPLOYABLE, "email_provider": "smtp"}
        ).deployment_problems()
        assert any("SMTP_HOST" in p for p in problems)


class TestCorsParsing:
    def test_a_wildcard_stays_a_wildcard(self):
        assert Settings(allowed_origins="*").cors_origins == ["*"]

    def test_a_list_is_split_and_trimmed(self):
        settings = Settings(
            allowed_origins=" https://a.example/ , https://b.example "
        )
        assert settings.cors_origins == ["https://a.example", "https://b.example"]

    def test_blank_entries_are_dropped(self):
        assert Settings(allowed_origins="https://a.example,,").cors_origins == [
            "https://a.example"
        ]


class TestStartupRefusal:
    def test_the_app_refuses_to_start_when_misconfigured(self, monkeypatch):
        """The check runs in the lifespan, so a bad deploy fails on deploy.

        Checked at startup rather than on the first request: a platform that
        reports the deploy as green and only fails once a customer arrives has
        told you nothing useful.
        """
        from fastapi.testclient import TestClient

        from app.core.config import get_settings
        from app.main import app

        monkeypatch.setenv("ENVIRONMENT", "production")
        get_settings.cache_clear()
        try:
            with pytest.raises(RuntimeError, match="not deployable"):
                with TestClient(app):
                    pass
        finally:
            get_settings.cache_clear()

    def test_the_message_names_every_problem(self, monkeypatch):
        from fastapi.testclient import TestClient

        from app.core.config import get_settings
        from app.main import app

        monkeypatch.setenv("ENVIRONMENT", "production")
        get_settings.cache_clear()
        try:
            with pytest.raises(RuntimeError) as raised:
                with TestClient(app):
                    pass
            message = str(raised.value)
            assert "MODEL_PROVIDER" in message
            assert "JWT_SECRET" in message
            assert "ENVIRONMENT=development" in message  # the way out
        finally:
            get_settings.cache_clear()
