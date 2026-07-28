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

REFUND_WORDS = ("refund", "money back", "reimburse", "send it back", "return this")

# Phrasings that mean "the thing I bought", where the customer is not going to
# supply an order number because from where they are standing they should not
# have to.
MINE_WORDS = (
    "my order", "my orders", "my delivery", "my parcel", "my package",
    "my purchase", "my stuff", "where is it", "where's it", "my item",
    "my refund", "my return", "track", "my last order", "recent order",
)

# A message that is *only* a greeting. Matched on the whole message rather than
# by substring, because "hi, where is my order" is an order question wearing a
# hello, and routing it anywhere else would be the bug this replaced.
GREETING_RE = re.compile(
    r"^\W*("
    r"hi|hey|hello|yo|hiya|howdy|"
    r"good\s+(morning|afternoon|evening)|"
    r"thanks?|thank\s+you|cheers|ta|"
    r"bye|goodbye|see\s+you|"
    r"what\s+can\s+you\s+do|who\s+are\s+you|are\s+you\s+(a\s+)?(bot|human|real)|"
    r"help|start"
    r")\W*(there|folks|team)?\W*$",
    re.IGNORECASE,
)

SUMMARY_WORDS = (
    "email me", "send me a summary", "summary by email", "in writing",
    "email a summary", "confirmation email", "send a summary",
)

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


def _latest_first(pattern: re.Pattern[str], latest: str, history: str):
    """Prefer an entity from the current message, falling back to the conversation.

    "Refund ORD-1005" must not pick up the ORD-1002 someone asked about earlier,
    but "my email is …" as a follow-up still needs the order id from before it.
    """
    return pattern.search(latest) or pattern.search(history)


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


def _phrase_refund(payload: dict[str, Any]) -> str:
    outcome = payload.get("outcome")
    if outcome == "executed":
        return (
            f"That's sorted — I've refunded {payload.get('amount')} to your original "
            "payment method. It usually lands within 5-10 business days. "
            "Sorry for the trouble, and thanks for your patience."
        )
    if outcome == "already_refunded":
        return (
            "Good news — that order has already been refunded, so the money is "
            "on its way to you. Nothing further to do."
        )
    return (
        "I wasn't able to complete that refund. "
        f"{payload.get('message', '')} Let me get a colleague to take a look."
    )


def _phrase_email(payload: dict[str, Any]) -> str:
    outcome = payload.get("outcome")
    if outcome == "sent":
        return (
            "I've emailed you a summary of everything we covered, along with a "
            "quick one-tap rating if you have a moment. Anything else I can help with?"
        )
    if outcome == "already_sent":
        return "That summary is already on its way to you — check your inbox shortly."
    if outcome == "refused":
        return (
            "Before I can email a summary I need to confirm who I'm speaking to. "
            "Could you give me your order number and the email on the order?"
        )
    return (
        "I couldn't get that summary email out just now, but everything we "
        "discussed still stands."
    )


def _kind_of(payload: dict[str, Any]) -> str:
    """Which tool produced this. The result schemas are disjoint by construction."""
    # Checked first: GreetResult also carries `message`, and the `outcome+message`
    # test further down would otherwise claim it as an email.
    if "can_do" in payload or payload.get("outcome") == "greeted":
        return "greet"
    # Before "order": MyOrdersResult carries a list under `orders`, the singular
    # lookup carries one under `order`.
    if "orders" in payload:
        return "orders"
    if "products" in payload:
        return "products"
    if "passages" in payload:
        return "policy"
    if "refund_id" in payload:
        return "refund"
    if "escalation_id" in payload:
        return "escalation"

    # Below here the payloads collide. `OrderLookupResult(outcome="not_found")`
    # drops its null `order` field and serialises to exactly {outcome, message} —
    # the same shape as every EmailResult. The old "identified by what it lacks"
    # test therefore read every failed order lookup as an email, which is how a
    # refund on an order we do not hold spun until max turns instead of saying so.
    #
    # The outcome vocabularies are disjoint, so they are what disambiguates.
    outcome = payload.get("outcome")
    if outcome in {"sent", "already_sent", "refused", "failed"}:
        return "email"
    if outcome in {"found", "not_found", "identity_mismatch"}:
        return "order"
    if set(payload) <= {"outcome", "message"}:
        return "email"
    return "order"


def _phrase_my_orders(payload: dict[str, Any]) -> str:
    """The reply that replaces "what is your order number and email?"."""
    orders = payload.get("orders") or []
    if not orders:
        return (
            "I can't see any orders on your account. If you ordered as a guest, "
            "give me the order number and the email you used and I'll find it."
        )

    name = str(payload.get("customer_name") or "").split(" ")[0]
    opener = f"Hi {name} — " if name else ""
    unverified = payload.get("source") == "declared"

    if len(orders) == 1:
        one = orders[0]
        lines = [
            f"{opener}I can see your order {one['order_id']}, "
            f"currently {str(one.get('status') or 'unknown').replace('_', ' ')}."
        ]
        if one.get("tracking_number"):
            lines.append(
                f"It's with {one.get('carrier') or 'the carrier'}, tracking "
                f"{one['tracking_number']}."
            )
        if one.get("eta"):
            lines.append(f"Expected by {one['eta']}.")
    else:
        listed = ", ".join(
            f"{o['order_id']} ({str(o.get('status') or 'unknown').replace('_', ' ')})"
            for o in orders[:4]
        )
        lines = [f"{opener}I can see {len(orders)} orders on your account: {listed}."]
        lines.append("Which one would you like to talk about?")

    if unverified:
        lines.append(
            "I'm reading these from the page rather than your account, so I'll "
            "get a colleague involved before anything is actioned."
        )
    return " ".join(lines)


def _phrase(payload: dict[str, Any]) -> str:
    kind = _kind_of(payload)
    if kind == "greet":
        return str(payload.get("message") or FALLBACK)
    if kind == "orders":
        return _phrase_my_orders(payload)
    if kind == "products":
        return _phrase_products(payload)
    if kind == "policy":
        return _phrase_policy(payload)
    if kind == "refund":
        return _phrase_refund(payload)
    if kind == "email":
        return _phrase_email(payload)
    if kind == "escalation":
        return (
            "I've passed this to a colleague who can help properly. "
            "They'll be in touch shortly."
        )
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

        # 1. Everything the tools have already returned this turn, by kind.
        #    Handoff outputs carry no `outcome`, so they are skipped here and fall
        #    through to routing below, which is what should happen.
        # Only this turn's tool results count. `items` carries the whole session,
        # so scanning all of it made turn two act on turn one's lookup — the agent
        # re-reported an order when it had just sent an email. Everything after
        # the last user message is what happened since they spoke.
        last_user = max(
            (i for i, item in enumerate(items) if item.get("role") == "user"),
            default=-1,
        )
        this_turn = items[last_user + 1 :]

        seen: dict[str, dict[str, Any]] = {}
        attempted: set[str] = set()
        rejections: list[str] = []
        for item in this_turn:
            if item.get("type") == "function_call":
                attempted.add(str(item.get("name") or ""))
                continue
            if item.get("type") != "function_call_output":
                continue
            raw = item.get("output")
            try:
                payload = json.loads(raw) if isinstance(raw, str) else raw
            except (TypeError, ValueError):
                payload = None
            if isinstance(payload, dict) and "outcome" in payload:
                seen[_kind_of(payload)] = payload
            elif isinstance(raw, str) and raw.strip():
                # A tool guardrail rejected the call: the output is a plain
                # sentence explaining why, not a typed result.
                rejections.append(raw)

        # Intent comes from what the customer just said; entities may come from
        # anywhere in the conversation.
        #
        # Conflating the two is a real bug the demo caught: with the whole history
        # scored for intent, "which desk is better?" still contained "my order"
        # from three messages earlier and routed to Orders, and a refund request
        # for ORD-1005 picked up ORD-1002 from the backlog. But entities genuinely
        # do span turns — an order id in one message and the email in the next is
        # the most natural way for someone to answer.
        user_messages = [
            _text_of(i) for i in items if i.get("role") == "user"
        ]
        latest = user_messages[-1] if user_messages else ""
        history = " ".join(user_messages)
        lowered = latest.lower()

        available = {getattr(t, "name", "") for t in tools}

        # 2. Routing agent — one that holds handoffs and no tools it could answer
        #    with. `greet` does not count: it is authored text, not a lookup, so
        #    triage still has nothing of its own to answer from. Orders holds a
        #    handoff to Refunds *and* real tools, and must not land here.
        if handoffs and not (available - {"greet"}):
            if "greet" in seen:
                return self._say(str(seen["greet"].get("message") or FALLBACK))
            if "greet" in available and GREETING_RE.match(latest.strip()):
                return self._tool("greet", {})
            return self._route(lowered, history.lower(), handoffs)
        wants_refund = any(w in lowered for w in REFUND_WORDS)

        # 2b. An explicit request for a written summary. Checked before the other
        #     tools so "email me a summary of my order" does not read as a lookup.
        if (
            "send_summary_email" in available
            and any(w in lowered for w in SUMMARY_WORDS)
            and "email" not in seen
        ):
            if "send_summary_email" in attempted:
                return self._say(
                    "That summary is already on its way to you — check your inbox."
                )
            return self._tool(
                "send_summary_email",
                {"summary": "Here's a recap of what we sorted out together."},
            )

        # 3. Refund flow: check policy, verify identity, then attempt the refund.
        #    Sequenced deliberately — refund_processor's guardrail refuses unless
        #    order_lookup has already verified this order in this run.
        if "refund_processor" in available and wants_refund:
            # A blocked refund must never be retried. Without this the guardrail
            # rejects, the model tries again, and the run spins until max turns —
            # which is a denial of service dressed up as persistence.
            if "refund_processor" in attempted and "refund" not in seen:
                return self._say(
                    "I wasn't able to put that refund through. "
                    f"{rejections[-1] if rejections else ''} "
                    "Let me get a colleague to pick this up with you."
                )
            step = self._refund_step(seen, latest, history, available, attempted)
            if step is not None:
                return step

        # 3b. Ask the page who this is, before asking the customer anything.
        #     Mirrors the instruction the specialists carry: a signed-in customer
        #     should never be interrogated for details their own screen shows.
        if (
            "my_orders" in available
            and "my_orders" not in attempted
            and "orders" not in seen
            and any(w in lowered for w in MINE_WORDS)
        ):
            return self._tool("my_orders", {})

        # 4. A terminal tool result -> phrase it.
        #
        # `my_orders` is only terminal when it actually found something. Asking
        # the page who is here and being told "nobody" is the start of the work,
        # not the end of it — treating it as an answer would strand every
        # customer who is not signed in on a shrug.
        for kind in (
            "refund", "escalation", "email", "products", "policy", "orders", "order"
        ):
            if kind not in seen:
                continue
            if kind == "orders" and seen[kind].get("outcome") != "found":
                continue
            return self._say(_phrase(seen[kind]))

        # 5. Otherwise pick the one tool that fits and call it.
        if "policy_retriever" in available and any(w in lowered for w in POLICY_WORDS):
            return self._tool("policy_retriever", {"question": latest})

        if "order_lookup" in available:
            order = _latest_first(ORDER_RE, latest, history)
            email = _latest_first(EMAIL_RE, latest, history)
            if order and email:
                return self._tool(
                    "order_lookup",
                    {"order_id": f"ORD-{order.group(1)}", "email": email.group(0)},
                )
            if order or "order" in lowered:
                return self._say(ASK_FOR_DETAILS)

        if "product_catalog" in available:
            return self._tool("product_catalog", {"query": latest})

        if "policy_retriever" in available:
            return self._tool("policy_retriever", {"question": latest})

        return self._say(FALLBACK)

    def _refund_step(
        self,
        seen: dict[str, dict[str, Any]],
        latest: str,
        history: str,
        available: set[str],
        attempted: set[str],
    ) -> ModelResponse | None:
        """Next step of the refund chain, or None to fall through."""
        if "refund" in seen:
            return self._say(_phrase_refund(seen["refund"]))

        # Ground the ruling in the written policy first.
        if "policy" not in seen:
            return self._tool("policy_retriever", {"question": latest})

        # Then prove who we are talking to. The storefront may already have: if
        # `my_orders` returned exactly one order there is nothing to ask about,
        # and asking anyway is the behaviour this whole path exists to remove.
        order_result = seen.get("order")
        mine = seen.get("orders")
        if order_result is None and mine and len(mine.get("orders") or []) == 1:
            only = mine["orders"][0]
            return self._tool(
                "order_lookup", {"order_id": only["order_id"], "email": ""}
            )

        if order_result is None:
            order = _latest_first(ORDER_RE, latest, history)
            email = _latest_first(EMAIL_RE, latest, history)
            if order and email:
                return self._tool(
                    "order_lookup",
                    {"order_id": f"ORD-{order.group(1)}", "email": email.group(0)},
                )
            if mine is None and "my_orders" in available and "my_orders" not in attempted:
                # Ask the page before asking the person.
                return self._tool("my_orders", {})
            return self._say(ASK_FOR_DETAILS)

        if order_result.get("outcome") != "found":
            return self._say(_phrase_order(order_result))

        # Identity proven and policy read: attempt the refund for the full total.
        # Whether it executes, pauses for a human or is refused is not ours to decide.
        order = order_result.get("order") or {}
        return self._tool(
            "refund_processor",
            {
                "order_id": order.get("order_id"),
                "amount": float(order.get("total", 0)),
                "reason": "Customer requested a refund",
            },
        )

    def _tool(self, name: str, arguments: dict[str, Any]) -> ModelResponse:
        return ModelResponse(
            output=[_call(name, arguments)], usage=Usage(), response_id=None
        )

    def _route(
        self, latest: str, history: str, handoffs: list[Any]
    ) -> ModelResponse:
        """Route on the latest message; fall back to the conversation's intent.

        A follow-up often carries none of its own — "ayesha.k@example.com" on its
        own is not an order question, but it is plainly an answer to one. Latest
        first so a change of subject is honoured, history second so a bare reply
        stays with the specialist already handling it.
        """
        by_agent = {getattr(h, "agent_name", ""): h for h in handoffs}

        for text in (latest, history):
            for agent_name, triggers in ROUTING:
                if agent_name in by_agent and any(t in text for t in triggers):
                    return ModelResponse(
                        output=[_call(by_agent[agent_name].tool_name, {})],
                        usage=Usage(),
                        response_id=None,
                    )

        # Nothing matched anywhere. Support is the safest default: it is the only
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
