from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service, get_pageindex_client, require_permission
from app.clients.pageindex import PageIndexClient
from app.domain.auth import GrantRoleRequest, Principal
from app.domain.knowledge import CreateKnowledgeBaseRequest
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/users/{user_id}/roles", status_code=204)
async def grant_role(
    user_id: str,
    body: GrantRoleRequest,
    principal: Principal = Depends(require_permission("role:grant")),
    auth: AuthService = Depends(get_auth_service),
) -> None:
    auth.grant_role(principal.tenant_id, principal.user_id, user_id, body.role)
    return None


@router.post("/official-knowledge-bases", status_code=201)
async def create_official_knowledge_base(
    body: CreateKnowledgeBaseRequest,
    _: Principal = Depends(require_permission("kb:publish_official")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    payload = body.model_dump()
    payload["visibility"] = "official_public"
    return await pageindex.request("POST", "/knowledge-bases", json=payload)
