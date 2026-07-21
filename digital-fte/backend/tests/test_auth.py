"""Identity verification and role enforcement.

PRD v2 metric: 100% of state-changing endpoints require a valid session.
These prove the negative cases — that unauthenticated and wrong-role callers are
actually refused — which is the only way that metric means anything.
"""
from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import auth
from auth import current_user, require_agent, verify_token
from authed import AGENT, CUSTOMER, token


# --- token verification ------------------------------------------------------

def test_mock_token_yields_the_claimed_role():
    assert verify_token("mock:agent").role == "agent"
    assert verify_token("mock:customer").role == "customer"


def test_mock_token_can_name_a_specific_user():
    user = verify_token("mock:customer:alice")
    assert user.id == "alice"
    assert user.role == "customer"


def test_two_ids_are_two_distinct_users():
    assert verify_token("mock:customer:alice").id != verify_token("mock:customer:bob").id


@pytest.mark.parametrize("token", [
    "", "garbage", "Bearer mock:agent", "mock:", "mock:admin", "mock:root",
    "mock:AGENT", "jwt.eyJhbGciOiJIUzI1NiJ9.x",
])
def test_anything_that_is_not_a_valid_mock_token_is_rejected(token):
    """Including 'mock:admin' — an unknown role must never authenticate."""
    assert verify_token(token) is None


def test_unknown_provider_raises_a_clear_value_error(monkeypatch):
    monkeypatch.setenv("AUTH_PROVIDER", "auth0")
    with pytest.raises(ValueError, match="Unknown AUTH_PROVIDER"):
        verify_token("mock:agent")


def test_supabase_without_its_secret_raises_a_clear_value_error(monkeypatch):
    monkeypatch.setenv("AUTH_PROVIDER", "supabase")
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    with pytest.raises(ValueError, match="SUPABASE_JWT_SECRET"):
        verify_token("some.jwt.token")


# --- the dependencies --------------------------------------------------------

def test_current_user_rejects_a_missing_header():
    with pytest.raises(HTTPException) as exc:
        current_user("")
    assert exc.value.status_code == 401


def test_current_user_rejects_a_bare_token_without_the_bearer_scheme():
    with pytest.raises(HTTPException) as exc:
        current_user("mock:agent")
    assert exc.value.status_code == 401


def test_current_user_accepts_a_well_formed_header():
    assert current_user("Bearer mock:agent").role == "agent"


def test_require_agent_gives_403_not_401_for_a_customer():
    """A customer is authenticated — they are simply not authorised. Returning
    401 here would tell them to log in again, which they cannot fix."""
    with pytest.raises(HTTPException) as exc:
        require_agent(verify_token("mock:customer"))
    assert exc.value.status_code == 403


def test_require_agent_passes_an_agent_through():
    assert require_agent(verify_token("mock:agent")).role == "agent"


def test_provider_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("AUTH_PROVIDER", raising=False)
    assert auth.provider_name() == "mock"


# --- supabase claim handling (verified without a live project) ---------------

def _signed(claims: dict, secret: str = "test-secret") -> str:
    jwt = pytest.importorskip("jwt")
    return jwt.encode(claims, secret, algorithm="HS256")


@pytest.fixture
def supabase_auth(monkeypatch):
    monkeypatch.setenv("AUTH_PROVIDER", "supabase")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")


def test_supabase_role_comes_from_app_metadata(supabase_auth):
    token = _signed({"sub": "u1", "email": "a@b.c", "aud": "authenticated",
                     "exp": 9999999999, "app_metadata": {"role": "agent"}})
    assert verify_token(token).role == "agent"


def test_user_metadata_cannot_grant_the_agent_role(supabase_auth):
    """user_metadata is writable by the user. If it were trusted, any customer
    could promote themselves to agent and read the whole audit log."""
    token = _signed({"sub": "u1", "email": "a@b.c", "aud": "authenticated",
                     "exp": 9999999999,
                     "user_metadata": {"role": "agent"},
                     "app_metadata": {"role": "customer"}})
    assert verify_token(token).role == "customer"


def test_an_unknown_role_falls_back_to_customer(supabase_auth):
    token = _signed({"sub": "u1", "email": "a@b.c", "aud": "authenticated",
                     "exp": 9999999999, "app_metadata": {"role": "superuser"}})
    assert verify_token(token).role == "customer"


def test_a_token_signed_with_the_wrong_secret_is_rejected(supabase_auth):
    token = _signed({"sub": "u1", "aud": "authenticated", "exp": 9999999999},
                    secret="attacker-secret")
    assert verify_token(token) is None


def test_an_expired_token_is_rejected(supabase_auth):
    token = _signed({"sub": "u1", "aud": "authenticated", "exp": 1000000000})
    assert verify_token(token) is None


# --- the gate, over HTTP -----------------------------------------------------
# PRD v2: "100% of state-changing endpoints require a valid session."
# These are the tests that make that claim mean something.

STATE_CHANGING = ["/chat", "/chat/stream"]


@pytest.fixture(autouse=True)
def clean():
    from store import mock_store
    mock_store.reset_sessions()
    mock_store.reset_tickets()
    yield
    mock_store.reset_sessions()
    mock_store.reset_tickets()


@pytest.mark.parametrize("path", STATE_CHANGING)
def test_state_changing_endpoints_refuse_an_anonymous_caller(path):
    import store
    from main import app
    response = TestClient(app).post(path, json={"message": "refund ORD-1002", "session_id": "x"})

    assert response.status_code == 401
    assert store.list_tickets() == [], "an anonymous call changed state"


@pytest.mark.parametrize("path", STATE_CHANGING)
@pytest.mark.parametrize("header", ["Bearer mock:admin", "Bearer garbage", "mock:agent", "Basic abc"])
def test_state_changing_endpoints_refuse_a_bad_token(path, header):
    from main import app
    client = TestClient(app, headers={"Authorization": header})
    assert client.post(path, json={"message": "hi", "session_id": "x"}).status_code == 401


def test_the_audit_log_refuses_an_anonymous_caller():
    from main import app
    assert TestClient(app).get("/tickets").status_code == 401


def test_the_audit_log_gives_a_customer_403_and_no_data():
    """Authenticated but not authorised. The old behaviour — any passer-by
    reading every customer's name, order total and escalation detail — is what
    this closes."""
    from main import app
    response = TestClient(app, headers={"Authorization": CUSTOMER}).get("/tickets")

    assert response.status_code == 403
    assert "tickets" not in response.text


def test_an_agent_can_read_the_audit_log():
    from main import app
    response = TestClient(app, headers={"Authorization": AGENT}).get("/tickets")
    assert response.status_code == 200
    assert "tickets" in response.json()


def test_health_stays_open():
    """It changes nothing and exposes nothing but which providers are live."""
    from main import app
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["auth"] == "mock"


def test_a_customer_may_use_the_chat():
    from main import app
    client = TestClient(app, headers={"Authorization": CUSTOMER})
    assert client.post("/chat", json={"message": "what is your refund policy",
                                      "session_id": "s"}).status_code == 200


def test_two_users_sharing_a_session_id_cannot_read_each_others_memory():
    """INTENT §5: memory is scoped per user. Both send with session_id 'shared';
    neither may see the other's turn."""
    import store
    from main import app

    alice = TestClient(app, headers={"Authorization": token("customer", "alice")})
    bob = TestClient(app, headers={"Authorization": token("customer", "bob")})

    alice.post("/chat", json={"message": "what is your refund policy", "session_id": "shared"})
    bob.post("/chat", json={"message": "what is the warranty", "session_id": "shared"})

    alice_memory = json.dumps(store.get_session("alice:shared")).lower()
    bob_memory = json.dumps(store.get_session("bob:shared")).lower()

    assert alice_memory and bob_memory
    assert "warranty" not in alice_memory
    assert "refund" not in bob_memory


def test_the_401_body_does_not_leak_internals():
    from main import app
    body = TestClient(app).post("/chat", json={"message": "hi"}).json()
    assert body == {"detail": "Not authenticated"}
