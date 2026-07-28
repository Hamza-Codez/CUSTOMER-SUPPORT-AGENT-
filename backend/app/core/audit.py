"""Audit logging.

Every sensitive read and write goes through here. The rule is that a tool records
what it did *including when it refused*: a denied identity check is exactly the
event worth having in the log.
"""

from __future__ import annotations

from typing import Any

from app.core.auth import TenantContext
from app.db import AuditEntry


async def record(
    ctx: TenantContext,
    *,
    action: str,
    target: str,
    outcome: str,
    **detail: Any,
) -> None:
    await ctx.store.write_audit(
        AuditEntry(
            business_id=ctx.business_id,
            actor=ctx.actor,
            action=action,
            target=target,
            outcome=outcome,
            detail=detail,
        )
    )
