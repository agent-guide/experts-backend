from fastapi import APIRouter, Depends

from app.api.deps import get_pageindex_client, require_tenant_permission
from app.clients.pageindex import PageIndexClient
from app.domain.auth import Principal

router = APIRouter()


@router.get("/{document_id}")
async def get_document_status(
    document_id: str,
    principal: Principal = Depends(require_tenant_permission("kb:read")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request(
        "GET", f"/documents/{document_id}", tenant_id=principal.active_tenant_id
    )


@router.get("/{document_id}/jobs")
async def list_document_jobs(
    document_id: str,
    principal: Principal = Depends(require_tenant_permission("kb:read")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request(
        "GET", f"/documents/{document_id}/jobs", tenant_id=principal.active_tenant_id
    )


@router.get("/{document_id}/chunks")
async def list_document_chunks(
    document_id: str,
    principal: Principal = Depends(require_tenant_permission("kb:read")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request(
        "GET", f"/documents/{document_id}/chunks", tenant_id=principal.active_tenant_id
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    principal: Principal = Depends(require_tenant_permission("doc:delete")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> None:
    await pageindex.request(
        "DELETE", f"/documents/{document_id}", tenant_id=principal.active_tenant_id
    )
    return None


@router.post("/{document_id}/reindex", status_code=202)
async def reindex_document(
    document_id: str,
    principal: Principal = Depends(require_tenant_permission("doc:reindex")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request(
        "POST", f"/documents/{document_id}/reindex", tenant_id=principal.active_tenant_id
    )
