from fastapi import APIRouter, Depends

from app.api.deps import get_pageindex_client, require_permission
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
    _: Principal = Depends(require_permission("doc:upload")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request("POST", "/uploads/initiate", json=body.model_dump())


@router.post("/complete", status_code=202)
async def complete_upload(
    body: CompleteUploadRequest,
    _: Principal = Depends(require_permission("doc:upload")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request("POST", "/uploads/complete", json=body.model_dump(exclude_none=True))


@router.post("/multipart/initiate")
async def initiate_multipart_upload(
    body: InitiateUploadRequest,
    _: Principal = Depends(require_permission("doc:upload")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request("POST", "/uploads/multipart/initiate", json=body.model_dump())


@router.post("/multipart/parts")
async def multipart_parts(
    body: MultipartPartsRequest,
    _: Principal = Depends(require_permission("doc:upload")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request("POST", "/uploads/multipart/parts", json=body.model_dump())


@router.post("/multipart/complete", status_code=202)
async def complete_multipart_upload(
    body: CompleteMultipartRequest,
    _: Principal = Depends(require_permission("doc:upload")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> dict:
    return await pageindex.request(
        "POST", "/uploads/multipart/complete", json=body.model_dump(exclude_none=True)
    )


@router.post("/multipart/abort", status_code=204)
async def abort_multipart_upload(
    body: AbortMultipartRequest,
    _: Principal = Depends(require_permission("doc:upload")),
    pageindex: PageIndexClient = Depends(get_pageindex_client),
) -> None:
    await pageindex.request("POST", "/uploads/multipart/abort", json=body.model_dump())
    return None
