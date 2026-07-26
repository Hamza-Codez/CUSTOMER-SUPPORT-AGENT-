"""A deterministic model for the zero-setup path.

This is a real `Model` implementation, not a stub that skips the agent. The SDK
Runner drives it exactly as it drives Gemini: it emits a genuine function call,
the Runner executes the real tool against the real store, and the result comes
back here to be phrased. That means `MODEL_PROVIDER=mock` exercises the tool
layer, tenancy scoping and audit logging for real — only the language model is
substituted.
"""

from __future__ import annotations

import json
import re
from typing import Any

from agents.items import ModelResponse
from agents.models.interface import Model
from agents.usage import Usage
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)

ORDER_RE = re.compile(r"\bORD[-\s]?(\d{3,})\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

ASK_FOR_DETAILS = (
    "Happy to check that for you. So I'm sure I'm looking at the right account, "
    "could you give me your order number (it looks like ORD-1002) and the email "
    "address on the order?"
)

OFF_TOPIC = (
    "I can help with orders, deliveries, products and refunds. "
    "Could you tell me a bit more about what you need?"
)


def _as_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    dump = getattr(item, "model_dump", None)
    return dump() if callable(dump) else {}


def _text_of(item: dict[str, Any]) -> str:
    content = item.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for part in content:
            part_d = _as_dict(part)
            if isinstance(part_d.get("text"), str):
                chunks.append(part_d["text"])
            elif isinstance(part, str):
                chunks.append(part)
        return " ".join(chunks)
    return ""


def _message(text: str) -> ResponseOutputMessage:
    return ResponseOutputMessage(
        id="mock_msg",
        type="message",
        role="assistant",
        status="completed",
        content=[ResponseOutputText(type="output_text", text=text, annotations=[])],
    )


def _phrase_order_result(payload: dict[str, Any]) -> str:
    """Turn a typed OrderLookupResult into something a customer would want to read."""
    outcome = payload.get("outcome")

    if outcome == "not_found":
        return (
            "I couldn't find an order with that number on your account. "
            "Could you double-check the order ID and try again? "
            "It usually looks like ORD-1002."
        )

    if outcome == "identity_mismatch":
        return (
            "That order number exists, but the email you gave doesn't match the one "
            "on it. For your security I can't share the details until they match — "
            "could you check which email address was used for the order?"
        )

    order = payload.get("order") or {}
    status = str(order.get("status", "unknown")).replace("_", " ")
    lines = [
        f"Good news — I found order {order.get('order_id')}. It's currently {status}."
    ]
    if order.get("carrier"):
        carrier = order["carrier"]
        tracking = order.get("tracking_number")
        lines.append(
            f"It's with {carrier}"
            + (f", tracking number {tracking}." if tracking else ".")
        )
    if order.get("eta"):
        verb = "was delivered on" if status == "delivered" else "is expected by"
        lines.append(f"It {verb} {order['eta']}.")
    lines.append("Anything else I can help with — returns, refunds or product questions?")
    return " ".join(lines)


class MockModel(Model):
    """Reason-act loop, minus the language model."""

    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[Any],
        model_settings: Any,
        tools: list[Any],
        output_schema: Any,
        handoffs: list[Any],
        tracing: Any,
        *,
        previous_response_id: str | None = None,
        conversation_id: str | None = None,
        prompt: Any = None,
        **kwargs: Any,
    ) -> ModelResponse:
        items = [{"role": "user", "content": input}] if isinstance(input, str) else [
            _as_dict(i) for i in input
        ]

        # If a tool already ran this turn, our job is to phrase its result.
        for item in reversed(items):
            if item.get("type") == "function_call_output":
                raw = item.get("output")
                try:
                    payload = json.loads(raw) if isinstance(raw, str) else raw
                except (TypeError, ValueError):
                    payload = {}
                if isinstance(payload, dict) and "outcome" in payload:
                    return self._respond(_phrase_order_result(payload))
                return self._respond("Thanks — that's sorted.")

        user_text = " ".join(
            _text_of(i) for i in items if i.get("role") == "user"
        )

        has_order_lookup = any(
            getattr(t, "name", "") == "order_lookup" for t in tools
        )
        order_match = ORDER_RE.search(user_text)
        email_match = EMAIL_RE.search(user_text)

        if has_order_lookup and order_match and email_match:
            order_id = f"ORD-{order_match.group(1)}"
            call = ResponseFunctionToolCall(
                id="mock_call",
                call_id="mock_call_1",
                type="function_call",
                name="order_lookup",
                arguments=json.dumps(
                    {"order_id": order_id, "email": email_match.group(0)}
                ),
            )
            return ModelResponse(output=[call], usage=Usage(), response_id=None)

        if has_order_lookup and (order_match or "order" in user_text.lower()):
            return self._respond(ASK_FOR_DETAILS)

        return self._respond(OFF_TOPIC)

    def _respond(self, text: str) -> ModelResponse:
        return ModelResponse(
            output=[_message(text)], usage=Usage(), response_id=None
        )

    def stream_response(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "The mock provider does not implement streaming. "
            "Phase 1 /chat is request/response; streaming arrives with the frontend phase."
        )
