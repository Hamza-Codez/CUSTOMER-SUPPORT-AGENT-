"""Product tools — part of the data frontier.

Same rules as every other tool: tenancy comes from the run context, the store is
the only data source, results are typed, and the read is audited.
"""

from __future__ import annotations

from agents import RunContextWrapper, function_tool

from app.core import audit
from app.core.auth import TenantContext
from app.rag import keyword
from app.schemas import ProductCard, ProductLookupResult

# Enough to lay two or three options side by side without flooding the model.
MAX_RESULTS = 3


@function_tool
async def product_catalog(
    ctx: RunContextWrapper[TenantContext],
    query: str,
) -> ProductLookupResult:
    """Search the store's product catalogue.

    Use this whenever the customer asks what a product is, what it costs, whether
    it is in stock, or how two products compare. Pass their words as the query —
    for a comparison, include both product names in one query so you get them
    back together. Describe only the products this returns; if it returns none,
    say so rather than describing a product from memory.
    """
    tenant = ctx.context
    products = await tenant.store.list_products(tenant.business_id)

    matches = keyword.rank(
        query,
        products,
        text_of=lambda p: (p.name, p.summary, " ".join(p.attributes.values())),
        limit=MAX_RESULTS,
    )

    await audit.record(
        tenant,
        action="product_catalog",
        target=query[:120],
        outcome="found" if matches else "no_match",
        result_count=len(matches),
    )

    if not matches:
        return ProductLookupResult(
            outcome="no_match",
            message=(
                f"Nothing in the catalogue matches {query!r}. "
                "Do not describe any product; offer to help the customer search differently."
            ),
        )

    return ProductLookupResult(
        outcome="found",
        products=[
            ProductCard(
                product_id=p.product_id,
                name=p.name,
                price=p.price,
                in_stock=p.in_stock,
                summary=p.summary,
                attributes=p.attributes,
            )
            for p in matches
        ],
        message=f"{len(matches)} product(s) matched.",
    )
