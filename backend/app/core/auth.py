"""Authentication and the tenant context.

Phase 1 uses static dev tokens from the environment. Real signup/login and JWT
issuance arrive with the auth phase; what matters now is that the shape below —
a `TenantContext` resolved per request — is already the contract, so swapping in
real tokens later does not touch the tool layer.

Security note: `business_id` is resolved from the caller's token and travels in
the run context. It is never a tool argument, so the model cannot influence
which tenant's data a tool reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import get_settings
from app.db import Store, get_store


@dataclass
class TenantContext:
    """Passed to `Runner.run(context=...)` and read by tools via `RunContextWrapper`."""

    business_id: str
    role: str
    actor: str
    store: Store


def _parse_dev_tokens(raw: str) -> dict[str, tuple[str, str]]:
    """"tok:biz:role,tok2:biz2:role2" -> {tok: (biz, role)}."""
    table: dict[str, tuple[str, str]] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) != 3:
            raise ValueError(
                f"Malformed DEV_TOKENS entry {entry!r}; expected '<token>:<business_id>:<role>'"
            )
        token, business_id, role = (p.strip() for p in parts)
        table[token] = (business_id, role)
    return table


async def require_tenant(
    authorization: Annotated[str | None, Header()] = None,
) -> TenantContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token. Send 'Authorization: Bearer <token>'.",
        )

    token = authorization.split(" ", 1)[1].strip()
    tokens = _parse_dev_tokens(get_settings().dev_tokens)
    if token not in tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown token.",
        )

    business_id, role = tokens[token]
    return TenantContext(
        business_id=business_id,
        role=role,
        actor=f"{role}:{token}",
        store=get_store(),
    )


TenantDep = Annotated[TenantContext, Depends(require_tenant)]
