from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.api.deps import get_database, get_object_store, get_settings, require_tenant_permission
from app.core.config import Settings
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.library import (
    LibraryDeletedResponse,
    LibraryDownloadResponse,
    LibraryFile,
    LibraryFileListResponse,
    LibraryPreviewResponse,
    LibrarySort,
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
    )


@router.post("/files", response_model=LibraryFile, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    connection: DatabaseConnection = Depends(get_database),
    object_store: ObjectStore = Depends(get_object_store),
    settings: Settings = Depends(get_settings),
) -> LibraryFile:
    content = await file.read()
    return _service(connection, object_store, settings).upload_file(
        principal,
        file_name=file.filename or "upload.bin",
        mime_type=file.content_type,
        content=content,
    )


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
