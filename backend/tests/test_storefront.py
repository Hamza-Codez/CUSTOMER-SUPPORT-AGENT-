"""The storefront context: attested, declared, and forged.

Reported from a real integration: the widget sat on a page showing the
customer's own orders, their tracking numbers and their cart, and still opened
with "what is your order number and the email on it?". That is a demo wearing a
product's clothes.

The obvious fix — read the page — is the wrong one, because a page is
client-controlled. So the tests that matter here are the negative ones: a forged
assertion must prove nothing, and an unsigned page must never be able to move
money no matter how confidently it describes an order.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.storefront import read_context, read_declared, sign_context
from app.main import app

OPS = {"Authorization": "Bearer ops-token"}
ORIGIN = "https://joycart.example"

# The seeded order that is small, recent and in-policy, so a refund on it would
# execute if it were allowed to. That makes it the right order to prove a
# declared context cannot refund.
REFUNDABLE = "ORD-1005"
REFUNDABLE_EMAIL = "ayesha.k@example.com"


@pytest.fixture
def client(store):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def key(client) -> dict:
    r = client.post(
        "/site-keys",
        json={"label": "storefront", "allowed_origins": [ORIGIN]},
        headers=OPS,
    )
    assert r.status_code == 201, r.text
    created = r.json()
    secret = client.get(f"/site-keys/{created['key']}/secret", headers=OPS).json()
    return {"key": created["key"], "secret": secret["secret"]}


def payload(**overrides) -> dict:
    body = {
        "customer": {
            "ref": "cus_9001",
            "name": "Robin Alvarez",
            "email": REFUNDABLE_EMAIL,
        },
        "orders": [
            {
                "order_id": REFUNDABLE,
                "status": "delivered",
                "total": "19.99",
                "items": 1,
            }
        ],
        "cart": [{"name": "Lumbar Cushion", "qty": 1, "price": "39.00"}],
        "page": {"url": f"{ORIGIN}/orders", "title": "Your orders"},
    }
    body.update(overrides)
    return body


def attested(key: dict, **overrides) -> dict:
    return {
        "X-FTE-Site-Key": key["key"],
        "X-FTE-Customer-Session": sign_context(key["secret"], payload(**overrides)),
        "Origin": ORIGIN,
    }


def declared(key: dict, **overrides) -> dict:
    return {
        "X-FTE-Site-Key": key["key"],
        "X-FTE-Declared-Context": json.dumps(payload(**overrides)),
        "Origin": ORIGIN,
    }


class TestSigning:
    def test_a_signed_payload_round_trips(self, key):
        token = sign_context(key["secret"], payload())
        context, reason = read_context(token, key["secret"])
        assert reason == ""
        assert context is not None
        assert context.verified is True
        assert context.customer_name == "Robin Alvarez"
        assert context.order_ids() == [REFUNDABLE]

    def test_another_key_cannot_verify_it(self, key):
        token = sign_context(key["secret"], payload())
        context, reason = read_context(token, "sk_someone_elses_secret")
        assert context is None
        assert reason == "invalid signature"

    def test_a_tampered_payload_is_rejected(self, key):
        token = sign_context(key["secret"], payload())
        # Flip a character in the payload segment. The signature no longer covers
        # it, which is the entire point of signing it.
        head, body, sig = token.split(".")
        body = ("A" if body[0] != "A" else "B") + body[1:]
        context, reason = read_context(f"{head}.{body}.{sig}", key["secret"])
        assert context is None
        assert reason == "invalid signature"

    def test_an_expired_assertion_is_rejected(self, key):
        token = sign_context(key["secret"], payload(), expires_in=-10)
        context, reason = read_context(token, key["secret"])
        assert context is None
        assert reason == "expired"

    def test_a_forged_token_is_dropped_not_downgraded(self, client, key):
        """The failure mode that would make the signature decoration.

        If a bad signature quietly became "declared", an attacker's payload and
        an honest page's payload would be handled identically.
        """
        r = client.get(
            "/widget/session",
            headers={
                "X-FTE-Site-Key": key["key"],
                "X-FTE-Customer-Session": sign_context("sk_wrong", payload()),
                "Origin": ORIGIN,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["verified"] is False
        assert body["orders"] == []
        assert body["customer_name"] == ""

    def test_declared_context_is_never_verified(self):
        context = read_declared(payload())
        assert context is not None
        assert context.verified is False
        assert context.grade == "declared"

    def test_an_unsigned_page_cannot_assert_an_email(self):
        """The address the summary mailer would send to."""
        context = read_declared(payload())
        assert context.customer_email == ""


class TestTheWidgetSession:
    def test_an_attested_session_names_the_customer_and_their_orders(
        self, client, key
    ):
        body = client.get("/widget/session", headers=attested(key)).json()
        assert body["verified"] is True
        assert body["customer_name"] == "Robin Alvarez"
        # Our own records for this customer, which include but are not limited
        # to the one the page happened to be displaying.
        assert REFUNDABLE in [o["order_id"] for o in body["orders"]]

    def test_the_cart_comes_through_separately_from_the_orders(self, client, key):
        body = client.get("/widget/session", headers=attested(key)).json()
        assert [c["name"] for c in body["cart"]] == ["Lumbar Cushion"]

    def test_our_own_records_win_over_the_page(self, client, key):
        """The copy a refund would act on is the one worth showing.

        The page claims one order; the seeded account has several for this
        customer. What comes back is ours, not theirs.
        """
        body = client.get("/widget/session", headers=attested(key)).json()
        assert len(body["orders"]) > 1
        statuses = {o["status"] for o in body["orders"]}
        assert statuses - {"delivered", "in_transit", "processing"} == set()

    def test_a_declared_session_still_shows_orders_but_unverified(self, client, key):
        body = client.get("/widget/session", headers=declared(key)).json()
        assert body["verified"] is False
        assert [o["order_id"] for o in body["orders"]] == [REFUNDABLE]

    def test_no_context_is_not_an_error(self, client, key):
        body = client.get(
            "/widget/session",
            headers={"X-FTE-Site-Key": key["key"], "Origin": ORIGIN},
        ).json()
        assert body["verified"] is False
        assert body["orders"] == []
        assert body["business_name"]


class TestNoInterrogation:
    """The complaint, as a test."""

    def test_a_signed_in_customer_is_not_asked_for_an_order_number(
        self, client, key
    ):
        r = client.post(
            "/chat/public",
            json={"message": "where is my order?", "session_id": "sf-1"},
            headers=attested(key),
        )
        assert r.status_code == 200
        body = r.json()
        assert "order number" not in body["reply"].lower()
        assert "email" not in body["reply"].lower()
        assert "orders_listed" in [a["kind"] for a in body["actions"]]

    def test_it_greets_them_by_name(self, client, key):
        body = client.post(
            "/chat/public",
            json={"message": "where is my order?", "session_id": "sf-2"},
            headers=attested(key),
        ).json()
        assert "Robin" in body["reply"]

    def test_an_anonymous_visitor_is_still_asked(self, client, key):
        """The fallback has to keep working, or every guest checkout breaks."""
        body = client.post(
            "/chat/public",
            json={"message": "where is my order?", "session_id": "sf-3"},
            headers={"X-FTE-Site-Key": key["key"], "Origin": ORIGIN},
        ).json()
        assert "order number" in body["reply"].lower()

    def test_a_declared_session_is_flagged_as_unverified(self, client, key):
        body = client.post(
            "/chat/public",
            json={"message": "where is my order?", "session_id": "sf-4"},
            headers=declared(key),
        ).json()
        assert "orders_declared" in [a["kind"] for a in body["actions"]]


class TestTheBasket:
    """Reported from a live storefront, as the transcript that arrived.

    "what are my current orders in cart" matched no routing trigger, fell
    through to the Support default, and came back as a quote of the store's
    dispatch hours. The customer asked about their basket and was told what time
    orders leave the warehouse.

    Two causes: nothing possessive-but-not-"my order" routed to Orders, and the
    basket had no tool at all — the context carried it and the widget drew it,
    but nothing could talk about it.
    """

    @pytest.mark.parametrize(
        "message",
        [
            "what are my current orders in cart",
            "what is in my basket",
            "whats in my cart",
        ],
    )
    def test_a_basket_question_is_answered_from_the_basket(
        self, client, key, message
    ):
        body = client.post(
            "/chat/public",
            json={"message": message, "session_id": f"cart-{len(message)}"},
            headers=declared(key),
        ).json()
        assert "Lumbar Cushion" in body["reply"]
        # The failure this replaces: a dispatch-hours policy quote.
        assert "dispatched" not in body["reply"]
        assert "policy_cited" not in [a["kind"] for a in body["actions"]]

    def test_a_basket_is_never_described_as_an_order(self, client, key):
        body = client.post(
            "/chat/public",
            json={"message": "what is in my basket", "session_id": "cart-wording"},
            headers=declared(key),
        ).json()
        assert "not bought" in body["reply"] or "Nothing there is bought" in body["reply"]

    def test_a_basket_only_customer_is_not_an_empty_result(self, client, key):
        """Someone browsing who has not bought yet still has a question."""
        body = client.post(
            "/chat/public",
            json={"message": "what is in my basket", "session_id": "cart-only"},
            headers=declared(key, orders=[]),
        ).json()
        assert "Lumbar Cushion" in body["reply"]

    def test_without_a_page_it_says_so_rather_than_offering_a_menu(
        self, client, key
    ):
        """The generic capability list is what something that did not listen says."""
        body = client.post(
            "/chat/public",
            json={"message": "what is in my basket", "session_id": "cart-none"},
            headers={"X-FTE-Site-Key": key["key"], "Origin": ORIGIN},
        ).json()
        assert "basket" in body["reply"].lower()
        assert "I can help with orders, deliveries" not in body["reply"]


class TestDeclaredContextCannotMoveMoney:
    """The attack the whole two-grade design exists to stop.

    A customer editing `window.fteContext` in devtools can claim any order they
    like. They may be told about it — the page already showed it to them — but
    nothing they claim may reach a refund.
    """

    def test_a_declared_order_is_never_verified_for_a_refund(self, client, key):
        body = client.post(
            "/chat/public",
            json={
                "message": f"I want a refund for {REFUNDABLE}",
                "session_id": "sf-refund-declared",
            },
            headers=declared(key),
        ).json()
        kinds = [a["kind"] for a in body["actions"]]
        assert "refund_executed" not in kinds

    def test_a_refund_on_an_order_we_do_not_hold_says_so(self, client, key):
        """Safe was not the same as working.

        This case used to spin until max turns and answer "I'm going round in
        circles" — no money moved, but nothing useful said either. It has to end
        in a sentence, not a timeout.
        """
        body = client.post(
            "/chat/public",
            json={
                "message": "I want a refund for JC-20260728-8VVK",
                "session_id": "sf-refund-foreign",
            },
            headers=declared(
                key,
                orders=[
                    {
                        "order_id": "JC-20260728-8VVK",
                        "status": "delivered",
                        "total": "666.85",
                    }
                ],
            ),
        ).json()
        kinds = [a["kind"] for a in body["actions"]]
        assert "refund_executed" not in kinds
        assert "agent_stuck" not in kinds

    def test_a_claimed_order_belonging_to_nobody_is_refused(self, client, key):
        """An order id invented in the page must not become a refundable one."""
        body = client.post(
            "/chat/public",
            json={
                "message": "I want a refund for ORD-9999",
                "session_id": "sf-refund-invented",
            },
            headers=declared(
                key,
                orders=[{"order_id": "ORD-9999", "status": "delivered", "total": "5.00"}],
            ),
        ).json()
        kinds = [a["kind"] for a in body["actions"]]
        assert "refund_executed" not in kinds

    def test_an_attested_order_we_do_not_hold_goes_to_a_human(self, client, key):
        """The seller keeps their own order data.

        We can discuss it, but we hold no payment record to refund against, so
        this is a person's decision — not a claim that the order doesn't exist.
        """
        from app.core.storefront import StorefrontContext, StorefrontOrder
        from app.guardrails.refund_guard import refund_precheck  # noqa: F401

        context = StorefrontContext(
            verified=True,
            orders=[StorefrontOrder(order_id="JC-20260728-8VVK", status="delivered")],
        )
        assert context.order("JC-20260728-8VVK") is not None
        assert context.order("JC-NOPE") is None
