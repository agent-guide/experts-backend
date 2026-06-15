from fastapi import APIRouter, Depends

from app.api.deps import get_database, require_platform_permission
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.knowledge import (
    CreateKnowledgeBaseRequest,
    KnowledgeBase,
    KnowledgeBaseListResponse,
    UpdateKnowledgeBaseRequest,
)
from app.services.knowledge_base_service import KnowledgeBaseService

router = APIRouter()


@router.post("", response_model=KnowledgeBase, status_code=201)
async def create_knowledge_base(
    body: CreateKnowledgeBaseRequest,
    principal: Principal = Depends(require_platform_permission("kb:create")),
    connection: DatabaseConnection = Depends(get_database),
) -> KnowledgeBase:
    return KnowledgeBaseService(connection).create(principal, body)


@router.get("", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    principal: Principal = Depends(require_platform_permission("kb:read")),
    connection: DatabaseConnection = Depends(get_database),
) -> KnowledgeBaseListResponse:
    items = KnowledgeBaseService(connection).list(principal)
    return KnowledgeBaseListResponse(items=items)


@router.get("/{knowledge_base_id}", response_model=KnowledgeBase)
async def get_knowledge_base(
    knowledge_base_id: str,
    principal: Principal = Depends(require_platform_permission("kb:read")),
    connection: DatabaseConnection = Depends(get_database),
) -> KnowledgeBase:
    return KnowledgeBaseService(connection).get(principal, knowledge_base_id)


@router.patch("/{knowledge_base_id}", response_model=KnowledgeBase)
async def update_knowledge_base(
    knowledge_base_id: str,
    body: UpdateKnowledgeBaseRequest,
    principal: Principal = Depends(require_platform_permission("kb:update")),
    connection: DatabaseConnection = Depends(get_database),
) -> KnowledgeBase:
    return KnowledgeBaseService(connection).update(principal, knowledge_base_id, body)


@router.delete("/{knowledge_base_id}", status_code=204)
async def delete_knowledge_base(
    knowledge_base_id: str,
    principal: Principal = Depends(require_platform_permission("kb:delete")),
    connection: DatabaseConnection = Depends(get_database),
) -> None:
    KnowledgeBaseService(connection).delete(principal, knowledge_base_id)
    return None
