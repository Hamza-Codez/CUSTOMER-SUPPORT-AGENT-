"""The grounding output guardrail.

This exists because of a failure observed against the live model, not a
hypothetical one. Asked "which is better, the AeroDesk Pro or the AeroDesk Lite?",
Gemini kept the conversation at the Orchestrator — which has no tools at all —
performed no handoff, and answered anyway with invented prices and specifications.

The triage prompt says, in plain words, "never answer a product question
yourself". The model ignored it. That is the whole argument for putting policy in
code: a prompt is a request, and a request can be declined.

The rule enforced here is evidence-based rather than content-based. We do not try
to judge whether a sentence sounds like a fact — that is exactly the kind of
guess this system exists to avoid. We check what the tools recorded during the
run, because only the tool layer knows what actually happened.
"""

from __future__ import annotations

from agents import GuardrailFunctionOutput, RunContextWrapper, output_guardrail

from app.core.auth import TenantContext

# Agents whose entire job is to route. They hold no tools, so any final answer
# they produce is necessarily ungrounded.
ROUTING_AGENTS = {"Orchestrator"}

# Agents that must consult a tool before asserting anything.
GROUNDED_AGENTS = {"Support", "Products", "Refunds", "Orders"}


def _text_of(output: object) -> str:
    if isinstance(output, str):
        return output
    return str(getattr(output, "final_output", output) or "")


def is_clarifying_question(reply: str) -> bool:
    """A question back to the customer asserts nothing, so it needs no grounding.

    Three conditions, because ending in a question mark alone is far too weak:
    a paragraph of invented policy followed by "does that help?" would sail
    straight through. A genuine clarification is short and is mostly the question.

    Sentence count does the real work here — length alone said a five-sentence
    fabrication ending in "?" was a clarification.
    """
    stripped = reply.strip()
    if not stripped.endswith("?") or len(stripped) > 300:
        return False
    sentences = sum(stripped.count(mark) for mark in ".!?")
    return sentences <= 2


def evaluate(agent_name: str, reply: str, tools_used: list[str]) -> str | None:
    """Return a reason to trip, or None. Pure function so it is directly testable."""
    if agent_name in ROUTING_AGENTS:
        # It should have handed off. Reaching here at all means it answered.
        return (
            f"{agent_name} produced a final answer but holds no tools, so nothing "
            "it said is grounded in store data."
        )

    if agent_name in GROUNDED_AGENTS and not tools_used:
        if is_clarifying_question(reply):
            return None
        return (
            f"{agent_name} answered without calling any tool, so the reply is not "
            "grounded in store data."
        )

    return None


@output_guardrail
async def must_be_grounded(
    ctx: RunContextWrapper[TenantContext],
    agent: object,
    output: object,
) -> GuardrailFunctionOutput:
    reason = evaluate(
        getattr(agent, "name", ""),
        _text_of(output),
        list(getattr(ctx.context, "tools_used", []) or []),
    )

    return GuardrailFunctionOutput(
        output_info={
            "reason": reason,
            "tools_used": list(getattr(ctx.context, "tools_used", []) or []),
            "sources": list(getattr(ctx.context, "sources", []) or []),
        },
        tripwire_triggered=reason is not None,
    )
