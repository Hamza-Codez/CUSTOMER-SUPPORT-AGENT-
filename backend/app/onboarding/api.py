from fastapi import APIRouter, HTTPException

from app.schemas import CompleteProfileRequest, AccountView
from app.core.auth import TenantDep
from app.db import get_store
from app.db.base import ProfileRecord, PolicyRecord
from app.rag.embeddings import get_embedder
from app.rag.parser import slugify

router = APIRouter(prefix="/auth", tags=["Onboarding"])

@router.post("/complete-profile", response_model=AccountView)
async def complete_profile(req: CompleteProfileRequest, tenant: TenantDep) -> AccountView:
    store = get_store()

    # A demo token names a business but no account, and a profile hangs off a
    # user row. Without this the insert fails on the foreign key as a 500.
    if not tenant.user_id or not tenant.user_email:
        raise HTTPException(
            status_code=403,
            detail="Completing a profile needs a signed-in account, not a demo token.",
        )

    # Update business name
    await store.update_business_name(tenant.business_id, req.store_name.strip())
    
    # Create or update profile
    profile = ProfileRecord(
        user_id=tenant.user_id,
        whatsapp=req.whatsapp.strip(),
        store_name=req.store_name.strip(),
        store_url=req.store_url.strip(),
        policies_text=req.policies_text.strip(),
        brand_voice=req.brand_voice.strip(),
        status="completed"
    )
    
    await store.save_profile(profile)

    # Embed and store the policies text
    embedder = get_embedder()
    blocks = req.policies_text.split("##")
    valid_blocks = [b.strip() for b in blocks if b.strip()]
    if valid_blocks:
        vectors = await embedder.embed(valid_blocks)
        for i, (block, vector) in enumerate(zip(valid_blocks, vectors)):
            lines = block.split("\n", 1)
            topic = lines[0].strip()
            body = lines[1].strip() if len(lines) > 1 else ""
            if not body:
                body = topic
            ref = f"onboarding.md#{slugify(topic)}"
            await store.upsert_policy(
                PolicyRecord(
                    business_id=tenant.business_id,
                    topic=topic,
                    text=body,
                    source_ref=ref,
                    doc="onboarding.md",
                ),
                vector,
            )
    
    user = await store.get_user_by_email(tenant.user_email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return AccountView(
        user_id=user.user_id,
        username=user.username,
        business_id=user.business_id,
        business_name=req.store_name.strip(),
        email=user.email,
        name=user.name,
        role=user.role,
        profile_completed=True
    )
