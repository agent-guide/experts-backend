from fastapi import APIRouter, Depends, Query

from app.api.deps import get_database, get_object_store, get_settings, require_tenant_permission
from app.core.config import Settings
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.library import (
    LibraryCompleteUploadRequest,
    LibraryDeletedResponse,
    LibraryDownloadResponse,
    LibraryFile,
    LibraryFileListResponse,
    LibraryPreviewResponse,
    LibrarySort,
    LibraryUploadUrlRequest,
    LibraryUploadUrlResponse,
)
from app.services.library_service import LibraryService
from app.services.object_store import ObjectStore

router = APIRouter()


def _service(
    connection: DatabaseConnection,
    object_store: ObjectStore,
    settings: Settings,
) -> LibraryService:
    return LibraryService(connection, object_store, settings)


@router.get("/files", response_model=LibraryFileListResponse)
async def list_files(
    keyword: str | None = None,
    type: str = Query(default="all", pattern="^(all|image|file)$"),  # noqa: A002 - API field
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),  # noqa: N803 - API field
    sort: LibrarySort = "updatedAt_desc",
    # docs/LIBRARY_FILE_LIFECYCLE.md §11. Default is permanent-only. lifecycle=temporary lists the
    # caller's non-expired temporary files: all of them (bound and unbound) without sessionId, or a
    # single session's bound ones when sessionId is given. Both stay owner-scoped, so there is no
    # cross-user exposure.
    lifecycle: str = Query(default="permanent", pattern="^(permanent|temporary)$"),
    sessionId: str | None = None,  # noqa: N803 - API field
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    connection: DatabaseConnection = Depends(get_database),
    object_store: ObjectStore = Depends(get_object_store),
    settings: Settings = Depends(get_settings),
) -> LibraryFileListResponse:
    return _service(connection, object_store, settings).list_files(
        principal,
        keyword=keyword,
        file_type=type,
        sort=sort,
        page=page,
        page_size=pageSize,
        lifecycle=lifecycle,
        session_id=sessionId,
    )


@router.post("/files/upload-url", response_model=LibraryUploadUrlResponse)
async def create_upload_url(
    body: LibraryUploadUrlRequest,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    connection: DatabaseConnection = Depends(get_database),
    object_store: ObjectStore = Depends(get_object_store),
    settings: Settings = Depends(get_settings),
) -> LibraryUploadUrlResponse:
    return _service(connection, object_store, settings).create_upload_url(principal, body)


@router.post("/files/complete-upload", response_model=LibraryFile, status_code=201)
async def complete_upload(
    body: LibraryCompleteUploadRequest,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    connection: DatabaseConnection = Depends(get_database),
    object_store: ObjectStore = Depends(get_object_store),
    settings: Settings = Depends(get_settings),
) -> LibraryFile:
    return _service(connection, object_store, settings).complete_upload(principal, body)


@router.post("/files/{file_id}/promote", response_model=LibraryFile)
async def promote_file(
    file_id: str,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    connection: DatabaseConnection = Depends(get_database),
    object_store: ObjectStore = Depends(get_object_store),
    settings: Settings = Depends(get_settings),
) -> LibraryFile:
    return _service(connection, object_store, settings).promote_file(principal, file_id)


@router.get("/files/{file_id}/preview", response_model=LibraryPreviewResponse)
async def preview_file(
    file_id: str,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    connection: DatabaseConnection = Depends(get_database),
    object_store: ObjectStore = Depends(get_object_store),
    settings: Settings = Depends(get_settings),
) -> LibraryPreviewResponse:
    return _service(connection, object_store, settings).preview_file(principal, file_id)


@router.get("/files/{file_id}/download", response_model=LibraryDownloadResponse)
async def download_file(
    file_id: str,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    connection: DatabaseConnection = Depends(get_database),
    object_store: ObjectStore = Depends(get_object_store),
    settings: Settings = Depends(get_settings),
) -> LibraryDownloadResponse:
    return _service(connection, object_store, settings).download_file(principal, file_id)


@router.delete("/files/{file_id}", response_model=LibraryDeletedResponse)
async def delete_file(
    file_id: str,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    connection: DatabaseConnection = Depends(get_database),
    object_store: ObjectStore = Depends(get_object_store),
    settings: Settings = Depends(get_settings),
) -> LibraryDeletedResponse:
    return _service(connection, object_store, settings).delete_file(principal, file_id)
