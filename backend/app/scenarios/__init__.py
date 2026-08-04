"""The scenario map — what LIGHTRON is contracted to do, before it does any of it.

This module exists because the previous build wrote prompts first and behaviour
second, so what the agent actually did was whatever the prose happened to
suggest that day. Here the behaviour is data: each scenario names its triggers,
the facts it must hold before deciding, the tools it may use, the rule it
decides by, the boundary it stops at, and the shape of the reply.

Three things consume this one table, which is the entire point:

1. **Specialist instructions** are generated from it, so a prompt cannot drift
   from the contract it is supposed to implement.
2. **The action guardrail** reads `escalates_when` to decide what must never
   complete without a human.
3. **The response renderer** reads `response` to decide whether an answer is a
   structured card built from tool data or prose from the voice tier — which is
   what stops order lists being retyped by a language model.

Adding a scenario means adding a row. It does not mean editing four prompts and
hoping they agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Specialist(StrEnum):
    """Who owns the scenario. These are real SDK agents, not labels."""

    ORDERS = "Orders"
    RETURNS = "Returns"
    PRODUCTS = "Products"
    POLICY = "Policy"


class Shape(StrEnum):
    """How the answer reaches the customer.

    The distinction is the fix for "responses look average". A card is built
    directly from adapter data — exact, fast, and impossible to phrase badly. The
    voice tier only writes the conversational glue around it, and for CARD-only
    scenarios it is skipped entirely.
    """

    CARD = "card"
    """Structured, rendered from tool output. No language model touches it."""

    PROSE = "prose"
    """Conversational. Rendered by the voice tier from decided facts."""

    CARD_AND_PROSE = "card+prose"
    """A card plus a sentence of context around it."""


class Boundary(StrEnum):
    """What happens when the decision rule cannot be satisfied.

    Named before the happy path, deliberately. Every one of these is a real
    outcome the agent reasons about — none of them is an exception, and none of
    them is a generic apology.
    """

    ASK = "ask_customer"
    """We are missing a fact only the customer has. Ask for exactly that fact."""

    ESCALATE = "escalate_to_human"
    """A person must take it from here. Produces a Decision Card."""

    APPROVAL = "human_approval"
    """The action is right but not ours to take. Pause the run, card it, resume."""

    REFUSE = "refuse_politely"
    """Out of scope. Say so and point somewhere useful."""


@dataclass(frozen=True)
class Scenario:
    id: str
    label: str
    owner: Specialist

    # What the customer says. Used to build routing instructions, never matched
    # as literal strings at runtime — the model routes, these teach it how.
    triggers: tuple[str, ...]

    # Facts that must be in hand before a decision is legitimate. If one is
    # missing and no tool can supply it, the boundary applies.
    needs: tuple[str, ...]

    # Adapter-backed tools this scenario may use. A specialist is never given a
    # tool no scenario it owns has asked for.
    tools: tuple[str, ...]

    # The rule, in one sentence, in the imperative. Goes verbatim into the
    # specialist's instructions so the prompt and this table cannot disagree.
    decision: str

    boundary: Boundary
    response: Shape

    # Conditions that force a human regardless of what the model concluded.
    # Read by the action guardrail, not by the model.
    escalates_when: tuple[str, ...] = field(default_factory=tuple)

    # True when the scenario's outcome moves money or changes an order. In
    # Flavour A there is no store backend to execute against, so every one of
    # these becomes a Decision Card by construction.
    writes: bool = False


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        id="order_status",
        label="Where is my order",
        owner=Specialist.ORDERS,
        triggers=("where is my order", "has it shipped", "track my delivery"),
        needs=("the specific order",),
        tools=("get_order", "get_orders"),
        decision=(
            "Report the order's real status, carrier, tracking and ETA exactly as "
            "the tool returned them. If the customer did not say which order and "
            "they have more than one, list them and ask which."
        ),
        boundary=Boundary.ASK,
        response=Shape.CARD_AND_PROSE,
    ),
    Scenario(
        id="order_list",
        label="My orders",
        owner=Specialist.ORDERS,
        triggers=("my orders", "what have I bought", "show my purchases"),
        needs=("the customer's visible orders",),
        tools=("get_orders",),
        decision=(
            "List every order newest first, each one selectable so the customer "
            "can open it. Do not summarise them in prose — the list is the answer."
        ),
        boundary=Boundary.ASK,
        response=Shape.CARD,
    ),
    Scenario(
        id="cart",
        label="What is in my basket",
        owner=Specialist.ORDERS,
        triggers=("my cart", "my basket", "what am I about to buy"),
        needs=("the live cart",),
        tools=("get_cart",),
        decision=(
            "Show the basket as it is right now. Never call a basket line an "
            "order: nothing in it is bought, and saying otherwise is the one "
            "mistake a customer will not forgive here."
        ),
        boundary=Boundary.ASK,
        response=Shape.CARD,
    ),
    Scenario(
        id="delayed_delivery",
        label="It is late",
        owner=Specialist.ORDERS,
        triggers=("it's late", "still not arrived", "past the delivery date"),
        needs=("the order", "its ETA", "the shipping policy"),
        tools=("get_order", "search_policies"),
        decision=(
            "Compare the ETA against today and say plainly whether it is late. "
            "Cite the shipping policy for what happens next. Acknowledge the "
            "delay before explaining anything."
        ),
        boundary=Boundary.ESCALATE,
        response=Shape.CARD_AND_PROSE,
        escalates_when=("more than 7 days past ETA", "second complaint about the same order"),
    ),
    Scenario(
        id="wrong_item",
        label="Wrong item received",
        owner=Specialist.RETURNS,
        triggers=("wrong item", "not what I ordered", "received the wrong thing"),
        needs=("the order", "what arrived", "the returns policy"),
        tools=("get_order", "search_policies", "create_return"),
        decision=(
            "Treat the store's error as the store's problem. Open a return and "
            "state the steps and the reference. Do not ask the customer to prove "
            "it before you have checked what the order says was sent."
        ),
        boundary=Boundary.APPROVAL,
        response=Shape.CARD_AND_PROSE,
        writes=True,
    ),
    Scenario(
        id="change_of_mind",
        label="Cancel — changed my mind",
        owner=Specialist.RETURNS,
        triggers=("cancel my order", "changed my mind", "I don't want it"),
        needs=("the order's dispatch status", "the cancellation policy"),
        tools=("get_order", "search_policies", "create_return"),
        decision=(
            "If it has not dispatched, the answer is cancellation. If it has, the "
            "answer is a return — say which one applies and why, rather than "
            "offering both and leaving the customer to work it out."
        ),
        boundary=Boundary.APPROVAL,
        response=Shape.PROSE,
        writes=True,
    ),
    Scenario(
        id="return",
        label="Return after delivery",
        owner=Specialist.RETURNS,
        triggers=("return this", "send it back", "how do I return"),
        needs=("the order", "the delivery date", "the returns window"),
        tools=("get_order", "search_policies", "create_return"),
        decision=(
            "Check the delivery date against the written returns window and say "
            "whether it qualifies. Quote the window from the policy rather than "
            "from memory."
        ),
        boundary=Boundary.APPROVAL,
        response=Shape.CARD_AND_PROSE,
        writes=True,
        escalates_when=("outside the returns window",),
    ),
    Scenario(
        id="replace",
        label="Replace a faulty item",
        owner=Specialist.RETURNS,
        triggers=("it's broken", "arrived damaged", "replace it", "faulty"),
        needs=("the order", "the warranty or damage policy"),
        tools=("get_order", "search_policies", "create_return"),
        decision=(
            "Damage on arrival is covered — lead with the replacement, not with "
            "the conditions. Cite the policy that covers it."
        ),
        boundary=Boundary.APPROVAL,
        response=Shape.CARD_AND_PROSE,
        writes=True,
    ),
    Scenario(
        id="refund",
        label="Refund me",
        owner=Specialist.RETURNS,
        triggers=("refund", "my money back", "reimburse me"),
        needs=("the order", "the refund policy", "the amount"),
        tools=("get_order", "search_policies", "create_refund"),
        decision=(
            "Rule on eligibility from the written policy and the order's real "
            "dates. Never tell a customer they have been refunded unless the tool "
            "reported that it happened."
        ),
        boundary=Boundary.APPROVAL,
        response=Shape.PROSE,
        writes=True,
        escalates_when=(
            "above the automatic cap",
            "outside the refund window",
            "the order has not been delivered",
        ),
    ),
    Scenario(
        id="policy_question",
        label="How does this store work",
        owner=Specialist.POLICY,
        triggers=("what's your returns policy", "how long is delivery", "warranty"),
        needs=("a passage from this store's own documents",),
        tools=("search_policies",),
        decision=(
            "Answer only from a retrieved passage and cite it. If retrieval "
            "returns nothing, say you cannot confirm it — a plausible-sounding "
            "policy is worse than no answer, because the customer will act on it."
        ),
        boundary=Boundary.ESCALATE,
        response=Shape.PROSE,
    ),
    Scenario(
        id="product_question",
        label="About a product",
        owner=Specialist.PRODUCTS,
        triggers=("does it come in", "how much is", "is it in stock", "compare"),
        needs=("the product as the store lists it",),
        tools=("search_products",),
        decision=(
            "Describe only what the store's own pages say. Prices and stock come "
            "from the tool, never from what sounds right."
        ),
        boundary=Boundary.ESCALATE,
        response=Shape.CARD_AND_PROSE,
    ),
    Scenario(
        id="angry",
        label="Upset customer",
        owner=Specialist.ORDERS,
        triggers=("this is unacceptable", "worst service", "I want to complain"),
        needs=("what actually went wrong",),
        tools=("get_order",),
        decision=(
            "Acknowledge before explaining. Do not defend the store, do not "
            "quote policy first, and do not ask them to calm down. Find the fact "
            "that fixes it, or find a person."
        ),
        boundary=Boundary.ESCALATE,
        response=Shape.PROSE,
        escalates_when=("legal threat", "mentions of harm", "asks for a human"),
    ),
    Scenario(
        id="resume",
        label="Reconnected mid-conversation",
        owner=Specialist.ORDERS,
        triggers=("are you still there", "I got disconnected"),
        needs=("the stored session",),
        tools=(),
        decision=(
            "Pick up from the last thing that actually happened. Do not restate "
            "the whole conversation and do not start again from a greeting."
        ),
        boundary=Boundary.ASK,
        response=Shape.PROSE,
    ),
    Scenario(
        id="decide_for_me",
        label="You choose",
        owner=Specialist.RETURNS,
        triggers=("what would you do", "you decide", "whatever is easiest"),
        needs=("the order", "the policy", "the available options"),
        tools=("get_order", "search_policies"),
        decision=(
            "Pick the best option the policy allows and say why it is best. "
            "Anything irreversible is proposed and confirmed, never simply done."
        ),
        boundary=Boundary.APPROVAL,
        response=Shape.PROSE,
        writes=True,
    ),
    Scenario(
        id="case_summary",
        label="Summarise my case",
        owner=Specialist.ORDERS,
        triggers=("summarise this", "what did we agree", "send me a recap"),
        needs=("the conversation", "any orders discussed"),
        tools=("get_orders",),
        decision=(
            "Assemble what was established and what happens next, from the "
            "record of the conversation rather than from impression."
        ),
        boundary=Boundary.ASK,
        response=Shape.CARD,
    ),
    Scenario(
        id="out_of_scope",
        label="Not about this store",
        owner=Specialist.POLICY,
        triggers=("the weather", "write me some code", "who is the president"),
        needs=(),
        tools=(),
        decision=(
            "Say plainly that you help with this store's orders, products and "
            "policies, and offer the nearest thing you can actually do."
        ),
        boundary=Boundary.REFUSE,
        response=Shape.PROSE,
    ),
)


BY_ID: dict[str, Scenario] = {s.id: s for s in SCENARIOS}


def owned_by(specialist: Specialist) -> tuple[Scenario, ...]:
    return tuple(s for s in SCENARIOS if s.owner is specialist)


def tools_for(specialist: Specialist) -> tuple[str, ...]:
    """Every tool the specialist's scenarios ask for, and nothing else.

    Least privilege falls out of the table rather than being maintained by hand:
    a specialist cannot reach a tool unless a scenario it owns declared it.
    """
    names: list[str] = []
    for scenario in owned_by(specialist):
        for tool in scenario.tools:
            if tool not in names:
                names.append(tool)
    return tuple(names)


def writing_scenarios() -> tuple[Scenario, ...]:
    """Everything that changes an order or moves money.

    In Flavour A these all resolve to Decision Cards, because there is no store
    backend to execute against — the adapter cannot write to a site we only
    scrape. That is a property of the flavour, not a limitation of the agent.
    """
    return tuple(s for s in SCENARIOS if s.writes)


def render_playbook(specialist: Specialist) -> str:
    """The specialist's scenarios as instruction text.

    Generated rather than written, so the prompt is the table. When someone adds
    a scenario the prompt gains it in the same commit, which is the whole reason
    this file exists.
    """
    lines: list[str] = []
    for scenario in owned_by(specialist):
        lines.append(f"\n### {scenario.label}")
        lines.append(f"They might say: {'; '.join(scenario.triggers)}.")
        if scenario.needs:
            lines.append(f"You need: {', '.join(scenario.needs)}.")
        lines.append(f"What to do: {scenario.decision}")
        if scenario.escalates_when:
            lines.append(
                "Hand to a colleague when: "
                f"{'; '.join(scenario.escalates_when)}."
            )
        lines.append(_BOUNDARY_TEXT[scenario.boundary])
    return "\n".join(lines).strip()


_BOUNDARY_TEXT: dict[Boundary, str] = {
    Boundary.ASK: (
        "If a fact is missing, ask for that one fact — not for a form's worth of "
        "details you could have looked up."
    ),
    Boundary.ESCALATE: (
        "If you cannot ground the answer, hand it to a colleague and say so. "
        "Guessing is the failure mode this whole system exists to prevent."
    ),
    Boundary.APPROVAL: (
        "This changes something. Prepare it and let a colleague approve it. Tell "
        "the customer it is with a person — never that it is done."
    ),
    Boundary.REFUSE: (
        "Decline in one sentence, without lecturing, and offer what you can do."
    ),
}
