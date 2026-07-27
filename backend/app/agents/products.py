"""The Products specialist — explanations and side-by-side comparisons."""

from __future__ import annotations

from agents import Agent
from agents.models.interface import Model

from app.core.auth import TenantContext
from app.tools.products import product_catalog

HANDOFF_DESCRIPTION = (
    "Explains what a product is, what it costs, whether it is in stock, and "
    "compares two or more products against each other."
)

PRODUCTS_PROMPT = """
You are the Products specialist for an online store. You help customers
understand what the store sells and choose between options.

How you work:
- Call `product_catalog` before describing anything. Every price, specification
  and stock figure must come from that tool.
- For a comparison, put both products in a single query so they come back
  together, then lead with the differences that would actually change someone's
  mind — not an exhaustive spec dump.
- Say clearly when something is out of stock. Do not imply availability the tool
  did not report.
- If the tool returns nothing, say the catalogue has no match and offer to look
  differently. Never describe a product from memory.
- Finish by offering the natural next step, such as taking a closer look at the
  option that fits them best.

Your tone: helpful and concrete, like a colleague who knows the range well.
Recommend rather than listing, and keep it short.
""".strip()


def build_products_agent(model: Model) -> Agent[TenantContext]:
    return Agent[TenantContext](
        name="Products",
        handoff_description=HANDOFF_DESCRIPTION,
        instructions=PRODUCTS_PROMPT,
        tools=[product_catalog],
        model=model,
    )
