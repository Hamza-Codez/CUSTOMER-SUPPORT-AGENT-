"""Input guardrails — screening before the first agent runs.

Deliberately implemented in code rather than as an LLM judge. Two reasons: a
model call per message doubles cost and burns rate limit on every turn, and a
screen that can be talked out of its job is not a screen.

Precision over recall. A false positive silences a real customer, which is worse
than letting an odd message through to agents that are themselves grounded and
tool-gated. So these patterns match intent to *manipulate the system*, not
merely rude or unusual phrasing.
"""

from __future__ import annotations

import re

from agents import GuardrailFunctionOutput, RunContextWrapper, input_guardrail

from app.core.auth import TenantContext

# Attempts to override the agent's instructions or extract its configuration.
_INJECTION_PATTERNS = [
    r"\bignore (all |any |your |the )?(previous |prior |above |earlier )?(instructions?|rules?|prompts?)\b",
    r"\bdisregard (all |any |your |the )?(previous |prior |above )?(instructions?|rules?)\b",
    r"\b(admin|developer|debug|god|sudo|root)[ -]?mode\b",
    r"\byou are now\b",
    r"\bpretend (to be|you are)\b",
    r"\bact as (if you|though|a)\b",
    r"\b(reveal|show|print|repeat|output) (me )?(your |the )?(system )?(prompt|instructions|rules)\b",
    r"\bwithout (needing|requiring|asking for) (any )?(the )?(email|verification|authentication|id)\b",
    r"\bbypass\b.{0,20}\b(check|verification|policy|guardrail)\b",
    r"\bjailbreak\b",
]

# Requests to use the agent as a general-purpose assistant. Narrow on purpose:
# only phrasings with no plausible support reading.
_OFF_TOPIC_PATTERNS = [
    r"\bwrite (me )?(a|an|some)? ?(poem|song|essay|story|joke|script|code|program)\b",
    r"\btranslate (this|the following|it)\b",
    r"\b(solve|calculate) (this )?(equation|math|integral)\b",
    r"\bwhat is the (capital|population|weather) (of|in)\b",
    r"\bwho (is|was) the (president|king|queen|prime minister)\b",
    r"\btell me a joke\b",
]

INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]
OFF_TOPIC_RE = [re.compile(p, re.IGNORECASE) for p in _OFF_TOPIC_PATTERNS]

REDIRECT_MESSAGE = (
    "I can help with orders, deliveries, products, returns and refunds. "
    "What can I help you with today?"
)


def _text(user_input: object) -> str:
    if isinstance(user_input, str):
        return user_input
    if isinstance(user_input, list):
        parts = []
        for item in user_input:
            content = item.get("content") if isinstance(item, dict) else None
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                parts.extend(
                    c.get("text", "")
                    for c in content
                    if isinstance(c, dict)
                )
        return " ".join(parts)
    return str(user_input)


def classify(message: str) -> str | None:
    """Return 'injection', 'off_topic', or None. Exposed for direct testing."""
    if any(r.search(message) for r in INJECTION_RE):
        return "injection"
    if any(r.search(message) for r in OFF_TOPIC_RE):
        return "off_topic"
    return None


@input_guardrail
async def scope_and_safety(
    ctx: RunContextWrapper[TenantContext],
    agent: object,
    user_input: object,
) -> GuardrailFunctionOutput:
    """Screen for prompt injection and clearly out-of-domain requests.

    Note this stops a message from reaching the agents at all. It is not the only
    defence and not the main one: even if something slips past, `business_id`
    still comes from the token, tools still verify identity, and the refund tool
    is still capped. This layer keeps the obvious attempts out of the transcript.
    """
    message = _text(user_input)
    verdict = classify(message)

    return GuardrailFunctionOutput(
        output_info={"verdict": verdict, "message": message[:200]},
        tripwire_triggered=verdict is not None,
    )
