"""A deterministic model for the zero-setup path.

This is a real `Model` implementation, not a stub that skips the agent. The SDK
Runner drives it exactly as it drives Gemini: it emits genuine handoff calls and
genuine function calls, the Runner performs the real handoffs and executes the
real tools against the real store, and the results come back here to be phrased.

So `MODEL_PROVIDER=mock` exercises routing, handoffs, the tool layer, tenancy
scoping and audit logging for real. Only the language model is substituted.

What it is not: a claim about how a language model will phrase things, or proof
that Gemini routes the same way. It pins our wiring, not the model's judgement.
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

# Routing vocabulary, checked in this order. Refunds first: "refund my order"
# is a refund, not an order status question.
ROUTING = [
    ("Refunds", ("refund", "money back", "return this", "send it back", "reimburse")),
    ("Orders", ("track", "where is", "delivered", "shipped", "arrive", "my order")),
    ("Products", ("compare", "versus", " vs ", "cheaper", "in stock", "recommend",
                  "which one", "difference between", "desk", "chair", "cushion",
                  "sell", "buy", "price", "cost", "do you have", "stock")),
    ("Support", ("policy", "how long", "warranty", "dispatch", "delivery take",
                 "shipping", "return", "guarantee")),
]

POLICY_WORDS = (
    "refund", "return", "policy", "warranty", "dispatch", "shipping",
    "delivery", "how long", "guarantee", "money back",
)

ASK_FOR_DETAILS = (
    "Happy to check that for you. So I'm sure I'm looking at the right account, "
    "could you give me your order number (it looks like ORD-1002) and the email "
    "address on the order?"
)

FALLBACK = (
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


def _call(name: str, arguments: dict[str, Any]) -> ResponseFunctionToolCall:
    return ResponseFunctionToolCall(
        id=f"mock_{name}",
        call_id=f"mock_call_{name}",
        type="function_call",
        name=name,
        arguments=json.dumps(arguments),
    )


# --- phrasing -----------------------------------------------------------------


def _phrase_order(payload: dict[str, Any]) -> str:
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
    parts = [f"Good news — I found order {order.get('order_id')}. It's currently {status}."]
    if order.get("carrier"):
        tracking = order.get("tracking_number")
        parts.append(
            f"It's with {order['carrier']}"
            + (f", tracking number {tracking}." if tracking else ".")
        )
    if order.get("eta"):
        verb = "was delivered on" if status == "delivered" else "is expected by"
        parts.append(f"It {verb} {order['eta']}.")
    parts.append("Anything else I can help with — returns, refunds or product questions?")
    return " ".join(parts)


def _phrase_products(payload: dict[str, Any]) -> str:
    if payload.get("outcome") == "no_match":
        return (
            "I couldn't find anything in our catalogue matching that. "
            "Could you describe what you're after a little differently?"
        )

    products = payload.get("products") or []

    if len(products) == 1:
        p = products[0]
        stock = "in stock" if p.get("in_stock") else "currently out of stock"
        return (
            f"{p['name']} is {p['price']} and {stock}. {p.get('summary', '')} "
            "Would you like a closer look?"
        )

    lead = "Here are the closest matches: "
    lines = []
    for p in products:
        stock = "in stock" if p.get("in_stock") else "out of stock"
        lines.append(f"{p['name']} at {p['price']} ({stock}) — {p.get('summary', '')}")
    return lead + " ".join(lines) + " Happy to go deeper on either one."


def _phrase_policy(payload: dict[str, Any]) -> str:
    if payload.get("outcome") == "no_match":
        return (
            "I can't confirm that one from our written policy, and I'd rather not "
            "guess at it. Let me get a colleague to come back to you with a "
            "definite answer."
        )

    passages = payload.get("passages") or []
    first = passages[0]
    reply = f"{first['text']} (Source: {first['source_ref']})"
    if len(passages) > 1:
        reply += f" Also relevant: {passages[1]['text']} (Source: {passages[1]['source_ref']})"
    return reply + " Does that answer it?"


def _phrase(payload: dict[str, Any]) -> str:
    if "order" in payload or payload.get("outcome") == "identity_mismatch":
        return _phrase_order(payload)
    if "products" in payload:
        return _phrase_products(payload)
    if "passages" in payload:
        return _phrase_policy(payload)
    # not_found / no_match carry no collection, so fall back on what was asked.
    return _phrase_order(payload)


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
        items = (
            [{"role": "user", "content": input}]
            if isinstance(input, str)
            else [_as_dict(i) for i in input]
        )

        # 1. A tool has already run this turn -> phrase its result and stop.
        #    Handoff outputs are skipped: they carry no `outcome`, so they fall
        #    through to routing/tool selection below, which is what should happen.
        for item in reversed(items):
            if item.get("type") != "function_call_output":
                continue
            raw = item.get("output")
            try:
                payload = json.loads(raw) if isinstance(raw, str) else raw
            except (TypeError, ValueError):
                continue
            if isinstance(payload, dict) and "outcome" in payload:
                return self._say(_phrase(payload))

        user_text = " ".join(_text_of(i) for i in items if i.get("role") == "user")
        lowered = user_text.lower()

        # 2. Routing agent (has handoffs, no tools of its own).
        if handoffs and not tools:
            return self._route(lowered, handoffs)

        # 3. Specialist: pick the one tool that fits, call it once.
        available = {getattr(t, "name", "") for t in tools}

        if "policy_retriever" in available and any(w in lowered for w in POLICY_WORDS):
            return ModelResponse(
                output=[_call("policy_retriever", {"question": user_text})],
                usage=Usage(),
                response_id=None,
            )

        if "order_lookup" in available:
            order = ORDER_RE.search(user_text)
            email = EMAIL_RE.search(user_text)
            if order and email:
                return ModelResponse(
                    output=[
                        _call(
                            "order_lookup",
                            {
                                "order_id": f"ORD-{order.group(1)}",
                                "email": email.group(0),
                            },
                        )
                    ],
                    usage=Usage(),
                    response_id=None,
                )
            if order or "order" in lowered:
                return self._say(ASK_FOR_DETAILS)

        if "product_catalog" in available:
            return ModelResponse(
                output=[_call("product_catalog", {"query": user_text})],
                usage=Usage(),
                response_id=None,
            )

        if "policy_retriever" in available:
            return ModelResponse(
                output=[_call("policy_retriever", {"question": user_text})],
                usage=Usage(),
                response_id=None,
            )

        return self._say(FALLBACK)

    def _route(self, lowered: str, handoffs: list[Any]) -> ModelResponse:
        by_agent = {getattr(h, "agent_name", ""): h for h in handoffs}

        for agent_name, triggers in ROUTING:
            if agent_name in by_agent and any(t in lowered for t in triggers):
                return ModelResponse(
                    output=[_call(by_agent[agent_name].tool_name, {})],
                    usage=Usage(),
                    response_id=None,
                )

        # Nothing matched. Support is the safest default: it is the only
        # specialist that can answer without first needing account details.
        if "Support" in by_agent:
            return ModelResponse(
                output=[_call(by_agent["Support"].tool_name, {})],
                usage=Usage(),
                response_id=None,
            )
        return self._say(FALLBACK)

    def _say(self, text: str) -> ModelResponse:
        return ModelResponse(output=[_message(text)], usage=Usage(), response_id=None)

    def stream_response(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "The mock provider does not implement streaming. "
            "Phase 1 /chat is request/response; streaming arrives with the frontend phase."
        )
