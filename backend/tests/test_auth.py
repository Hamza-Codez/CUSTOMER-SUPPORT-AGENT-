"""Real seller accounts: signup, login, and what a session token grants.

Sign-up is for sellers, not shoppers. An end customer is identified by order id
plus email because the widget lives on the seller's own site, so there is no
shopper account for these tests to cover.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.security import (
    dummy_hash,
    hash_password,
    issue_token,
    read_token,
    verify_password,
)
from app.main import app

SIGNUP = {
    "business_name": "Aeron Home Goods",
    "name": "Ayesha K.",
    "email": "ayesha@aeron.example.com",
    "password": "a-long-enough-passphrase",
}


@pytest.fixture
def client(store):
    with TestClient(app) as c:
        yield c


def register(client, **overrides) -> dict:
    r = client.post("/auth/signup", json={**SIGNUP, **overrides})
    assert r.status_code == 201, r.text
    return r.json()


class TestPasswordHashing:
    def test_the_same_password_hashes_differently_each_time(self):
        assert hash_password("hunter2hunter2") != hash_password("hunter2hunter2")

    def test_a_correct_password_verifies(self):
        assert verify_password("hunter2hunter2", hash_password("hunter2hunter2"))

    def test_a_wrong_password_does_not(self):
        assert not verify_password("wrong", hash_password("hunter2hunter2"))

    def test_a_malformed_hash_is_a_failed_login_not_a_crash(self):
        assert verify_password("anything", "garbage") is False
        assert verify_password("anything", "") is False

    def test_the_hash_records_its_own_parameters(self):
        """So the cost can be raised later without invalidating every password."""
        assert hash_password("hunter2hunter2").startswith("scrypt$16384$8$1$")

    def test_the_plaintext_is_not_recoverable_from_the_hash(self):
        assert "hunter2hunter2" not in hash_password("hunter2hunter2")


class TestSessionTokens:
    def test_a_token_round_trips(self):
        token = issue_token(
            user_id="usr_1", business_id="biz_1", role="operator", email="a@b.co"
        )
        claims = read_token(token)
        assert claims["sub"] == "usr_1"
        assert claims["biz"] == "biz_1"
        assert claims["role"] == "operator"

    def test_a_tampered_token_is_rejected(self):
        token = issue_token(
            user_id="usr_1", business_id="biz_1", role="operator", email="a@b.co"
        )
        assert read_token(token[:-4] + "AAAA") is None

    def test_nonsense_is_rejected(self):
        assert read_token("not-a-token") is None

    def test_an_expired_token_is_rejected(self, monkeypatch):
        import app.core.security as security

        monkeypatch.setattr(security, "TOKEN_TTL", -security.TOKEN_TTL)
        token = security.issue_token(
            user_id="usr_1", business_id="biz_1", role="operator", email="a@b.co"
        )
        assert security.read_token(token) is None


class TestSignup:
    def test_it_creates_an_account_and_a_store(self, client):
        body = register(client)
        assert body["account"]["business_name"] == "Aeron Home Goods"
        assert body["account"]["role"] == "operator"
        assert body["account"]["business_id"].startswith("biz_")
        assert body["token"]

    def test_the_token_it_returns_works_immediately(self, client):
        body = register(client)
        r = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {body['token']}"}
        )
        assert r.status_code == 200
        assert r.json()["email"] == "ayesha@aeron.example.com"

    def test_a_duplicate_email_is_refused(self, client):
        register(client)
        r = client.post("/auth/signup", json=SIGNUP)
        assert r.status_code == 409
        assert "already registered" in r.json()["detail"]

    def test_the_password_is_never_returned(self, client):
        assert SIGNUP["password"] not in client.post(
            "/auth/signup", json=SIGNUP
        ).text

    @pytest.mark.parametrize(
        "field,value",
        [
            ("email", "not-an-email"),
            ("password", "short"),
            ("business_name", ""),
            ("name", ""),
        ],
    )
    def test_the_form_is_validated(self, client, field, value):
        r = client.post("/auth/signup", json={**SIGNUP, field: value})
        assert r.status_code == 422

    def test_each_signup_gets_its_own_tenant(self, client):
        first = register(client)
        second = register(client, email="other@example.com")
        assert (
            first["account"]["business_id"] != second["account"]["business_id"]
        )


class TestLogin:
    def test_correct_credentials_return_a_session(self, client):
        register(client)
        r = client.post(
            "/auth/login",
            json={"email": SIGNUP["email"], "password": SIGNUP["password"]},
        )
        assert r.status_code == 200
        assert r.json()["account"]["business_name"] == "Aeron Home Goods"

    def test_email_is_case_insensitive(self, client):
        register(client)
        r = client.post(
            "/auth/login",
            json={"email": "AYESHA@AERON.EXAMPLE.COM", "password": SIGNUP["password"]},
        )
        assert r.status_code == 200

    def test_a_wrong_password_is_refused(self, client):
        register(client)
        r = client.post(
            "/auth/login", json={"email": SIGNUP["email"], "password": "wrong-password"}
        )
        assert r.status_code == 401

    def test_an_unknown_account_gives_the_same_answer_as_a_wrong_password(
        self, client
    ):
        """Different messages would let anyone check who has an account."""
        register(client)
        wrong = client.post(
            "/auth/login", json={"email": SIGNUP["email"], "password": "wrong-password"}
        )
        missing = client.post(
            "/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
        )
        assert wrong.status_code == missing.status_code == 401
        assert wrong.json()["detail"] == missing.json()["detail"]

    def test_a_dummy_hash_exists_so_both_paths_do_the_same_work(self):
        """The timing defence itself: verifying against this costs what verifying
        a real hash costs, so a missing email is not detectably faster."""
        assert dummy_hash().startswith("scrypt$")
        assert verify_password("anything", dummy_hash()) is False


class TestWhatASessionGrants:
    def test_a_new_account_is_an_operator_of_its_own_store(self, client):
        body = register(client)
        auth = {"Authorization": f"Bearer {body['token']}"}
        assert client.get("/dashboard/escalations", headers=auth).status_code == 200
        assert client.get("/dashboard/analytics", headers=auth).status_code == 200

    def test_it_sees_none_of_the_demo_tenant_s_data(self, client):
        """The whole tenancy story, now with real accounts behind it."""
        client.post(
            "/chat",
            json={
                "message": "refund ORD-1001, email ayesha.k@example.com",
                "session_id": "seeded",
            },
            headers={"Authorization": "Bearer demo-token"},
        )
        demo = client.get(
            "/dashboard/escalations", headers={"Authorization": "Bearer ops-token"}
        ).json()["escalations"]
        assert demo, "the seeded tenant should have an escalation to be hidden"

        body = register(client)
        mine = client.get(
            "/dashboard/escalations",
            headers={"Authorization": f"Bearer {body['token']}"},
        ).json()["escalations"]
        assert mine == []

    def test_an_invalid_session_is_refused_with_a_useful_message(self, client):
        r = client.get(
            "/dashboard/analytics", headers={"Authorization": "Bearer made-up"}
        )
        assert r.status_code == 401
        assert "sign in" in r.json()["detail"].lower()

    def test_demo_tokens_still_work(self, client):
        """The seeded playground has to work for someone who has not signed up."""
        assert (
            client.get(
                "/dashboard/analytics", headers={"Authorization": "Bearer ops-token"}
            ).status_code
            == 200
        )

    def test_me_reports_a_demo_session_honestly(self, client):
        body = client.get(
            "/auth/me", headers={"Authorization": "Bearer ops-token"}
        ).json()
        assert body["name"] == "Demo session"
        assert body["email"] == ""
