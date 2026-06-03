from fastapi import APIRouter, Depends

from app.api.deps import get_pageindex_client, require_platform_permission, require_tenant_permission
from app.clients.pageindex import PageIndexClient
from app.domain.auth import Principal
from app.domain.knowledge import CreateKnowledgeBaseRequest, UpdateKnowledgeBaseRequest

router = APIRouter()


@router.post("", status_code=201)
async def create_knowledge_base(
    body: CreateKnowledgeBaseRequest,
    principal: Principal = Depends(require_tenant_permission("kb:create")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request(
        "POST", "/knowledge-bases", tenant_id=principal.active_tenant_id, json=body.model_dump()
    )


@router.post("/official", status_code=201)
async def create_official_knowledge_base(
    body: CreateKnowledgeBaseRequest,
    _: Principal = Depends(require_platform_permission("platform:kb_publish_official")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    payload = body.model_dump()
    payload["visibility"] = "official_public"
    return await pageindex.request("POST", "/knowledge-bases", json=payload)


@router.get("")
async def list_knowledge_bases(
    principal: Principal = Depends(require_tenant_permission("kb:read")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request(
        "GET", "/knowledge-bases", tenant_id=principal.active_tenant_id
    )


@router.get("/{knowledge_base_id}")
async def get_knowledge_base(
    knowledge_base_id: str,
    principal: Principal = Depends(require_tenant_permission("kb:read")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request(
        "GET", f"/knowledge-bases/{knowledge_base_id}", tenant_id=principal.active_tenant_id
    )


@router.patch("/{knowledge_base_id}")
async def update_knowledge_base(
    knowledge_base_id: str,
    body: UpdateKnowledgeBaseRequest,
    principal: Principal = Depends(require_tenant_permission("kb:update")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request(
        "PATCH",
        f"/knowledge-bases/{knowledge_base_id}",
        tenant_id=principal.active_tenant_id,
        json=body.model_dump(exclude_none=True),
    )


@router.delete("/{knowledge_base_id}", status_code=204)
async def delete_knowledge_base(
    knowledge_base_id: str,
    principal: Principal = Depends(require_tenant_permission("kb:delete")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> None:
    await pageindex.request(
        "DELETE", f"/knowledge-bases/{knowledge_base_id}", tenant_id=principal.active_tenant_id
    )
    return None


@router.post("/{knowledge_base_id}/documents", status_code=202)
async def upload_document_multipart() -> dict:
    return {
        "message": "Use /api/v1/uploads/* direct-upload APIs until multipart PageIndex mapping is finalized"
    }


@router.get("/{knowledge_base_id}/documents")
async def list_knowledge_base_documents(
    knowledge_base_id: str,
    principal: Principal = Depends(require_tenant_permission("kb:read")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request(
        "GET",
        f"/knowledge-bases/{knowledge_base_id}/documents",
        tenant_id=principal.active_tenant_id,
    )
