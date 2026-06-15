from fastapi import APIRouter, Depends

from app.api.deps import require_tenant_principal
from app.domain.auth import Principal

router = APIRouter()


@router.get("/llm")
async def list_llm_models(_: Principal = Depends(require_tenant_principal)) -> dict:
    return {"models": [{"id": "codex/gpt-5", "isDefault": True}]}


@router.get("/embedding")
async def get_embedding_model(_: Principal = Depends(require_tenant_principal)) -> dict:
    return {"provider": "pageindex", "model": "pageindex-managed"}
