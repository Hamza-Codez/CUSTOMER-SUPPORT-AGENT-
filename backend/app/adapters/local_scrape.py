from typing import Any, List, Optional
from app.adapters.base import DataAdapter
from app.db.base import Store, OrderRecord, ProductRecord, PolicyRecord, EscalationRecord
import uuid

class LocalScrapeAdapter(DataAdapter):
    """
    Flavour A: Uses the scraped local Knowledge Base for policies,
    and relies on mock/ephemeral context for orders and products.
    All write actions (returns/refunds) generate Decision Cards for operator approval.
    """
    
    def __init__(self, store: Store):
        self.store = store
        self.ephemeral_context: dict | None = None

    async def get_order(self, business_id: str, order_id: str) -> Optional[OrderRecord]:
        if self.ephemeral_context and "orders" in self.ephemeral_context:
            for order in self.ephemeral_context["orders"]:
                if order.get("order_id") == order_id:
                    # Construct OrderRecord from ephemeral context
                    return OrderRecord(
                        business_id=business_id,
                        order_id=order_id,
                        status=order.get("status", "unknown"),
                        total=order.get("total", "0.00"),
                        placed_at=order.get("placed_at", "unknown"),
                        customer_email=order.get("email", ""),
                        customer_name=order.get("name", ""),
                        carrier=order.get("carrier"),
                        tracking_number=order.get("tracking_number"),
                        eta=order.get("eta"),
                        item_count=order.get("item_count", 0)
                    )
        return await self.store.get_order(business_id, order_id)

    async def get_cart(self, business_id: str, session_id: str) -> Any:
        if self.ephemeral_context and "cart" in self.ephemeral_context:
            return self.ephemeral_context["cart"]
        return {"items": [], "total": "0.00"}

    async def list_policies(self, business_id: str) -> List[PolicyRecord]:
        return await self.store.list_policies(business_id)

    async def search_policies(self, business_id: str, query: Any, limit: int = 2) -> List[PolicyRecord]:
        return await self.store.search_policies(business_id, query, limit=limit)

    async def search_products(self, business_id: str, query: str) -> List[ProductRecord]:
        return await self.store.search_products(business_id, query)

    async def get_product(self, business_id: str, product_id: str) -> Optional[ProductRecord]:
        return await self.store.get_product(business_id, product_id)

    async def create_return(self, business_id: str, order_id: str, items: List[str]) -> Any:
        # Flavour A: All write actions yield a Decision Card.
        return {"status": "escalated", "message": "Return request requires human approval."}

    async def create_refund(self, business_id: str, order_id: str, amount: str, reason: str) -> Any:
        # Flavour A: All write actions yield a Decision Card.
        return {"status": "escalated", "message": "Refund request requires human approval."}
