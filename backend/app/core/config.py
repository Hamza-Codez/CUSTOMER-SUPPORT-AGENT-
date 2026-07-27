"""Environment configuration.

Every environment choice is an env var. Nothing about a provider, a model name
or a database lives in code, so switching any of them is a config change.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # `protected_namespaces=()` because pydantic reserves the `model_` prefix and
    # our config genuinely needs `model_provider` / `gemini_model`.
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    # Model provider. `mock` is the default so the app boots with zero setup.
    model_provider: Literal["mock", "gemini"] = "mock"

    gemini_api_key: str = ""
    # Verified working 2026-07-26. Note `gemini-2.5-flash` — the value the spec
    # suggested — is still listed by the models endpoint but returns 404 "no
    # longer available to new users", so a pinned version is not automatically
    # the safer choice here. `gemini-flash-latest` is a moving alias; pin it to a
    # dated model once you want reproducible behaviour and can re-verify.
    gemini_model: str = "gemini-flash-latest"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # Empty means the in-memory store. A URL means real Postgres.
    database_url: str = ""

    # Dev-only static tokens: "<token>:<business_id>:<role>", comma separated.
    dev_tokens: str = "demo-token:biz_demo:customer,ops-token:biz_demo:operator"

    # Money-moving limits, enforced in code by the refund tool guardrail — never
    # by the prompt. Above the cap, or outside the window, the run pauses for a
    # human instead of executing.
    auto_refund_cap: float = 25.00
    refund_window_days: int = 30

    @property
    def store_kind(self) -> Literal["mock", "postgres"]:
        return "postgres" if self.database_url.strip() else "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()
