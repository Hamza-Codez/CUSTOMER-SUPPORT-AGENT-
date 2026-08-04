"""Environment configuration.

Every environment choice is an env var. Nothing about a provider, a model name
or a database lives in code, so switching any of them is a config change.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

# The built-in demo credentials, named here so a deployment check can spot
# that they were never changed. Kept in step with the field default below.
_DEMO_TOKENS = "demo-token:biz_demo:customer,ops-token:biz_demo:operator"


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

    # --- Groq: both LIGHTRON tiers ------------------------------------------
    #
    # Reasoning and voice both run here. The spec put reasoning on Gemini, but
    # its free tier is 20 requests/day — roughly ten conversations for the whole
    # platform — which rules it out as the path a real customer's question takes.
    # Gemini keeps embeddings, which draw on a separate quota.
    #
    # Groq's model IDs churn and old ones are retired without notice, so both are
    # env-configurable and neither is pinned in code. Verify against Groq's
    # models page rather than trusting these defaults.
    groq_api_key: str = ""
    groq_reasoning_model: str = "openai/gpt-oss-120b"
    groq_voice_model: str = "openai/gpt-oss-20b"

    gemini_api_key: str = ""
    # Verified working 2026-07-26. Note `gemini-2.5-flash` — the value the spec
    # suggested — is still listed by the models endpoint but returns 404 "no
    # longer available to new users", so a pinned version is not automatically
    # the safer choice here. `gemini-flash-latest` is a moving alias; pin it to a
    # dated model once you want reproducible behaviour and can re-verify.
    gemini_model: str = "gemini-flash-latest"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # Retrieval. Independent of MODEL_PROVIDER: Gemini embeddings use a separate
    # quota bucket, so retrieval can be real on a day the chat model is exhausted.
    embedding_provider: Literal["mock", "gemini"] = "mock"
    embedding_model: str = "gemini-embedding-001"
    # 1536 rather than the native 3072: pgvector cannot index above 2000
    # dimensions, and Gemini supports asking for fewer. Changing this requires
    # re-ingesting, since the column type is fixed to it.
    embedding_dim: int = 1536

    # Retrieval admission. A passage is returned if the keyword signal clears its
    # floor OR the vector signal clears this one — see app/rag/retriever.py.
    #
    # 0.65 comes from measurement, not taste. Against this corpus with
    # gemini-embedding-001 at 1536 dims: on-topic questions scored 0.607-0.780,
    # off-domain ones 0.381-0.582. Those ranges only separate by 0.025, which is
    # far too narrow to place a threshold between them and call it rejection. So
    # this floor is set well *above* the highest observed miss instead: vectors
    # only ever add a passage they are confident about, and keyword retrieval —
    # which is properly calibrated for this corpus — does the rejecting.
    #
    # The same value leaves `mock` keyword-only, since the mock embedder tops out
    # around 0.36. Re-measure before lowering it for a different provider.
    retrieval_use_vectors: bool = True
    retrieval_vector_floor: float = 0.65

    # --- Deployment -------------------------------------------------------------
    #
    # `development` keeps every zero-setup default: mock provider, in-memory
    # store, a generated signing secret. `production` refuses all three, because
    # each of them fails silently rather than loudly — a deployed app on the mock
    # provider looks like it works and answers from a lookup table.
    environment: Literal["development", "production"] = "development"

    # Backing store for `signing_key`'s per-process fallback.
    _ephemeral_key: str | None = PrivateAttr(default=None)

    # Origins the browser API is served to. `*` is the development default and is
    # rejected in production: the site key already scopes a widget to its own
    # origins, but the dashboard's own endpoints are bearer-token routes that
    # should not be callable from any page on the internet.
    allowed_origins: str = "*"

    # Empty means the in-memory store. A URL means real Postgres.
    database_url: str = ""

    # Connection pool bounds. Small by default because a serverless platform runs
    # many instances of this process at once, and a pool sized for one long-lived
    # server becomes a connection-limit outage when fifty of them wake up.
    db_pool_min: int = 1
    db_pool_max: int = 5

    # Set when the DSN points at a *transaction* pooler (Supabase port 6543,
    # pgBouncer, pgcat). Those multiplex one server connection across clients per
    # transaction, so a prepared statement cached by one client is not there for
    # the next — asyncpg must be told to stop caching them, or you get
    # intermittent "prepared statement _asyncpg_stmt_ does not exist" under load.
    db_transaction_pooler: bool = False

    # Signs session tokens. Empty means "generate one for this process" — see
    # `signing_key`. Left empty the app still boots with zero setup, at the cost
    # of every restart signing everyone out.
    #
    # On a serverless platform that is worse than inconvenient: each instance
    # generates its own, so a token minted by one is rejected by the next, and
    # sign-ins fail at random. `production` therefore requires it explicitly.
    #
    # Stored as the raw value rather than pre-filled by a default factory, so
    # "was this configured?" stays a question the code can answer.
    jwt_secret: str = ""

    # Static tokens for the demo and the test suite. Real accounts authenticate
    # with a JWT from /auth/login; these remain so the seeded demo works without
    # anyone signing up.
    dev_tokens: str = _DEMO_TOKENS

    # --- Email ----------------------------------------------------------------
    # `mock` records the message in the store and sends nothing, so the whole
    # flow — including the feedback link — is demoable and testable without an
    # SMTP account, and no test can accidentally email a real person.
    email_provider: Literal["mock", "smtp"] = "mock"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    email_from: str = "Aeron Home Goods <support@example.com>"
    # Shown in the email header. Per-business branding moves to the DB at onboarding.
    business_display_name: str = "Aeron Home Goods"
    # Where the one-click feedback links point. The API serves them directly, so
    # a rating works straight from an email client with no frontend involved.
    public_base_url: str = "http://localhost:8000"

    # Money-moving limits, enforced in code by the refund tool guardrail — never
    # by the prompt. Above the cap, or outside the window, the run pauses for a
    # human instead of executing.
    auto_refund_cap: float = 25.00
    refund_window_days: int = 30

    # Model pricing, per million tokens, for cost-per-conversation (SPEC §16.5).
    # Zero by default and reported as unavailable rather than as 0.00 — a cost
    # nobody has configured is not a cost of nothing.
    cost_per_mtok_input: float = 0.0
    cost_per_mtok_output: float = 0.0

    @property
    def store_kind(self) -> Literal["mock", "postgres"]:
        return "postgres" if self.database_url.strip() else "mock"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def signing_key(self) -> str:
        """The key session tokens are actually signed with.

        Falls back to a value generated once per process. Cached on the settings
        instance rather than regenerated per call — otherwise every token would
        be signed with a key that no longer exists by the time it is verified.
        """
        configured = self.jwt_secret.strip()
        if configured:
            return configured
        if self._ephemeral_key is None:
            self._ephemeral_key = secrets.token_urlsafe(48)
        return self._ephemeral_key

    @property
    def cors_origins(self) -> list[str]:
        """Parsed allowed origins. `*` stays a single wildcard entry."""
        raw = self.allowed_origins.strip()
        if raw == "*":
            return ["*"]
        return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]

    def deployment_problems(self) -> list[str]:
        """Everything about this configuration that would fail quietly in production.

        Returned as a list rather than raised one at a time: someone deploying
        wants the whole list on the first attempt, not to fix one variable, redeploy,
        and discover the next.

        Every item here is something that *works* in the sense of not erroring —
        which is exactly why it needs a check. A deployed app on the mock provider
        answers every question from a lookup table and looks entirely healthy.
        """
        if not self.is_production:
            return []

        problems: list[str] = []

        if self.store_kind == "mock":
            problems.append(
                "DATABASE_URL is unset, so this would run on the in-memory store: "
                "every request gets a different empty database and nothing is kept."
            )
        if self.model_provider == "mock":
            problems.append(
                "MODEL_PROVIDER=mock answers from a deterministic lookup table. "
                "It will look like it is working. Set MODEL_PROVIDER=gemini."
            )
        if self.model_provider != "mock" and not self.groq_api_key.strip():
            problems.append(
                "GROQ_API_KEY is empty. Both LIGHTRON tiers run on Groq, so "
                "without it every customer question fails."
            )
        if self.embedding_provider == "gemini" and not self.gemini_api_key.strip():
            problems.append("EMBEDDING_PROVIDER=gemini but GEMINI_API_KEY is empty.")

        # The one that would actually be exploited. These are documented,
        # guessable strings, and `ops-token` resolves to an operator — so a
        # deployment that keeps them is one `Authorization: Bearer ops-token`
        # away from handing a stranger the refund queue.
        if self.dev_tokens.strip() == _DEMO_TOKENS:
            problems.append(
                "DEV_TOKENS still holds the built-in demo credentials, and "
                "'ops-token' grants operator access to biz_demo. Set DEV_TOKENS="
                " (empty) to disable them, or to your own unguessable values. "
                "Note the seeded /demo playground stops working when you do — it "
                "authenticates with exactly these."
            )

        if not self.jwt_secret.strip():
            problems.append(
                "JWT_SECRET is unset, so each instance generates its own. On a "
                "serverless platform a token issued by one instance is rejected "
                "by the next and sign-ins fail at random."
            )

        if self.cors_origins == ["*"]:
            problems.append(
                "ALLOWED_ORIGINS=* exposes the bearer-token dashboard routes to "
                "any page on the internet. List your frontend's origins."
            )
        if self.public_base_url.startswith("http://"):
            problems.append(
                f"PUBLIC_BASE_URL is {self.public_base_url!r}. It is baked into "
                "widget.js and into email links, so it has to be the public HTTPS "
                "address of this API."
            )
        if self.email_provider == "smtp" and not self.smtp_host.strip():
            problems.append("EMAIL_PROVIDER=smtp but SMTP_HOST is empty.")

        return problems



@lru_cache
def get_settings() -> Settings:
    return Settings()
