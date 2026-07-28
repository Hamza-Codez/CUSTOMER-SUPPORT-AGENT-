"""Test fixtures.

Tests run on the mock provider and the in-memory store, so the whole suite is
CI-safe and needs no API key and no database. The Postgres-specific tests in
test_postgres.py opt in separately when a real DSN is configured.
"""

from __future__ import annotations

import json
import os

# Set before app imports so cached settings pick these up. Real env vars take
# precedence over .env, which keeps the suite hermetic even once a developer has
# filled in a real DATABASE_URL locally.
os.environ["MODEL_PROVIDER"] = "mock"
os.environ["DATABASE_URL"] = ""
os.environ["DEV_TOKENS"] = (
    "demo-token:biz_demo:customer,other-token:biz_other:customer,ops-token:biz_demo:operator"
)

import pytest  # noqa: E402
from agents.tool_context import ToolContext  # noqa: E402

from app.agents.orchestrator import get_entry_agent  # noqa: E402
from app.core.auth import TenantContext  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.model import gemini_model  # noqa: E402
from app.db import set_store  # noqa: E402
from app.db.mock_store import MockStore  # noqa: E402


@pytest.fixture(autouse=True)
def store() -> MockStore:
    """A fresh store per test, with every cached singleton reset around it."""
    get_settings.cache_clear()
    gemini_model.cache_clear()
    get_entry_agent.cache_clear()

    s = MockStore()
    set_store(s)
    yield s
    set_store(None)

    get_settings.cache_clear()
    gemini_model.cache_clear()
    get_entry_agent.cache_clear()


@pytest.fixture
def tenant(store: MockStore) -> TenantContext:
    return TenantContext(
        business_id="biz_demo",
        role="customer",
        actor="customer:demo-token",
        store=store,
    )


@pytest.fixture
def other_tenant(store: MockStore) -> TenantContext:
    return TenantContext(
        business_id="biz_other",
        role="customer",
        actor="customer:other-token",
        store=store,
    )


async def invoke(tool, ctx: TenantContext, **kwargs):
    """Invoke a function tool the way the Runner does.

    Going through `on_invoke_tool` rather than calling a plain function means the
    tool's generated JSON schema and argument validation are exercised too.

    The SDK passes a `ToolContext` (not a bare `RunContextWrapper`) — its error
    path reads `run_config` off the context, so the narrower type fails only when
    something has already gone wrong, which is the worst time to lose the message.
    """
    arguments = json.dumps(kwargs)
    tool_context = ToolContext(
        context=ctx,
        tool_name=tool.name,
        tool_call_id="test-call",
        tool_arguments=arguments,
    )
    return await tool.on_invoke_tool(tool_context, arguments)
