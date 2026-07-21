"""Identity verification — the edge of the system (INTENT §6).

    AUTH_PROVIDER = mock | supabase        (default: mock)

Same switch pattern as `model.py` and `store/__init__.py`, for the same reason:
INTENT §5 requires the whole flow to run with zero external setup, and the PRD
guardrail requires CI to run with no external deps. `mock` satisfies both while
still *requiring* a session, so "unauthenticated calls are refused" stays
provable — an auto-sign-in mock would make the PRD's session metric untestable.

Roles are `customer` (chat only) and `agent` (chat + the audit log). The role is
never taken from a client claim; it is read from the verified token.
"""
from __future__ import annotations

import os
from typing import Literal, Optional

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

Role = Literal["customer", "agent"]
VALID_ROLES = ("customer", "agent")


class User(BaseModel):
    id: str
    email: str
    role: Role


def provider_name() -> str:
    return os.getenv("AUTH_PROVIDER", "mock").lower()


# --- mock provider -----------------------------------------------------------
# Token format:  mock:<role>[:<user id>]     e.g. "mock:agent", "mock:customer:u2"
# Anything else is rejected, so 401 and 403 are both exercisable without
# credentials. Two different ids give two genuinely separate tenants in tests.

def _verify_mock(token: str) -> Optional[User]:
    if not token.startswith("mock:"):
        return None
    parts = token.split(":")
    role = parts[1] if len(parts) > 1 else ""
    if role not in VALID_ROLES:
        return None
    user_id = parts[2] if len(parts) > 2 and parts[2] else f"demo-{role}"
    return User(id=user_id, email=f"{user_id}@example.test", role=role)


# --- supabase provider -------------------------------------------------------

def _verify_supabase(token: str) -> Optional[User]:
    """Verify a Supabase-issued JWT: signature, expiry, and audience.

    The role is read from `app_metadata`, never `user_metadata` — user_metadata
    is writable by the user themselves, so trusting it would let any customer
    promote themselves to agent.
    """
    secret = os.getenv("SUPABASE_JWT_SECRET")
    if not secret:
        raise ValueError(
            "AUTH_PROVIDER=supabase requires SUPABASE_JWT_SECRET "
            "(Supabase dashboard → Project Settings → API → JWT Secret)."
        )
    try:
        import jwt
    except ImportError as exc:  # pragma: no cover - optional extra
        raise ValueError(
            "AUTH_PROVIDER=supabase requires PyJWT: pip install pyjwt"
        ) from exc

    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
    except jwt.PyJWTError:
        return None       # expired, tampered, or simply not ours

    subject = claims.get("sub")
    if not subject:
        return None

    role = (claims.get("app_metadata") or {}).get("role", "customer")
    if role not in VALID_ROLES:
        role = "customer"     # unknown role is never an escalation of privilege

    return User(id=subject, email=claims.get("email") or "", role=role)


def verify_token(token: str) -> Optional[User]:
    provider = provider_name()
    if provider == "mock":
        return _verify_mock(token)
    if provider == "supabase":
        return _verify_supabase(token)
    raise ValueError(f"Unknown AUTH_PROVIDER '{provider}' (use mock | supabase)")


# --- FastAPI dependencies ----------------------------------------------------

def current_user(authorization: str = Header(default="")) -> User:
    """401 for anyone without a valid session. Use on every state-changing route."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = verify_token(authorization[len("Bearer "):].strip())
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_agent(user: User = Depends(current_user)) -> User:
    """403, not 401 — the caller proved who they are, they just aren't allowed."""
    if user.role != "agent":
        raise HTTPException(
            status_code=403,
            detail="This view is restricted to support agents.",
        )
    return user
