from fastapi import APIRouter, Depends

from app.api.deps import get_database, get_object_store, get_settings, require_platform_permission
from app.core.config import Settings
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.knowledge import (
    CompleteUploadRequest,
    CompleteUploadsRequest,
    CompleteUploadsResponse,
    Document,
    DocumentListResponse,
    DownloadUrlResponse,
    UpdateDocumentRequest,
    UploadUrlRequest,
    UploadUrlResponse,
    UploadUrlsRequest,
    UploadUrlsResponse,
)
from app.services.document_service import DocumentService
from app.services.object_store import ObjectStore

# Mounted under /knowledge-bases/{knowledge_base_id}/docs (see app/api/v1/router.py). Documents
# are platform-authored resources nested under a knowledge base; there is no tenant context.
router = APIRouter()


def _service(
    connection: DatabaseConnection,
    object_store: ObjectStore | None,
    settings: Settings,
) -> DocumentService:
    return DocumentService(connection, object_store, settings)


@router.post("/upload-url", response_model=UploadUrlResponse)
async def create_upload_url(
    knowledge_base_id: str,
    body: UploadUrlRequest,
    principal: Principal = Depends(require_platform_permission("doc:create")),
    connection: DatabaseConnection = Depends(get_database),
    object_store: ObjectStore = Depends(get_object_store),
    settings: Settings = Depends(get_settings),
) -> UploadUrlResponse:
    return _service(connection, object_store, settings).create_upload_url(
        principal, knowledge_base_id, body
    )


@router.post("/upload-urls", response_model=UploadUrlsResponse)
async def create_upload_urls(
    knowledge_base_id: str,
    body: UploadUrlsRequest,
    principal: Principal = Depends(require_platform_permission("doc:create")),
    connection: DatabaseConnection = Depends(get_database),
    object_store: ObjectStore = Depends(get_object_store),
    settings: Settings = Depends(get_settings),
) -> UploadUrlsResponse:
    return _service(connection, object_store, settings).create_upload_urls(
        principal, knowledge_base_id, body
    )


@router.post("/complete-upload", response_model=Document, status_code=201)
async def complete_upload(
    knowledge_base_id: str,
    body: CompleteUploadRequest,
    principal: Principal = Depends(require_platform_permission("doc:create")),
    connection: DatabaseConnection = Depends(get_database),
    object_store: ObjectStore = Depends(get_object_store),
    settings: Settings = Depends(get_settings),
) -> Document:
    return _service(connection, object_store, settings).complete_upload(
        principal, knowledge_base_id, body
    )


# Returns 200 (not 201): the batch is non-atomic, so the body reports per-item outcomes rather
# than asserting every document was created.
@router.post("/complete-uploads", response_model=CompleteUploadsResponse)
async def complete_uploads(
    knowledge_base_id: str,
    body: CompleteUploadsRequest,
    principal: Principal = Depends(require_platform_permission("doc:create")),
    connection: DatabaseConnection = Depends(get_database),
    object_store: ObjectStore = Depends(get_object_store),
    settings: Settings = Depends(get_settings),
) -> CompleteUploadsResponse:
    return _service(connection, object_store, settings).complete_uploads(
        principal, knowledge_base_id, body
    )


# list / get / update / soft-delete are pure DB operations -- they intentionally do NOT depend on
# get_object_store, so they keep working when MinIO is unconfigured or unreachable.
@router.get("", response_model=DocumentListResponse)
async def list_documents(
    knowledge_base_id: str,
    principal: Principal = Depends(require_platform_permission("doc:read")),
    connection: DatabaseConnection = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> DocumentListResponse:
    items = _service(connection, None, settings).list_documents(
        principal, knowledge_base_id
    )
    return DocumentListResponse(items=items)


@router.get("/{document_id}", response_model=Document)
async def get_document(
    knowledge_base_id: str,
    document_id: str,
    principal: Principal = Depends(require_platform_permission("doc:read")),
    connection: DatabaseConnection = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> Document:
    return _service(connection, None, settings).get_document(
        principal, knowledge_base_id, document_id
    )


@router.patch("/{document_id}", response_model=Document)
async def update_document(
    knowledge_base_id: str,
    document_id: str,
    body: UpdateDocumentRequest,
    principal: Principal = Depends(require_platform_permission("doc:update")),
    connection: DatabaseConnection = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> Document:
    return _service(connection, None, settings).update_document(
        principal, knowledge_base_id, document_id, body
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    knowledge_base_id: str,
    document_id: str,
    principal: Principal = Depends(require_platform_permission("doc:delete")),
    connection: DatabaseConnection = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> None:
    _service(connection, None, settings).delete_document(
        principal, knowledge_base_id, document_id
    )
    return None


@router.get("/{document_id}/download-url", response_model=DownloadUrlResponse)
async def get_download_url(
    knowledge_base_id: str,
    document_id: str,
    principal: Principal = Depends(require_platform_permission("doc:read")),
    connection: DatabaseConnection = Depends(get_database),
    object_store: ObjectStore = Depends(get_object_store),
    settings: Settings = Depends(get_settings),
) -> DownloadUrlResponse:
    return _service(connection, object_store, settings).download_url(
        principal, knowledge_base_id, document_id
    )
