from fastapi import APIRouter, Depends
from app.schemas import ChatRequest, ChatResponse
from app.core.auth import require_tenant, TenantContext

router = APIRouter(prefix="/demo", tags=["Demo"])

@router.post("/chat", response_model=ChatResponse)
async def demo_chat(
    req: ChatRequest, 
    tenant: TenantContext = Depends(require_tenant)
) -> ChatResponse:
    """Isolated chat endpoint for demo scenarios."""
    from app.main import _run_turn
    return await _run_turn(req, tenant)
