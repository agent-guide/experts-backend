from __future__ import annotations

import re
import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.parse import quote
from uuid import uuid4
from xml.etree import ElementTree

from app.core.config import Settings
from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.library import (
    LibraryDeletedResponse,
    LibraryDownloadResponse,
    LibraryFile,
    LibraryFileRecord,
    LibraryFileType,
    LibraryFileListResponse,
    LibraryPreviewResponse,
    LibrarySort,
)
from app.services.library_repository import LibraryRepository
from app.services.object_store import ObjectStore


_IMAGE_MIME_PREFIX = "image/"
_TEXT_MIME_PREFIX = "text/"
_INLINE_TEXT_MIME = {
    "application/json",
    "text/csv",
    "text/markdown",
    "text/plain",
}
_INLINE_TEXT_EXTENSIONS = {"txt", "md", "csv", "json"}
_PDF_MIME = "application/pdf"
_DOCX_EXTENSIONS = {"docx"}
_ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "gif",
    "webp",
    "bmp",
    "svg",
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "txt",
    "md",
    "csv",
    "json",
}
_FILE_TYPE_BY_EXT = {
    "jpg": "image",
    "jpeg": "image",
    "png": "image",
    "gif": "image",
    "webp": "image",
    "bmp": "image",
    "svg": "image",
}


class LibraryService:
    def __init__(self, connection: DatabaseConnection, store: ObjectStore, settings: Settings) -> None:
        self.connection = connection
        self.store = store
        self.settings = settings
        self.repo = LibraryRepository(connection)

    def list_files(
        self,
        principal: Principal,
        *,
        keyword: str | None,
        file_type: str,
        sort: LibrarySort,
        page: int,
        page_size: int,
    ) -> LibraryFileListResponse:
        owner = self._owner(principal)
        normalized_type = None if file_type == "all" else file_type
        items, total = self.repo.list_files(
            user_id=owner[0],
            tenant_id=owner[1],
            keyword=keyword.strip() if keyword else None,
            file_type=normalized_type,
            sort=sort,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        return LibraryFileListResponse(
            items=[_to_item(file) for file in items],
            total=total,
            page=page,
            pageSize=page_size,
        )

    def upload_file(
        self,
        principal: Principal,
        *,
        file_name: str,
        mime_type: str | None,
        content: bytes,
    ) -> LibraryFile:
        user_id, tenant_id = self._owner(principal)
        safe_name = _safe_file_name(file_name)
        extension = _extension(safe_name)
        file_type = _resolve_file_type(safe_name, mime_type)
        preview_supported = _preview_supported(mime_type, extension, file_type)
        file_id = f"file_{uuid4().hex}"
        object_key = _object_key(tenant_id, user_id, file_id, safe_name)
        now = _now_iso()
        self.store.put(object_key, content, content_type=mime_type)
        self.repo.create_file(
            file_id=file_id,
            user_id=user_id,
            tenant_id=tenant_id,
            original_name=file_name,
            safe_name=safe_name,
            mime_type=mime_type,
            file_type=file_type,
            extension=extension,
            size_bytes=len(content),
            storage_bucket=self.store.bucket,
            storage_object_key=object_key,
            content_hash=None,
            preview_supported=preview_supported,
            metadata={},
            now=now,
        )
        self.connection.commit()
        file = self.repo.get_file(user_id, tenant_id, file_id)
        assert file is not None
        return _to_item(file)

    def preview_file(self, principal: Principal, file_id: str) -> LibraryPreviewResponse:
        record = self._require_file(principal, file_id)
        if not _record_preview_supported(record):
            return LibraryPreviewResponse(previewType="unsupported")
        if record.extension in _DOCX_EXTENSIONS:
            content = _extract_docx_text(
                self.store.read(record.storageObjectKey, max_bytes=10 * 1024 * 1024)
            )
            return LibraryPreviewResponse(
                previewType="text",
                content=content,
                mimeType=record.mimeType,
            )
        if _is_text_preview(record.mimeType, record.extension):
            content = self.store.read(record.storageObjectKey, max_bytes=1024 * 1024).decode(
                "utf-8", errors="replace"
            )
            return LibraryPreviewResponse(
                previewType="text",
                content=content,
                mimeType=record.mimeType,
            )
        return LibraryPreviewResponse(
            previewType="url",
            url=self.store.presigned_get_url(
                record.storageObjectKey,
                expires=timedelta(seconds=self.settings.presigned_url_ttl_seconds),
                response_headers=_preview_response_headers(record),
            ),
            mimeType=record.mimeType,
            expiresAt=_now_plus_ttl(self.settings.presigned_url_ttl_seconds),
        )

    def download_file(self, principal: Principal, file_id: str) -> LibraryDownloadResponse:
        record = self._require_file(principal, file_id)
        return LibraryDownloadResponse(
            downloadUrl=self.store.presigned_get_url(
                record.storageObjectKey, expires=timedelta(seconds=self.settings.presigned_url_ttl_seconds)
            ),
            expiresAt=_now_plus_ttl(self.settings.presigned_url_ttl_seconds),
        )

    def delete_file(self, principal: Principal, file_id: str) -> LibraryDeletedResponse:
        user_id, tenant_id = self._owner(principal)
        now = _now_iso()
        deleted = self.repo.soft_delete_file(user_id, tenant_id, file_id, now)
        if not deleted:
            raise ApiError(404, "LIBRARY_FILE_NOT_FOUND", "Library file not found")
        self.connection.commit()
        return LibraryDeletedResponse(id=file_id)

    def purge_deleted_files(self, limit: int = 100) -> int:
        deleted = self.repo.list_deleted(limit)
        purged = 0
        for file_id, storage_key in deleted:
            try:
                self.store.remove(storage_key)
            except Exception:  # noqa: BLE001 - best effort, retry on next GC pass
                continue
            self.repo.hard_delete_file(file_id)
            purged += 1
        self.connection.commit()
        return purged

    def _require_file(self, principal: Principal, file_id: str) -> LibraryFileRecord:
        user_id, tenant_id = self._owner(principal)
        record = self.repo.get_file(user_id, tenant_id, file_id)
        if record is None:
            raise ApiError(404, "LIBRARY_FILE_NOT_FOUND", "Library file not found")
        return record

    @staticmethod
    def _owner(principal: Principal) -> tuple[str, str]:
        if principal.active_tenant_id is None:
            raise ApiError(401, "AUTH_UNAUTHORIZED", "Missing active tenant")
        return principal.user_id, str(principal.active_tenant_id)


def _to_item(record: LibraryFileRecord) -> LibraryFile:
    return LibraryFile(
        id=record.id,
        name=record.originalName,
        mimeType=record.mimeType,
        type=record.fileType,
        sizeBytes=record.sizeBytes,
        sizeLabel=_size_label(record.sizeBytes),
        updatedAt=record.updatedAt,
        createdAt=record.createdAt,
        previewSupported=_record_preview_supported(record),
    )


def _object_key(tenant_id: str, user_id: str, file_id: str, safe_name: str) -> str:
    return f"library/{tenant_id}/users/{user_id}/{file_id}/{safe_name}"


def _safe_file_name(file_name: str) -> str:
    safe = file_name.replace("\\", "/").split("/")[-1].strip()
    safe = re.sub(r"[\x00-\x1f\x7f]", "", safe)
    if not safe or safe in {".", ".."}:
        raise ApiError(400, "LIBRARY_INVALID_FILE_NAME", "Invalid file name")
    return safe


def _extension(file_name: str) -> str | None:
    if "." not in file_name:
        return None
    return file_name.rsplit(".", 1)[1].lower() or None


def _resolve_file_type(file_name: str, mime_type: str | None) -> LibraryFileType:
    ext = _extension(file_name)
    if ext in _FILE_TYPE_BY_EXT:
        return _FILE_TYPE_BY_EXT[ext]
    if mime_type and mime_type.startswith(_IMAGE_MIME_PREFIX):
        return "image"
    return "file"


def _preview_supported(mime_type: str | None, extension: str | None, file_type: LibraryFileType) -> bool:
    if file_type == "image":
        return True
    if mime_type == _PDF_MIME or extension == "pdf":
        return True
    if extension in _DOCX_EXTENSIONS:
        return True
    if mime_type in _INLINE_TEXT_MIME:
        return True
    if mime_type and mime_type.startswith(_TEXT_MIME_PREFIX):
        return True
    return extension in _INLINE_TEXT_EXTENSIONS


def _record_preview_supported(record: LibraryFileRecord) -> bool:
    return _preview_supported(record.mimeType, record.extension, record.fileType)


def _is_text_preview(mime_type: str | None, extension: str | None) -> bool:
    if mime_type == _PDF_MIME or extension == "pdf":
        return False
    if extension in _DOCX_EXTENSIONS:
        return True
    return _preview_supported(mime_type, extension, "file")


def _preview_response_headers(record: LibraryFileRecord) -> dict[str, str] | None:
    if record.mimeType == _PDF_MIME or record.extension == "pdf":
        return {
            "response-content-type": _PDF_MIME,
            "response-content-disposition": _inline_content_disposition(record.safeName),
        }
    if record.mimeType and record.fileType == "image":
        return {
            "response-content-type": record.mimeType,
            "response-content-disposition": _inline_content_disposition(record.safeName),
        }
    if record.mimeType:
        return {
            "response-content-type": record.mimeType,
            "response-content-disposition": _inline_content_disposition(record.safeName),
        }
    return None


def _inline_content_disposition(file_name: str) -> str:
    fallback = re.sub(r'["\\]', "_", file_name)
    fallback = "".join(char if 0x20 <= ord(char) < 0x7F else "_" for char in fallback)
    fallback = fallback or "download"
    encoded = quote(file_name, safe="")
    return f"inline; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


def _size_label(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f}".rstrip("0").rstrip(".") + f" {unit}"
        value /= 1024
    return f"{size} B"


def _extract_docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise ApiError(400, "LIBRARY_PREVIEW_UNAVAILABLE", "DOCX preview is unavailable") from exc
    root = ElementTree.fromstring(xml)
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{namespace}p"):
        parts = [text.text or "" for text in paragraph.iter(f"{namespace}t")]
        line = "".join(parts).strip()
        if line:
            paragraphs.append(line)
    return "\n".join(paragraphs)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_plus_ttl(ttl_seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
