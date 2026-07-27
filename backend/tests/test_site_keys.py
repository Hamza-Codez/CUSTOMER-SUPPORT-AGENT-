"""Public site keys and the widget's chat endpoint.

This is the first credential that ships to a browser we do not control, so the
tests below are mostly about what it *cannot* do. The interesting assertions are
the refusals: an operator route reached with a site key, another tenant's data,
a key used from an origin it was not issued for.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

OPS = {"Authorization": "Bearer ops-token"}
CUSTOMER = {"Authorization": "Bearer demo-token"}
STORE_ORIGIN = "https://aeron-home.example"


@pytest.fixture
def client(store):
    with TestClient(app) as c:
        yield c


def mint(client, **body) -> dict:
    payload = {"label": "storefront", "allowed_origins": [STORE_ORIGIN]}
    payload.update(body)
    r = client.post("/site-keys", json=payload, headers=OPS)
    assert r.status_code == 201, r.text
    return r.json()


class TestIssuing:
    def test_an_operator_can_mint_a_key(self, client):
        body = mint(client)
        assert body["key"].startswith("pk_")
        assert body["active"] is True
        assert body["allowed_origins"] == [STORE_ORIGIN]

    def test_the_snippet_carries_the_key_and_the_script_url(self, client):
        body = mint(client)
        assert body["key"] in body["snippet"]
        assert "/widget.js" in body["snippet"]

    def test_a_bare_domain_is_normalised_to_an_origin(self, client):
        body = mint(client, allowed_origins=["MyStore.com/"])
        assert body["allowed_origins"] == ["https://mystore.com"]

    def test_a_production_key_needs_an_origin(self, client):
        """Fails closed. A key with no origins would work from anywhere."""
        r = client.post("/site-keys", json={"allowed_origins": []}, headers=OPS)
        assert r.status_code == 422
        assert "allowed origin" in r.json()["detail"]

    def test_a_preview_key_may_omit_origins(self, client):
        body = mint(client, allowed_origins=[], preview=True)
        assert body["preview"] is True

    def test_a_customer_token_cannot_mint_a_key(self, client):
        r = client.post(
            "/site-keys", json={"allowed_origins": [STORE_ORIGIN]}, headers=CUSTOMER
        )
        assert r.status_code == 403

    def test_keys_are_listed_for_the_owning_tenant(self, client):
        made = mint(client)
        r = client.get("/site-keys", headers=OPS)
        assert r.status_code == 200
        assert made["key"] in [k["key"] for k in r.json()["keys"]]


class TestRevoking:
    def test_a_revoked_key_stops_working(self, client):
        key = mint(client)["key"]
        assert client.delete(f"/site-keys/{key}", headers=OPS).status_code == 204

        r = client.post(
            "/chat/public",
            json={"message": "hi", "session_id": "revoked"},
            headers={"X-FTE-Site-Key": key, "Origin": STORE_ORIGIN},
        )
        assert r.status_code == 401

    def test_revoking_twice_is_not_found(self, client):
        key = mint(client)["key"]
        client.delete(f"/site-keys/{key}", headers=OPS)
        assert client.delete(f"/site-keys/{key}", headers=OPS).status_code == 404

    def test_a_revoked_key_is_still_listed(self, client):
        """Kept, not deleted — an audit entry naming it has to stay resolvable."""
        key = mint(client)["key"]
        client.delete(f"/site-keys/{key}", headers=OPS)
        keys = client.get("/site-keys", headers=OPS).json()["keys"]
        row = next(k for k in keys if k["key"] == key)
        assert row["active"] is False
        assert row["revoked_at"] is not None


class TestPublicChat:
    def test_a_valid_key_from_its_own_origin_can_chat(self, client):
        key = mint(client)["key"]
        r = client.post(
            "/chat/public",
            json={"message": "hi", "session_id": "pub-1"},
            headers={"X-FTE-Site-Key": key, "Origin": STORE_ORIGIN},
        )
        assert r.status_code == 200
        assert "greeted" in [a["kind"] for a in r.json()["actions"]]

    def test_the_widget_gets_the_same_agent_as_the_dashboard(self, client):
        key = mint(client)["key"]
        r = client.post(
            "/chat/public",
            json={
                "message": "where is ORD-1002? email ayesha.k@example.com",
                "session_id": "pub-2",
            },
            headers={"X-FTE-Site-Key": key, "Origin": STORE_ORIGIN},
        )
        assert r.status_code == 200
        assert "ORD-1002" in r.json()["reply"]

    def test_a_key_from_another_origin_is_refused(self, client):
        key = mint(client)["key"]
        r = client.post(
            "/chat/public",
            json={"message": "hi", "session_id": "pub-3"},
            headers={"X-FTE-Site-Key": key, "Origin": "https://evil.example"},
        )
        assert r.status_code == 403

    def test_a_key_with_no_origin_header_is_refused(self, client):
        key = mint(client)["key"]
        r = client.post(
            "/chat/public",
            json={"message": "hi", "session_id": "pub-4"},
            headers={"X-FTE-Site-Key": key},
        )
        assert r.status_code == 403

    def test_the_referer_is_accepted_when_origin_is_absent(self, client):
        key = mint(client)["key"]
        r = client.post(
            "/chat/public",
            json={"message": "hi", "session_id": "pub-5"},
            headers={"X-FTE-Site-Key": key, "Referer": f"{STORE_ORIGIN}/cart"},
        )
        assert r.status_code == 200

    def test_a_preview_key_accepts_any_origin(self, client):
        key = mint(client, allowed_origins=[], preview=True)["key"]
        r = client.post(
            "/chat/public",
            json={"message": "hi", "session_id": "pub-6"},
            headers={"X-FTE-Site-Key": key, "Origin": "https://anywhere.example"},
        )
        assert r.status_code == 200

    def test_an_unknown_key_is_refused(self, client):
        r = client.post(
            "/chat/public",
            json={"message": "hi", "session_id": "pub-7"},
            headers={"X-FTE-Site-Key": "pk_not_a_real_key", "Origin": STORE_ORIGIN},
        )
        assert r.status_code == 401

    def test_a_missing_key_is_refused(self, client):
        r = client.post(
            "/chat/public",
            json={"message": "hi", "session_id": "pub-8"},
            headers={"Origin": STORE_ORIGIN},
        )
        assert r.status_code == 401


class TestTheKeyCannotEscalateItself:
    """The whole point of a separate credential type."""

    def test_a_site_key_is_not_a_bearer_token(self, client):
        key = mint(client)["key"]
        r = client.get(
            "/dashboard/escalations", headers={"Authorization": f"Bearer {key}"}
        )
        assert r.status_code == 401

    def test_a_site_key_cannot_reach_the_operator_queue(self, client):
        key = mint(client)["key"]
        r = client.get("/dashboard/escalations", headers={"X-FTE-Site-Key": key})
        assert r.status_code == 401

    def test_a_site_key_cannot_mint_more_keys(self, client):
        key = mint(client)["key"]
        r = client.post(
            "/site-keys",
            json={"allowed_origins": ["https://evil.example"]},
            headers={"X-FTE-Site-Key": key},
        )
        assert r.status_code == 401


class TestWidgetScript:
    def test_the_script_is_served(self, client):
        r = client.get("/widget.js")
        assert r.status_code == 200
        assert "javascript" in r.headers["content-type"]

    def test_it_posts_to_the_public_endpoint_with_the_key_header(self, client):
        body = client.get("/widget.js").text
        assert "/chat/public" in body
        assert "X-FTE-Site-Key" in body

    def test_the_api_base_is_baked_in(self, client):
        """A seller pasting one line must not also have to configure a URL."""
        assert "__API_BASE__" not in client.get("/widget.js").text

    def test_it_never_writes_a_reply_as_markup(self, client):
        """The reply is model output rendered on someone else's page.

        Matches an assignment rather than the bare word: the comment explaining
        this rule names it too, and a test that a comment exists is worthless.
        """
        body = client.get("/widget.js").text
        assert ".innerHTML =" not in body
        assert ".outerHTML =" not in body
        assert "document.write" not in body
