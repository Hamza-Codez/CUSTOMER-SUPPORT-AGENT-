"""SSE streaming contract, on MODEL_PROVIDER=mock.

The streamed reply must be indistinguishable from the /chat reply — same text,
same guardrails, and none of the internal plumbing that `stream_mode="messages"`
happily hands you if you forward every chunk.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import main
import store
from main import app
from store import mock_store

client = TestClient(app)

# `stream_mode="messages"` yields tool results too. If any of these reach the
# customer, the endpoint is forwarding chunks it should have filtered.
REPLY_LEAKS = ["[refund policy]", "[shipping times]", "[warranty]",
               "ask the customer", "do not refund", "traceback"]


def stream(message: str, session_id: str = "stream") -> list[dict]:
    with client.stream("POST", "/chat/stream",
                       json={"message": message, "session_id": session_id}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        frames = []
        for line in response.iter_lines():
            if line.startswith("data: "):
                frames.append(json.loads(line[len("data: "):]))
    return frames


def tokens(frames: list[dict]) -> str:
    return "".join(f["text"] for f in frames if f["type"] == "token")


def only(frames: list[dict], kind: str) -> list[dict]:
    return [f for f in frames if f["type"] == kind]


@pytest.fixture(autouse=True)
def clean():
    mock_store.reset_sessions()
    mock_store.reset_tickets()
    yield
    mock_store.reset_sessions()
    mock_store.reset_tickets()


# --- contract ----------------------------------------------------------------

def test_stream_emits_tokens_then_one_done_frame():
    frames = stream("what is your refund policy", "kb")

    assert len(only(frames, "token")) > 1, "expected the reply split into chunks"
    done = only(frames, "done")
    assert len(done) == 1
    assert done[-1] is frames[-1], "done must be the final frame"
    assert done[0]["session_id"] == "kb"


def test_streamed_tokens_reassemble_into_the_done_reply():
    frames = stream("what is your refund policy", "kb")
    assert tokens(frames) == only(frames, "done")[0]["reply"]


def test_stream_reply_matches_the_non_streaming_endpoint():
    """Same question, same answer — streaming is a transport, not a behaviour."""
    streamed = only(stream("how long does shipping take", "a"), "done")[0]["reply"]
    plain = client.post("/chat", json={"message": "how long does shipping take",
                                       "session_id": "b"}).json()["reply"]
    assert streamed == plain


def test_stream_never_leaks_tool_output_as_tokens():
    """The regression this endpoint invites: forwarding ToolMessage chunks."""
    for message in ["what is your refund policy", "track ORD-1001", "refund ORD-1002 damaged"]:
        text = tokens(stream(message, "leak")).lower()
        for leak in REPLY_LEAKS:
            assert leak not in text, f"{leak!r} leaked while streaming {message!r}"


def test_tool_frames_name_the_tool_that_ran():
    assert [f["name"] for f in only(stream("track ORD-1001", "t"), "tool")] == ["track_order"]
    assert [f["name"] for f in only(stream("what is the warranty", "t2"), "tool")] == ["search_kb"]


def test_tool_frames_arrive_before_the_tokens_they_explain():
    frames = stream("track ORD-1001", "order")
    kinds = [f["type"] for f in frames]
    assert kinds.index("tool") < kinds.index("token")


# --- guardrails hold on the streaming path -----------------------------------

def test_out_of_policy_refund_is_refused_and_escalated_while_streaming():
    frames = stream("refund ORD-1003 please", "refuse")
    reply = only(frames, "done")[0]["reply"]

    assert "haven't issued one" in reply
    tickets = store.list_tickets()
    assert len(tickets) == 1
    assert tickets[0]["escalated"] is True
    assert tickets[0]["priority"] == "high"


def test_kb_miss_escalates_while_streaming():
    frames = stream("do you offer gift wrapping", "miss")
    assert "can't answer" in only(frames, "done")[0]["reply"].lower()
    assert store.list_tickets()[0]["escalated"] is True


# --- failure path ------------------------------------------------------------

def test_agent_failure_arrives_as_an_error_frame_not_an_http_error(monkeypatch):
    """The response is already streaming when the agent dies, so the status line
    is long gone — the failure has to travel as a frame."""
    def boom():
        raise RuntimeError("model exploded")

    monkeypatch.setattr(main, "get_agent", boom)
    frames = stream("hello", "boom")

    errors = only(frames, "error")
    assert len(errors) == 1
    assert "temporarily unavailable" in errors[0]["detail"]
    assert "model exploded" not in json.dumps(frames)   # no internals leaked
    assert only(frames, "done") == []
    assert store.get_session("boom") == []             # failed turn not retained
