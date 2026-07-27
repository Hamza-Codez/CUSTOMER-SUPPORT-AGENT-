"""Postgres parity tests.

Skipped unless a real DATABASE_URL is configured in backend/.env. When it is,
these run the *same* assertions the mock store passes, which is the only way to
know the two implementations genuinely agree — a store that has only ever been
exercised through a fake is a store nobody has tested.

Run with:  uv run pytest tests/test_postgres.py -v
"""

from __future__ import annotations

import pytest
from dotenv import dotenv_values

from app.core.auth import TenantContext
from app.core.config import BACKEND_DIR
from app.db.postgres_store import PostgresStore
from app.db.session_store import StoreSession
from app.schemas import OrderLookupResult
from app.tools.orders import order_lookup
from tests.conftest import invoke

# Read the DSN from .env directly: conftest deliberately blanks DATABASE_URL in
# the environment to keep the rest of the suite hermetic.
DSN = (dotenv_values(BACKEND_DIR / ".env").get("DATABASE_URL") or "").strip()

pytestmark = pytest.mark.skipif(
    not DSN, reason="No DATABASE_URL in backend/.env — Postgres tests skipped"
)


@pytest.fixture
async def pg():
    store = PostgresStore(DSN)
    await store.connect()
    await store.apply_schema(seed=True)
    yield store
    await store.close()


@pytest.fixture
def pg_tenant(pg):
    return TenantContext("biz_demo", "customer", "customer:pg-test", pg)


async def test_connects_and_reports_healthy(pg):
    assert await pg.health() is True


async def test_seed_data_matches_the_mock_store(pg):
    """The two stores must describe the same world, or tests prove nothing."""
    from app.db.mock_store import MockStore

    mock = MockStore()
    for business_id, order_id in [
        ("biz_demo", "ORD-1001"),
        ("biz_demo", "ORD-1002"),
        ("biz_demo", "ORD-1003"),
        ("biz_demo", "ORD-1004"),
        ("biz_other", "ORD-1002"),
    ]:
        from_pg = await pg.get_order(business_id, order_id)
        from_mock = await mock.get_order(business_id, order_id)
        assert from_pg == from_mock, f"{business_id}/{order_id} differs between stores"


async def test_unknown_order_returns_none(pg):
    assert await pg.get_order("biz_demo", "ORD-0000") is None


async def test_products_match_the_mock_store(pg):
    """Including the jsonb attributes map, which is where a coercion bug would hide."""
    from app.db.mock_store import MockStore

    mock = MockStore()
    for business_id in ("biz_demo", "biz_other"):
        from_pg = await pg.list_products(business_id)
        from_mock = await mock.list_products(business_id)
        assert [p.product_id for p in from_pg] == [p.product_id for p in from_mock]
        assert from_pg == from_mock, f"products differ for {business_id}"


async def test_policies_match_the_mock_store(pg):
    from app.db.mock_store import MockStore

    mock = MockStore()
    for business_id in ("biz_demo", "biz_other"):
        from_pg = await pg.list_policies(business_id)
        from_mock = await mock.list_policies(business_id)
        assert sorted(p.source_ref for p in from_pg) == sorted(
            p.source_ref for p in from_mock
        )
        assert set(from_pg) == set(from_mock), f"policies differ for {business_id}"


async def test_catalogue_and_policies_are_tenant_scoped(pg):
    demo_products = {p.product_id for p in await pg.list_products("biz_demo")}
    other_products = {p.product_id for p in await pg.list_products("biz_other")}
    assert "PRD-OTHER-1" not in demo_products
    assert demo_products.isdisjoint(other_products)

    demo_policies = {p.source_ref for p in await pg.list_policies("biz_demo")}
    assert "other-tenant.md#fixture" not in demo_policies


async def test_tenancy_is_enforced_in_sql(pg):
    """ORD-1002 exists for both tenants with different statuses."""
    mine = await pg.get_order("biz_demo", "ORD-1002")
    theirs = await pg.get_order("biz_other", "ORD-1002")
    assert mine.status == "in_transit"
    assert theirs.status == "cancelled"


class TestToolAgainstPostgres:
    async def test_found(self, pg_tenant):
        result: OrderLookupResult = await invoke(
            order_lookup, pg_tenant, order_id="ORD-1002", email="ayesha.k@example.com"
        )
        assert result.outcome == "found"
        assert result.order.carrier == "FedEx"
        assert result.order.item_count == 2

    async def test_identity_mismatch(self, pg_tenant):
        result = await invoke(
            order_lookup, pg_tenant, order_id="ORD-1002", email="attacker@example.com"
        )
        assert result.outcome == "identity_mismatch"
        assert result.order is None

    async def test_not_found(self, pg_tenant):
        result = await invoke(
            order_lookup, pg_tenant, order_id="ORD-9999", email="ayesha.k@example.com"
        )
        assert result.outcome == "not_found"


class TestCatalogToolsAgainstPostgres:
    """Retrieval must rank identically on either store — that is the whole point
    of doing the ranking in one place rather than in SQL."""

    async def test_product_search(self, pg_tenant):
        from app.tools.products import product_catalog

        result = await invoke(product_catalog, pg_tenant, query="lumbar cushion")
        assert result.outcome == "found"
        assert result.products[0].product_id == "PRD-CUSH-1"
        assert result.products[0].attributes["fill"] == "Memory foam"

    async def test_product_miss(self, pg_tenant):
        from app.tools.products import product_catalog

        result = await invoke(product_catalog, pg_tenant, query="scuba diving gear")
        assert result.outcome == "no_match"

    async def test_policy_retrieval_cites_a_source(self, pg_tenant):
        from app.tools.policies import policy_retriever

        result = await invoke(
            policy_retriever, pg_tenant, question="how long does dispatch take?"
        )
        assert result.outcome == "found"
        assert result.passages[0].source_ref == "shipping-policy.md#dispatch"

    async def test_policy_miss(self, pg_tenant):
        from app.tools.policies import policy_retriever

        result = await invoke(
            policy_retriever, pg_tenant, question="do you accept cryptocurrency?"
        )
        assert result.outcome == "no_match"
        assert result.passages == []


class TestAuditPersistence:
    async def test_audit_row_is_written_and_readable(self, pg, pg_tenant):
        await invoke(
            order_lookup, pg_tenant, order_id="ORD-1001", email="ayesha.k@example.com"
        )
        entries = await pg.recent_audit("biz_demo", limit=5)
        assert any(
            e.action == "order_lookup" and e.target == "ORD-1001" and e.outcome == "found"
            for e in entries
        )

    async def test_jsonb_detail_round_trips(self, pg, pg_tenant):
        await invoke(
            order_lookup, pg_tenant, order_id="ORD-1002", email="nope@example.com"
        )
        entry = (await pg.recent_audit("biz_demo", limit=1))[0]
        assert isinstance(entry.detail, dict)
        assert entry.detail["supplied_email"] == "nope@example.com"


class TestSessionPersistence:
    async def test_round_trip_and_ordering(self, pg):
        s = StoreSession("pg-session-test", "biz_demo", pg)
        await s.clear_session()
        await s.add_items([{"role": "user", "content": "one"}])
        await s.add_items([{"role": "assistant", "content": "two"}])

        assert [i["content"] for i in await s.get_items()] == ["one", "two"]
        assert [i["content"] for i in await s.get_items(limit=1)] == ["two"]

        assert (await s.pop_item())["content"] == "two"
        await s.clear_session()
        assert await s.get_items() == []

    async def test_tenant_isolation(self, pg):
        mine = StoreSession("pg-shared", "biz_demo", pg)
        theirs = StoreSession("pg-shared", "biz_other", pg)
        await mine.clear_session()
        await theirs.clear_session()

        await mine.add_items([{"role": "user", "content": "private"}])
        assert await theirs.get_items() == []
        await mine.clear_session()
