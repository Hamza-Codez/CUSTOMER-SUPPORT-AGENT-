"""Postgres parity tests.

Skipped unless a real DATABASE_URL is configured in backend/.env. When it is,
these run the *same* assertions the mock store passes, which is the only way to
know the two implementations genuinely agree — a store that has only ever been
exercised through a fake is a store nobody has tested.

Run with:  uv run pytest tests/test_postgres.py -v
"""

from __future__ import annotations

from contextlib import asynccontextmanager

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


_prepared = False


@pytest.fixture
async def pg():
    """A connected Postgres store.

    Schema and ingestion run once per session, not per test. Both are idempotent,
    so repeating them changes nothing — but each re-ingest embeds every passage
    again, which turned a fast suite into a six-minute one. The connection itself
    is still per-test, so pool lifecycle stays isolated.
    """
    global _prepared

    store = PostgresStore(DSN)
    await store.connect()

    if not _prepared:
        from app.rag.ingest import ingest_knowledge_base

        await store.apply_schema(seed=True)
        # Policies come from the documents, not seed.sql, so the fixture loads
        # them exactly the way the setup scripts do.
        await ingest_knowledge_base(store, "biz_demo")
        _prepared = True

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
    """Both stores derive from the same markdown, so they must agree exactly."""
    from app.db.mock_store import MockStore

    mock = MockStore()
    for business_id in ("biz_demo", "biz_other"):
        from_pg = await pg.list_policies(business_id)
        from_mock = await mock.list_policies(business_id)
        assert sorted(p.source_ref for p in from_pg) == sorted(
            p.source_ref for p in from_mock
        )
        assert set(from_pg) == set(from_mock), f"policies differ for {business_id}"


class TestPgvector:
    async def test_the_extension_and_column_exist(self, pg):
        async with pg.pool.acquire() as conn:
            version = await conn.fetchval(
                "select extversion from pg_extension where extname = 'vector'"
            )
            dims = await conn.fetchval(
                """
                select atttypmod from pg_attribute
                 where attrelid = 'fte.policies'::regclass and attname = 'embedding'
                """
            )
        assert version
        assert dims == 1536

    async def test_every_ingested_passage_has_an_embedding(self, pg):
        async with pg.pool.acquire() as conn:
            missing = await conn.fetchval(
                """
                select count(*) from fte.policies
                 where business_id = 'biz_demo' and embedding is null
                """
            )
        assert missing == 0

    async def test_vector_search_ranks_by_cosine_similarity(self, pg):
        from app.rag.embeddings import embed_one

        vector = await embed_one("how long does dispatch take?")
        hits = await pg.search_policies("biz_demo", vector, limit=3)
        assert hits
        # Similarity, not distance: higher is better and the list is descending.
        scores = [score for _, score in hits]
        assert scores == sorted(scores, reverse=True)
        assert all(-1.0 <= s <= 1.0 for s in scores)

    async def test_vector_search_is_tenant_scoped(self, pg):
        from app.rag.embeddings import embed_one

        vector = await embed_one("unrelated seller policy")
        hits = await pg.search_policies("biz_demo", vector, limit=10)
        assert all(r.source_ref != "other-tenant.md#fixture" for r, _ in hits)

    async def test_passages_without_an_embedding_are_excluded(self, pg):
        """The cross-tenant fixture is seeded with no vector. It must be absent
        rather than ranked as maximally distant, which would present an
        un-ingested row as though it had been considered."""
        from app.rag.embeddings import embed_one

        vector = await embed_one("anything at all")
        hits = await pg.search_policies("biz_other", vector, limit=10)
        assert hits == []

    async def test_ingest_updates_in_place_rather_than_duplicating(self, pg):
        from app.rag.ingest import ingest_knowledge_base

        before = len(await pg.list_policies("biz_demo"))
        await ingest_knowledge_base(pg, "biz_demo")
        assert len(await pg.list_policies("biz_demo")) == before


class TestHybridRetrievalOnPostgres:
    """The same questions the in-memory store answers, against real pgvector."""

    @pytest.mark.parametrize(
        "question,expected",
        [
            ("how long does dispatch take?", "shipping-policy.md#dispatch"),
            ("what is your warranty cover?", "warranty-policy.md#cover"),
            ("my item arrived broken", "refund-policy.md#damaged-goods"),
            ("do you ship to Mars?", "shipping-policy.md#delivery-areas"),
        ],
    )
    async def test_finds_the_right_passage(self, pg, question, expected):
        from app.rag.retriever import retrieve_policies

        hits = await retrieve_policies(pg, "biz_demo", question, limit=2)
        assert hits, f"{question!r} returned nothing"
        assert hits[0].record.source_ref == expected

    @pytest.mark.parametrize(
        "question",
        ["do you accept cryptocurrency?", "what is the capital of France?"],
    )
    async def test_a_question_the_documents_do_not_answer_returns_nothing(
        self, pg, question
    ):
        from app.rag.retriever import retrieve_policies

        assert await retrieve_policies(pg, "biz_demo", question, limit=2) == []


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


class TestMoneyAndEscalationsInPostgres:
    """The refund and escalation tables carry the safety guarantees, so the
    guarantees have to hold in SQL and not only in the in-memory store."""

    async def test_a_duplicate_refund_is_refused_by_the_database(self, pg):
        import uuid

        from app.db.base import RefundRecord

        order_id = f"ORD-DUP-{uuid.uuid4().hex[:6]}"
        first = RefundRecord(
            refund_id=f"ref_{uuid.uuid4().hex[:8]}",
            business_id="biz_demo",
            order_id=order_id,
            amount="19.99",
            reason="pg test",
            status="executed",
        )
        assert await pg.create_refund(first) is True

        second = RefundRecord(**{**first.__dict__, "refund_id": f"ref_{uuid.uuid4().hex[:8]}"})
        assert await pg.create_refund(second) is False

        stored = await pg.get_refund("biz_demo", order_id)
        assert stored.refund_id == first.refund_id
        assert stored.amount == "19.99"

    async def test_an_escalation_round_trips_with_its_jsonb(self, pg):
        import uuid

        from app.db.base import EscalationRecord

        escalation_id = f"esc_{uuid.uuid4().hex[:8]}"
        await pg.create_escalation(
            EscalationRecord(
                escalation_id=escalation_id,
                business_id="biz_demo",
                session_id="pg-sess",
                status="pending",
                decision_card={"request": "Refund 149.00", "options": ["approve"]},
                run_state={"$schemaVersion": "test", "nested": {"a": [1, 2]}},
            )
        )
        got = await pg.get_escalation("biz_demo", escalation_id)
        assert got.decision_card["request"] == "Refund 149.00"
        assert got.run_state["nested"]["a"] == [1, 2]

    async def test_only_one_operator_can_resolve_a_card(self, pg):
        """Compare-and-set in SQL: the second Approve must lose."""
        import uuid

        from app.db.base import EscalationRecord

        escalation_id = f"esc_{uuid.uuid4().hex[:8]}"
        await pg.create_escalation(
            EscalationRecord(
                escalation_id=escalation_id,
                business_id="biz_demo",
                session_id="pg-race",
                status="pending",
                decision_card={},
            )
        )
        first = await pg.resolve_escalation(
            "biz_demo", escalation_id, "approved", "operator:a"
        )
        second = await pg.resolve_escalation(
            "biz_demo", escalation_id, "approved", "operator:b"
        )
        assert first is True
        assert second is False
        assert (await pg.get_escalation("biz_demo", escalation_id)).resolved_by == "operator:a"

    async def test_the_queue_is_tenant_scoped(self, pg):
        import uuid

        from app.db.base import EscalationRecord

        marker = uuid.uuid4().hex[:8]
        await pg.create_escalation(
            EscalationRecord(
                escalation_id=f"esc_{marker}",
                business_id="biz_other",
                session_id="s",
                status="pending",
                decision_card={"request": marker},
            )
        )
        mine = await pg.list_escalations("biz_demo", status="pending")
        assert all(e.escalation_id != f"esc_{marker}" for e in mine)


class TestRefundEligibilityAgainstPostgres:
    async def test_the_seeded_recent_order_is_auto_refundable(self, pg):
        """ORD-1005's dates are reset relative to current_date by seed.sql, so the
        auto-execute path stays reachable however long ago the database was set up."""
        from app.core.config import get_settings
        from app.guardrails.refund_guard import approval_reasons

        settings = get_settings()
        record = await pg.get_order("biz_demo", "ORD-1005")
        assert record is not None
        assert approval_reasons(
            record,
            float(record.total),
            cap=settings.auto_refund_cap,
            window_days=settings.refund_window_days,
        ) == []

    async def test_the_old_order_is_outside_the_window(self, pg):
        from app.guardrails.refund_guard import approval_reasons

        record = await pg.get_order("biz_demo", "ORD-1003")
        reasons = approval_reasons(record, 89.00, cap=25.0, window_days=30)
        assert "outside_refund_window" in reasons


class TestApprovalLoopOnPostgres:
    """The whole human-approval loop, over HTTP, against the real database.

    This exists because the loop passed every in-memory test and still failed on
    Postgres: serialising the paused run deep-copies the tenant context, which
    there holds a live asyncpg pool, so `to_json` raised and the escalation was
    stored with no run state. Approving then recorded a decision that could never
    execute. A store-agnostic test could not have caught it.
    """

    async def test_pause_then_approve_actually_pays(self, pg):
        import uuid

        from fastapi.testclient import TestClient

        from app.db import set_store
        from app.db.postgres_store import PostgresStore
        from app.main import app

        session_id = f"pg-approve-{uuid.uuid4().hex[:6]}"
        async with _clean_refund(pg, "ORD-1001"):
            # Its own store instance: the app lifespan closes whatever it is given,
            # and the `pg` fixture's pool is still needed by other tests.
            own = PostgresStore(DSN)
            set_store(own)
            try:
                with TestClient(app) as client:
                    body = client.post(
                        "/chat",
                        json={
                            "message": "refund ORD-1001, email ayesha.k@example.com",
                            "session_id": session_id,
                        },
                        headers={"Authorization": "Bearer demo-token"},
                    ).json()
                    assert "approval_pending" in [a["kind"] for a in body["actions"]]
                    assert await pg.get_refund("biz_demo", "ORD-1001") is None

                    cards = client.get(
                        "/dashboard/escalations?status_filter=pending",
                        headers={"Authorization": "Bearer ops-token"},
                    ).json()["escalations"]
                    card = next(
                        c
                        for c in cards
                        if c["proposed_action"].get("order_id") == "ORD-1001"
                    )

                    stored = await pg.get_escalation("biz_demo", card["escalation_id"])
                    assert stored.run_state, "run state was not persisted"

                    decision = client.post(
                        f"/escalations/{card['escalation_id']}/decision",
                        json={"decision": "approve"},
                        headers={"Authorization": "Bearer ops-token"},
                    ).json()
                    assert decision["status"] == "approved"
                    assert decision["outcome"] == "resumed"

                paid = await pg.get_refund("biz_demo", "ORD-1001")
                assert paid is not None
                assert paid.amount == "149.00"
            finally:
                set_store(None)


@asynccontextmanager
async def _clean_refund(pg, order_id: str):
    """Remove any refund for this order before and after, so the test is repeatable."""
    async with pg.pool.acquire() as conn:
        await conn.execute(
            "delete from fte.refunds where business_id='biz_demo' and order_id=$1",
            order_id,
        )
    try:
        yield
    finally:
        async with pg.pool.acquire() as conn:
            await conn.execute(
                "delete from fte.refunds where business_id='biz_demo' and order_id=$1",
                order_id,
            )


class TestCommsOnPostgres:
    async def test_one_summary_per_conversation_is_enforced_by_the_database(self, pg):
        import uuid

        from app.db.base import EmailRecord

        session_id = f"pg-email-{uuid.uuid4().hex[:6]}"

        def build() -> EmailRecord:
            return EmailRecord(
                email_id=f"eml_{uuid.uuid4().hex[:10]}",
                business_id="biz_demo",
                session_id=session_id,
                recipient="ayesha.k@example.com",
                subject="Your conversation",
                body_html="<p>hi</p>",
                feedback_token=uuid.uuid4().hex,
                status="pending",
                provider="mock",
            )

        first = build()
        assert await pg.create_email(first) is True
        assert await pg.create_email(build()) is False

        stored = await pg.get_email_for_session("biz_demo", session_id)
        assert stored.email_id == first.email_id

    async def test_delivery_status_round_trips(self, pg):
        import uuid

        from app.db.base import EmailRecord

        session_id = f"pg-status-{uuid.uuid4().hex[:6]}"
        record = EmailRecord(
            email_id=f"eml_{uuid.uuid4().hex[:10]}",
            business_id="biz_demo",
            session_id=session_id,
            recipient="a@example.com",
            subject="s",
            body_html="<p>x</p>",
            feedback_token=uuid.uuid4().hex,
            status="pending",
            provider="smtp",
        )
        await pg.create_email(record)
        await pg.update_email_status("biz_demo", record.email_id, "failed", "boom")

        stored = await pg.get_email_for_session("biz_demo", session_id)
        assert stored.status == "failed"
        assert stored.error == "boom"

    async def test_one_rating_per_token(self, pg):
        import uuid

        from app.db.base import EmailRecord, FeedbackRecord

        token = uuid.uuid4().hex
        session_id = f"pg-fb-{uuid.uuid4().hex[:6]}"
        await pg.create_email(
            EmailRecord(
                email_id=f"eml_{uuid.uuid4().hex[:10]}",
                business_id="biz_demo",
                session_id=session_id,
                recipient="a@example.com",
                subject="s",
                body_html="<p>x</p>",
                feedback_token=token,
                status="recorded",
                provider="mock",
            )
        )

        def feedback(rating: int) -> FeedbackRecord:
            return FeedbackRecord(
                business_id="biz_demo",
                feedback_token=token,
                session_id=session_id,
                rating=rating,
            )

        assert await pg.record_feedback(feedback(5)) is True
        assert await pg.record_feedback(feedback(1)) is False

        rows = [f for f in await pg.list_feedback("biz_demo", limit=500)
                if f.feedback_token == token]
        assert [f.rating for f in rows] == [5]

    async def test_a_token_resolves_to_its_tenant(self, pg):
        """The feedback link carries no tenant; the record it finds names one."""
        import uuid

        from app.db.base import EmailRecord

        token = uuid.uuid4().hex
        await pg.create_email(
            EmailRecord(
                email_id=f"eml_{uuid.uuid4().hex[:10]}",
                business_id="biz_demo",
                session_id=f"pg-tok-{uuid.uuid4().hex[:6]}",
                recipient="a@example.com",
                subject="s",
                body_html="<p>x</p>",
                feedback_token=token,
                status="recorded",
                provider="mock",
            )
        )
        found = await pg.get_email_by_token(token)
        assert found is not None
        assert found.business_id == "biz_demo"
        assert await pg.get_email_by_token("not-a-token") is None


class TestSessionVerificationOnPostgres:
    async def test_a_verification_survives_and_is_scoped(self, pg):
        import uuid

        from app.db.base import VerificationRecord

        session_id = f"pg-ver-{uuid.uuid4().hex[:6]}"
        await pg.add_verification(
            VerificationRecord(
                business_id="biz_demo",
                session_id=session_id,
                order_id="ORD-1002",
                email="ayesha.k@example.com",
                name="Ayesha K.",
            )
        )
        records = await pg.get_verifications("biz_demo", session_id)
        assert [r.order_id for r in records] == ["ORD-1002"]

        assert await pg.get_verifications("biz_other", session_id) == []
        assert await pg.get_verifications("biz_demo", "different-session") == []

    async def test_re_verifying_the_same_order_does_not_duplicate(self, pg):
        import uuid

        from app.db.base import VerificationRecord

        session_id = f"pg-ver2-{uuid.uuid4().hex[:6]}"
        for _ in range(3):
            await pg.add_verification(
                VerificationRecord(
                    business_id="biz_demo",
                    session_id=session_id,
                    order_id="ORD-1002",
                    email="ayesha.k@example.com",
                    name="Ayesha K.",
                )
            )
        assert len(await pg.get_verifications("biz_demo", session_id)) == 1


class TestCommercialOnPostgres:
    async def test_an_integration_request_round_trips(self, pg):
        import uuid

        from app.db.base import IntegrationRequest

        request_id = f"int_{uuid.uuid4().hex[:10]}"
        await pg.create_integration_request(
            IntegrationRequest(
                request_id=request_id,
                business_id="biz_demo",
                contact_name="Ayesha K.",
                contact_email="ayesha@aeron.example.com",
                website="https://aeron.example.com",
                platform="Shopify",
                monthly_conversations="2000",
                notes="Product pages too.",
            )
        )
        rows = await pg.list_integration_requests("biz_demo")
        found = next(r for r in rows if r.request_id == request_id)
        assert found.platform == "Shopify"
        assert found.status == "new"

    async def test_integration_requests_are_tenant_scoped(self, pg):
        import uuid

        from app.db.base import IntegrationRequest

        marker = uuid.uuid4().hex[:10]
        await pg.create_integration_request(
            IntegrationRequest(
                request_id=f"int_{marker}",
                business_id="biz_other",
                contact_name="Someone",
                contact_email="other@example.com",
            )
        )
        rows = await pg.list_integration_requests("biz_demo")
        assert all(r.request_id != f"int_{marker}" for r in rows)

    async def test_usage_aggregates_in_sql(self, pg):
        import uuid

        from app.db.base import UsageRecord

        session_id = f"pg-usage-{uuid.uuid4().hex[:6]}"
        before = await pg.usage_summary("biz_demo")

        for _ in range(2):
            await pg.record_usage(
                UsageRecord(
                    business_id="biz_demo",
                    session_id=session_id,
                    provider="gemini",
                    model="gemini-flash-latest",
                    requests=2,
                    input_tokens=1000,
                    output_tokens=250,
                )
            )

        after = await pg.usage_summary("biz_demo")
        # Two turns in one conversation is one conversation.
        assert after.conversations == before.conversations + 1
        assert after.input_tokens == before.input_tokens + 2000
        assert after.output_tokens == before.output_tokens + 500
        assert "gemini" in after.providers

    async def test_conversation_count_comes_from_the_transcript(self, pg):
        import uuid

        from app.db.session_store import StoreSession

        session_id = f"pg-conv-{uuid.uuid4().hex[:6]}"
        before = await pg.conversation_count("biz_demo")

        session = StoreSession(session_id, "biz_demo", pg)
        await session.add_items([{"role": "user", "content": "hello"}])

        assert await pg.conversation_count("biz_demo") == before + 1
        await session.clear_session()

    async def test_escalation_counts_group_in_sql(self, pg):
        counts = await pg.escalation_counts("biz_demo")
        assert set(counts) >= {"pending", "approved", "declined", "sessions"}
        assert all(isinstance(v, int) for v in counts.values())


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


class TestSiteKeysOnPostgres:
    """The public credential, against the real database.

    Parity matters more here than elsewhere: `allowed_origins` is a `text[]`,
    which is the one column type where asyncpg and the in-memory store could
    plausibly disagree — a list arriving back as a string would make `permits()`
    match on substrings instead of whole origins.
    """

    async def test_a_key_round_trips_with_its_origins_intact(self, pg):
        import uuid

        from app.db.base import SiteKeyRecord

        key = f"pk_{uuid.uuid4().hex}"
        await pg.create_site_key(
            SiteKeyRecord(
                key=key,
                business_id="biz_demo",
                label="Storefront",
                allowed_origins=["https://aeron.example.com"],
            )
        )
        found = await pg.get_site_key(key)
        assert found is not None
        assert found.business_id == "biz_demo"
        assert found.allowed_origins == ["https://aeron.example.com"]
        assert found.active is True
        assert found.permits("https://aeron.example.com")
        assert not found.permits("https://evil.example")

    async def test_revoking_is_tenant_scoped(self, pg):
        """Another tenant guessing the key must not be able to revoke it."""
        import uuid

        from app.db.base import SiteKeyRecord

        key = f"pk_{uuid.uuid4().hex}"
        await pg.create_site_key(
            SiteKeyRecord(
                key=key,
                business_id="biz_demo",
                allowed_origins=["https://aeron.example.com"],
            )
        )
        assert await pg.revoke_site_key("biz_other", key) is False
        assert (await pg.get_site_key(key)).active is True

        assert await pg.revoke_site_key("biz_demo", key) is True
        revoked = await pg.get_site_key(key)
        assert revoked.active is False
        assert revoked.permits("https://aeron.example.com") is False

    async def test_revoking_twice_reports_no_change(self, pg):
        import uuid

        from app.db.base import SiteKeyRecord

        key = f"pk_{uuid.uuid4().hex}"
        await pg.create_site_key(
            SiteKeyRecord(key=key, business_id="biz_demo", preview=True)
        )
        assert await pg.revoke_site_key("biz_demo", key) is True
        assert await pg.revoke_site_key("biz_demo", key) is False

    async def test_keys_are_listed_per_tenant(self, pg):
        import uuid

        from app.db.base import SiteKeyRecord

        marker = f"pk_{uuid.uuid4().hex}"
        await pg.create_site_key(
            SiteKeyRecord(key=marker, business_id="biz_other", preview=True)
        )
        keys = [k.key for k in await pg.list_site_keys("biz_demo")]
        assert marker not in keys

    async def test_a_preview_key_permits_any_origin(self, pg):
        import uuid

        from app.db.base import SiteKeyRecord

        key = f"pk_{uuid.uuid4().hex}"
        await pg.create_site_key(
            SiteKeyRecord(key=key, business_id="biz_demo", preview=True)
        )
        found = await pg.get_site_key(key)
        assert found.permits("https://anywhere.example")
