"""Policy retrieval — the grounding tool.

This is the only source of policy truth the agents have. It returns the seller's
own parsed passages, each carrying a `source_ref`, and returns *nothing* when it
has no match. Returning nothing is the point: it is what lets the agent say "I
don't have that" instead of composing a plausible policy from model priors.

Phase 4 swaps keyword ranking for vector retrieval behind this same signature and
adds the grounding output guardrail that enforces the citation.
"""

from __future__ import annotations

from agents import RunContextWrapper, function_tool

from app.core import audit
from app.core.auth import TenantContext
from app.rag import keyword
from app.schemas import PolicyLookupResult, PolicyPassage

MAX_PASSAGES = 2


@function_tool
async def policy_retriever(
    ctx: RunContextWrapper[TenantContext],
    question: str,
) -> PolicyLookupResult:
    """Retrieve the store's written policy on a topic.

    Use this for any question about refunds, returns, delivery, dispatch times,
    shipping or warranty — including when you need to judge whether a refund
    request qualifies. Pass the customer's question as-is.

    Answer only from the passages this returns, and cite the `source_ref`. If it
    returns none, tell the customer you cannot confirm that and offer to get a
    colleague. Never state a policy this tool did not give you.
    """
    tenant = ctx.context
    policies = await tenant.store.list_policies(tenant.business_id)

    matches = keyword.rank(
        question,
        policies,
        text_of=lambda p: (p.topic, p.text),
        limit=MAX_PASSAGES,
    )

    await audit.record(
        tenant,
        action="policy_retriever",
        target=question[:120],
        outcome="found" if matches else "no_match",
        sources=[p.source_ref for p in matches],
    )

    if not matches:
        return PolicyLookupResult(
            outcome="no_match",
            message=(
                "No policy passage covers that question. You have no grounding for "
                "an answer here — say you cannot confirm it and offer a colleague. "
                "Do not answer from your own knowledge."
            ),
        )

    return PolicyLookupResult(
        outcome="found",
        passages=[
            PolicyPassage(topic=p.topic, text=p.text, source_ref=p.source_ref)
            for p in matches
        ],
        message=f"{len(matches)} passage(s) found. Cite the source_ref in your answer.",
    )
