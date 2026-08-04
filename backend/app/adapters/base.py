from typing import Protocol, Any, Dict, List, Optional

class DataAdapter(Protocol):
    """
    Protocol for interacting with the store's e-commerce backend.
    This separates the FTE logic from the specific store platform (e.g. Shopify, Magento, or local scrape).
    """

    async def get_order(self, business_id: str, order_id: str) -> Optional[Any]:
        ...

    async def get_cart(self, business_id: str, session_id: str) -> Any:
        ...

    async def list_policies(self, business_id: str) -> List[Any]:
        ...

    async def search_policies(self, business_id: str, query: Any, limit: int = 2) -> List[Any]:
        ...

    async def search_products(self, business_id: str, query: str) -> List[Any]:
        ...

    async def get_product(self, business_id: str, product_id: str) -> Optional[Any]:
        ...

    async def create_return(self, business_id: str, order_id: str, items: List[str]) -> Any:
        ...

    async def create_refund(self, business_id: str, order_id: str, amount: str, reason: str) -> Any:
        ...
