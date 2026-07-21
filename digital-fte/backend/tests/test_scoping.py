"""Per-user data scoping.

The tools' signatures are frozen (SPEC §5), so identity reaches them as ambient
context. These tests prove that plumbing actually isolates users — including
through the agent loop and the SSE generator, where a ContextVar is easiest to
lose.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import context
import store
from authed import token
from fakes import FakeSupabase
from main import app
from store import mock_store, supabase_store
from tools import process_refund, track_order


@pytest.fixture(autouse=True)
def clean():
    mock_store.reset_sessions()
    mock_store.reset_tickets()
    mock_store.reset_orders()
    yield
    mock_store.reset_sessions()
    mock_store.reset_tickets()
    mock_store.reset_orders()


def client(role="customer", user_id=None):
    return TestClient(app, headers={"Authorization": token(role, user_id)})


# --- seeding -----------------------------------------------------------------

@pytest.fixture(params=["mock", "supabase"])
def backend(request, monkeypatch):
    monkeypatch.setenv("DATA_BACKEND", request.param)
    if request.param == "supabase":
        supabase_store.set_client(FakeSupabase(mock_store.KNOWLEDGE_BASE))
    yield request.param
    supabase_store.set_client(None)


def test_seeding_gives_a_user_three_owned_orders(backend):
    orders = store.seed_demo_orders("alice")

    assert len(orders) == 3
    assert {o["user_id"] for o in orders} == {"alice"}
    assert len({o["order_id"] for o in orders}) == 3


def test_seeded_ids_never_collide_with_the_canonical_demo_orders(backend):
    ids = {o["order_id"] for o in store.seed_demo_orders("alice")}
    assert not ids & {"ORD-1001", "ORD-1002", "ORD-1003"}


def test_seeding_is_idempotent(backend):
    first = store.seed_demo_orders("alice")
    second = store.seed_demo_orders("alice")
    assert [o["order_id"] for o in first] == [o["order_id"] for o in second]


def test_two_users_get_different_orders(backend):
    alice = {o["order_id"] for o in store.seed_demo_orders("alice")}
    bob = {o["order_id"] for o in store.seed_demo_orders("bob")}
    assert not alice & bob


def test_a_seeded_set_can_demonstrate_both_approval_and_refusal(backend):
    """Onboarding needs one refundable order and one that is not, or the demo
    can only ever show half the guardrail."""
    orders = store.seed_demo_orders("alice")
    assert any(o["refundable"] for o in orders)
    assert any(not o["refundable"] for o in orders)


# --- the isolation rule ------------------------------------------------------

def test_an_owner_can_read_their_own_order(backend):
    order = store.seed_demo_orders("alice")[0]
    assert store.get_order(order["order_id"], "alice") is not None


def test_another_user_cannot_read_it(backend):
    order = store.seed_demo_orders("alice")[0]
    assert store.get_order(order["order_id"], "bob") is None


def test_an_anonymous_caller_cannot_read_an_owned_order(backend):
    order = store.seed_demo_orders("alice")[0]
    assert store.get_order(order["order_id"], None) is None


def test_shared_demo_fixtures_stay_visible_to_everyone(backend):
    """ORD-1001..1003 carry user_id=None. They are documentation, not data."""
    assert store.get_order("ORD-1001", "alice") is not None
    assert store.get_order("ORD-1001", "bob") is not None
    assert store.get_order("ORD-1001", None) is not None


# --- through the tools -------------------------------------------------------

def test_a_tool_cannot_reach_another_users_order():
    order = mock_store.seed_demo_orders("alice")[0]

    tok = context.set_user_id("bob")
    try:
        result = track_order.invoke({"order_id": order["order_id"]})
    finally:
        context.reset(tok)

    assert "couldn't find" in result.lower()
    assert order["customer"] not in result


def test_refunding_another_users_order_is_refused_and_logs_nothing():
    """The nastiest case: a refund on someone else's order must not succeed and
    must not even leave an escalation implying the order exists."""
    alice_order = next(o for o in mock_store.seed_demo_orders("alice") if o["refundable"])

    tok = context.set_user_id("bob")
    try:
        result = process_refund.invoke({"order_id": alice_order["order_id"],
                                        "reason": "not mine"})
    finally:
        context.reset(tok)

    assert "couldn't find" in result.lower()
    assert store.list_tickets() == []


def test_a_ticket_records_who_caused_it():
    tok = context.set_user_id("alice")
    try:
        process_refund.invoke({"order_id": "ORD-1002", "reason": "damaged"})
    finally:
        context.reset(tok)

    assert store.list_tickets()[0]["user_id"] == "alice"


# --- through HTTP, where the context is actually set -------------------------

def test_the_chat_endpoint_scopes_orders_to_the_caller():
    order = mock_store.seed_demo_orders("alice")[0]

    reply = client("customer", "bob").post(
        "/chat", json={"message": f"track {order['order_id']}", "session_id": "s"}
    ).json()["reply"]
    assert "couldn't find" in reply.lower()

    reply = client("customer", "alice").post(
        "/chat", json={"message": f"track {order['order_id']}", "session_id": "s"}
    ).json()["reply"]
    assert order["order_id"] in reply


def test_the_streaming_endpoint_scopes_orders_too():
    """The ContextVar is set inside the generator; if that were wrong, the
    streaming path would silently fall back to unscoped lookups."""
    order = mock_store.seed_demo_orders("alice")[0]

    def streamed_reply(user_id):
        with client("customer", user_id).stream(
            "POST", "/chat/stream",
            json={"message": f"track {order['order_id']}", "session_id": "s"}
        ) as response:
            frames = [json.loads(line[6:]) for line in response.iter_lines()
                      if line.startswith("data: ")]
        return next(f["reply"] for f in frames if f["type"] == "done")

    assert "couldn't find" in streamed_reply("bob").lower()
    assert order["order_id"] in streamed_reply("alice")


def test_tickets_carry_the_user_who_caused_them_over_http():
    client("customer", "alice").post(
        "/chat", json={"message": "refund ORD-1002, damaged", "session_id": "s"})

    tickets = client("agent").get("/tickets").json()["tickets"]
    assert len(tickets) == 1
    assert tickets[0]["user_id"] == "alice"


def test_me_provisions_the_users_own_orders():
    body = client("customer", "alice").get("/me").json()

    assert body["user"] == {"id": "alice", "email": "alice@example.test",
                            "role": "customer"}
    assert len(body["orders"]) == 3
    assert any(o["refundable"] for o in body["orders"])
    assert any(not o["refundable"] for o in body["orders"])


def test_me_is_idempotent_and_per_user():
    alice = client("customer", "alice").get("/me").json()["orders"]
    again = client("customer", "alice").get("/me").json()["orders"]
    bob = client("customer", "bob").get("/me").json()["orders"]

    assert [o["order_id"] for o in alice] == [o["order_id"] for o in again]
    assert not {o["order_id"] for o in alice} & {o["order_id"] for o in bob}


def test_me_requires_a_session():
    assert TestClient(app).get("/me").status_code == 401


def test_the_orders_a_user_is_shown_are_ones_they_can_actually_act_on():
    """Onboarding suggests these ids in the chat — if they weren't the user's
    own, every suggested message would come back 'couldn't find'."""
    orders = client("customer", "alice").get("/me").json()["orders"]

    reply = client("customer", "alice").post(
        "/chat", json={"message": f"track {orders[0]['order_id']}", "session_id": "s"}
    ).json()["reply"]
    assert orders[0]["order_id"] in reply


def test_identity_does_not_leak_between_consecutive_requests():
    """A ContextVar left set would make the next caller inherit the last one."""
    client("customer", "alice").post(
        "/chat", json={"message": "refund ORD-1002, damaged", "session_id": "s"})
    client("customer", "bob").post(
        "/chat", json={"message": "refund ORD-1002, damaged", "session_id": "s"})

    owners = [t["user_id"] for t in store.list_tickets()]
    assert sorted(owners) == ["alice", "bob"]
    assert context.current_user_id() is None      # cleaned up after the request
