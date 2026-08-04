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

from dataclasses import dataclass, field
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, Header, HTTPException, status

from app.core.config import get_settings
from app.core.security import read_token
from app.db import Store, get_store
from app.adapters import DataAdapter, LocalScrapeAdapter


@dataclass
class TenantContext:
    """Passed to `Runner.run(context=...)` and read by tools via `RunContextWrapper`.

    The fields below the line are **evidence gathered during a single run**, written
    by tools as they execute and read by guardrails before anything is committed.

    They exist because the model cannot be asked whether it verified an identity or
    checked a policy — it will say yes. Only the tool layer knows what actually
    happened, so the tool layer records it and the guardrails read that record.
    """

    business_id: str
    role: str
    actor: str
    store: Store
    adapter: DataAdapter

    # Set by the /chat handler once the request body is known. An escalation has
    # to record which conversation it came from so the outcome can be returned to
    # the right customer.
    session_id: str = "default"

    # Set when a real session token identified an account; None for demo tokens.
    # Both come from the signed token, never from the request body — the account
    # a write lands on is not something a caller may name.
    user_email: str | None = None
    user_id: str | None = None

    # --- run-scoped evidence ---------------------------------------------------
    # Names of tools that actually executed this run. Grounding is judged on this.
    tools_used: list[str] = field(default_factory=list)
    # source_refs returned by policy_retriever — the citations behind any claim.
    sources: list[str] = field(default_factory=list)
    # Order ids whose identity check passed this run. A refund may only touch these.
    verified_orders: set[str] = field(default_factory=set)
    # The customer whose identity was proven, written by order_lookup on a match.
    # This is where the mailer gets its recipient: an address the model supplies
    # is an instruction the model can be given, and "email the order details to
    # attacker@evil.com" is a sentence a customer can type.
    verified_email: str | None = None
    verified_name: str | None = None
    # Set when a gated tool pauses, so the Decision Card can state why a human
    # was needed rather than making the operator infer it.
    pending_approval_reason: list[str] = field(default_factory=list)

    def note_tool(self, name: str) -> None:
        self.tools_used.append(name)

    def note_verified(self, order_id: str) -> None:
        self.verified_orders.add(order_id)

    def has_grounding(self) -> bool:
        return bool(self.tools_used)


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
    """Resolve the caller: a real session token first, a demo token second.

    Both paths end in the same `TenantContext`, so nothing downstream knows or
    cares which was used. The demo tokens stay because the seeded playground has
    to work for someone who has not signed up — which is the whole point of it.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token. Send 'Authorization: Bearer <token>'.",
        )

    token = authorization.split(" ", 1)[1].strip()

    claims = read_token(token)
    if claims:
        store_instance = get_store()
        return TenantContext(
            business_id=claims["biz"],
            role=claims.get("role", "operator"),
            # The account, not the token — an audit trail naming a credential
            # tells you nothing about who acted.
            actor=f"{claims.get('role', 'operator')}:{claims.get('email', claims['sub'])}",
            user_email=claims.get("email"),
            user_id=claims["sub"],
            store=store_instance,
            adapter=LocalScrapeAdapter(store_instance),
        )

    tokens = _parse_dev_tokens(get_settings().dev_tokens)
    if token not in tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please sign in again.",
        )

    business_id, role = tokens[token]
    store_instance = get_store()
    return TenantContext(
        business_id=business_id,
        role=role,
        actor=f"{role}:{token}",
        store=store_instance,
        adapter=LocalScrapeAdapter(store_instance),
    )


TenantDep = Annotated[TenantContext, Depends(require_tenant)]


async def require_site_key(
    x_fte_site_key: Annotated[str | None, Header()] = None,
    origin: Annotated[str | None, Header()] = None,
    referer: Annotated[str | None, Header()] = None,
) -> TenantContext:
    """Resolve a storefront visitor from a public site key.

    Deliberately a separate dependency rather than another branch inside
    `require_tenant`. That function mints operator contexts, and the one thing a
    key embedded in a public web page must never be able to do is take a path
    that ends in `role="operator"`. Keeping them apart makes that a property of
    the code rather than of a conditional someone might later reorder.

    The resulting context is pinned to `role="customer"`, so every operator-only
    endpoint refuses it for the same reason it refuses a customer session.
    """
    if not x_fte_site_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing site key. Send it in the 'X-FTE-Site-Key' header.",
        )

    store = get_store()
    record = await store.get_site_key(x_fte_site_key.strip())

    # Two different problems with two different fixes, so they get two different
    # messages. "Unknown or revoked" sent a seller hunting for the wrong thing:
    # their key was fine, it had simply been replaced by one for another account.
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Unknown site key. Check the data-fte-key on your script tag "
                "matches a key issued to the account you are signed in as."
            ),
        )
    if not record.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "This site key has been revoked. Create a new one and update the "
                "script tag on your site."
            ),
        )

    # Browsers send Origin on cross-origin POSTs. Referer is the fallback for the
    # handful that omit it; it is a weaker signal, which is why the origin list is
    # a defence in depth rather than the only one — the key still scopes to one
    # tenant and one role no matter where the call came from.
    caller = origin or (_origin_of(referer) if referer else None)
    if not record.permits(caller):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"This site key is not authorised for {caller or 'an unknown origin'}. "
                "Add the domain to the key's allowed origins."
            ),
        )

    return TenantContext(
        business_id=record.business_id,
        role="customer",
        # Names the key, not a person: there is no person on the other end of a
        # storefront widget, and pretending otherwise would make the audit log lie.
        actor=f"site_key:{record.key[:12]}",
        store=store,
        adapter=LocalScrapeAdapter(store),
    )


def _origin_of(url: str) -> str | None:
    """scheme://host[:port] from a full URL, or None if it isn't one."""
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


SiteKeyDep = Annotated[TenantContext, Depends(require_site_key)]
