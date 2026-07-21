"""Test helpers for the authenticated API.

Every state-changing endpoint now requires a session (PRD v2), so tests need an
identity. `AUTH_PROVIDER=mock` accepts `Bearer mock:<role>[:<id>]` and rejects
everything else, which keeps 401 and 403 provable without credentials.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

AGENT = "Bearer mock:agent"
CUSTOMER = "Bearer mock:customer"

AGENT_ID = "demo-agent"
CUSTOMER_ID = "demo-customer"


def token(role: str = "agent", user_id: str | None = None) -> str:
    return f"Bearer mock:{role}" + (f":{user_id}" if user_id else "")


def authed_client(app, header: str = AGENT) -> TestClient:
    """A client that carries an identity on every request."""
    return TestClient(app, headers={"Authorization": header})


def session_key(session_id: str, user_id: str = AGENT_ID) -> str:
    """Memory is scoped per user — `main._session_key` composes the stored key as
    `<user id>:<session id>`. Tests assert against the scoped key on purpose: it
    is what proves two users can't read each other's conversation."""
    return f"{user_id}:{session_id}"
