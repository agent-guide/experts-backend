from fastapi import APIRouter, Depends

from app.api.deps import get_pageindex_client, require_tenant_permission
from app.clients.pageindex import PageIndexClient
from app.domain.auth import Principal
from app.domain.knowledge import (
    AbortMultipartRequest,
    CompleteMultipartRequest,
    CompleteUploadRequest,
    InitiateUploadRequest,
    MultipartPartsRequest,
)

router = APIRouter()


@router.post("/initiate")
async def initiate_upload(
    body: InitiateUploadRequest,
    principal: Principal = Depends(require_tenant_permission("doc:upload")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request(
        "POST", "/uploads/initiate", tenant_id=principal.active_tenant_id, json=body.model_dump()
    )


@router.post("/complete", status_code=202)
async def complete_upload(
    body: CompleteUploadRequest,
    principal: Principal = Depends(require_tenant_permission("doc:upload")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request(
        "POST",
        "/uploads/complete",
        tenant_id=principal.active_tenant_id,
        json=body.model_dump(exclude_none=True),
    )


@router.post("/multipart/initiate")
async def initiate_multipart_upload(
    body: InitiateUploadRequest,
    principal: Principal = Depends(require_tenant_permission("doc:upload")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request(
        "POST",
        "/uploads/multipart/initiate",
        tenant_id=principal.active_tenant_id,
        json=body.model_dump(),
    )


@router.post("/multipart/parts")
async def multipart_parts(
    body: MultipartPartsRequest,
    principal: Principal = Depends(require_tenant_permission("doc:upload")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request(
        "POST",
        "/uploads/multipart/parts",
        tenant_id=principal.active_tenant_id,
        json=body.model_dump(),
    )


@router.post("/multipart/complete", status_code=202)
async def complete_multipart_upload(
    body: CompleteMultipartRequest,
    principal: Principal = Depends(require_tenant_permission("doc:upload")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request(
        "POST",
        "/uploads/multipart/complete",
        tenant_id=principal.active_tenant_id,
        json=body.model_dump(exclude_none=True),
    )


@router.post("/multipart/abort", status_code=204)
async def abort_multipart_upload(
    body: AbortMultipartRequest,
    principal: Principal = Depends(require_tenant_permission("doc:upload")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> None:
    await pageindex.request(
        "POST",
        "/uploads/multipart/abort",
        tenant_id=principal.active_tenant_id,
        json=body.model_dump(),
    )
    return None
