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
    LibraryCompleteUploadRequest,
    LibraryDeletedResponse,
    LibraryDownloadResponse,
    LibraryFile,
    LibraryFileRecord,
    LibraryFileType,
    LibraryFileListResponse,
    LibraryPreviewResponse,
    LibrarySort,
    LibraryUploadSessionRecord,
    LibraryUploadUrlRequest,
    LibraryUploadUrlResponse,
)
from app.services._sql import is_unique_violation
from app.services.library_repository import LibraryRepository
from app.services.object_store import ObjectStore, best_effort_remove, remove_if_present


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
        lifecycle: str = "permanent",
        session_id: str | None = None,
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
            lifecycle=lifecycle,
            chat_session_id=session_id,
            now=_now_iso() if lifecycle == "temporary" else None,
        )
        return LibraryFileListResponse(
            items=[_to_item(file) for file in items],
            total=total,
            page=page,
            pageSize=page_size,
        )

    def create_upload_url(
        self,
        principal: Principal,
        request: LibraryUploadUrlRequest,
    ) -> LibraryUploadUrlResponse:
        user_id, tenant_id = self._owner(principal)
        return self._allocate_upload(
            user_id,
            tenant_id,
            file_name=request.fileName,
            mime_type=request.mimeType,
            file_size_bytes=request.fileSizeBytes,
        )

    def _allocate_upload(
        self,
        user_id: str,
        tenant_id: str,
        *,
        file_name: str,
        mime_type: str | None,
        file_size_bytes: int,
    ) -> LibraryUploadUrlResponse:
        if file_size_bytes <= 0:
            raise ApiError(400, "LIBRARY_INVALID_SIZE", "fileSizeBytes must be positive")
        if file_size_bytes > self.settings.object_storage_max_upload_bytes:
            raise ApiError(413, "OBJECT_TOO_LARGE", "Object upload is too large")

        safe_name = _safe_file_name(file_name)
        extension = _extension(safe_name)
        file_type = _resolve_file_type(safe_name, mime_type)
        file_id = f"file_{uuid4().hex}"
        session_id = f"upl_{uuid4().hex}"
        object_key = _object_key(tenant_id, user_id, file_id, safe_name)
        now = _now_iso()
        expires = _now_plus_ttl(self.settings.presigned_url_ttl_seconds)

        self.repo.create_upload_session(
            session_id=session_id,
            file_id=file_id,
            user_id=user_id,
            tenant_id=tenant_id,
            original_name=file_name,
            safe_name=safe_name,
            mime_type=mime_type,
            file_type=file_type,
            extension=extension,
            file_size_bytes=file_size_bytes,
            storage_bucket=self.store.bucket,
            storage_object_key=object_key,
            content_hash=None,
            expires_at=expires,
            now=now,
        )
        upload_url = self.store.presigned_put_url(
            object_key,
            expires=timedelta(seconds=self.settings.presigned_url_ttl_seconds),
            content_type=mime_type,
            content_length=file_size_bytes,
        )
        self.connection.commit()

        headers = {"Content-Type": mime_type} if mime_type else {}
        return LibraryUploadUrlResponse(
            uploadSessionId=session_id,
            fileId=file_id,
            uploadUrl=upload_url,
            headers=headers,
            objectKey=object_key,
            expiresAt=expires,
        )

    def complete_upload(
        self,
        principal: Principal,
        request: LibraryCompleteUploadRequest,
    ) -> LibraryFile:
        user_id, tenant_id = self._owner(principal)
        session = self._load_session_for_completion(request.uploadSessionId, user_id, tenant_id)
        # §7: a temporary file is minted unbound (no session) and expires on its retention window;
        # it binds to a session on first turn use (§5). A permanent file is an ordinary library file.
        if request.lifecycle == "temporary":
            source, lifecycle = "chat_upload", "temporary"
            expires_at: str | None = _now_plus_ttl(self.settings.chat_attachment_retention_seconds)
        else:
            source, lifecycle, expires_at = "library", "permanent", None
        record = self._persist_completed_file(
            session,
            user_id,
            tenant_id,
            source=source,
            lifecycle=lifecycle,
            expires_at=expires_at,
        )
        return _to_item(record)

    def promote_file(self, principal: Principal, file_id: str) -> LibraryFile:
        """Promote a temporary chat file to a permanent library file with no byte copy (§10)."""
        user_id, tenant_id = self._owner(principal)
        record = self.repo.promote_file(user_id, tenant_id, file_id, _now_iso())
        if record is None:
            # Distinguish a missing/deleted file (404) from a non-promotable one (409): expired,
            # already permanent. The expiry guard lives in promote_file's SQL where clause.
            if self.repo.get_file(user_id, tenant_id, file_id) is None:
                raise ApiError(404, "LIBRARY_FILE_NOT_FOUND", "Library file not found")
            raise ApiError(
                409,
                "LIBRARY_FILE_NOT_PROMOTABLE",
                "File is not a promotable temporary file (expired, already permanent, or deleted)",
            )
        self.connection.commit()
        return _to_item(record)

    def _load_session_for_completion(
        self, upload_session_id: str, user_id: str, tenant_id: str
    ) -> LibraryUploadSessionRecord:
        """Load and validate an upload session for completion (owner, status, expiry, size).

        Shared by the library and chat complete-upload paths; the lifecycle/routing decision is
        made by each caller after this returns.
        """
        session = self.repo.get_upload_session(upload_session_id)
        if session is None:
            raise ApiError(404, "LIBRARY_UPLOAD_SESSION_NOT_FOUND", "Upload session not found")
        if session.userId != user_id or session.tenantId != tenant_id:
            raise ApiError(404, "LIBRARY_UPLOAD_SESSION_NOT_FOUND", "Upload session not found")
        if session.status != "initiated":
            raise ApiError(409, "LIBRARY_UPLOAD_SESSION_NOT_ACTIVE", "Upload session is not active")
        if _expired(session.expiresAt):
            self.repo.set_upload_session_status(session.id, "expired", _now_iso())
            self.connection.commit()
            raise ApiError(409, "LIBRARY_UPLOAD_SESSION_EXPIRED", "Upload session has expired")

        stat = self.store.stat(session.storageObjectKey)
        if stat.size != session.fileSizeBytes:
            self.repo.set_upload_session_status(session.id, "failed", _now_iso())
            self.connection.commit()
            best_effort_remove(self.store, session.storageObjectKey)
            raise ApiError(
                400,
                "LIBRARY_UPLOAD_SIZE_MISMATCH",
                "Uploaded object size does not match the declared size",
                {"declared": session.fileSizeBytes, "actual": stat.size},
            )
        return session

    def _persist_completed_file(
        self,
        session: LibraryUploadSessionRecord,
        user_id: str,
        tenant_id: str,
        *,
        source: str,
        lifecycle: str,
        expires_at: str | None,
        chat_session_id: str | None = None,
    ) -> LibraryFileRecord:
        now = _now_iso()
        try:
            record = self.repo.create_file(
                file_id=session.fileId,
                user_id=user_id,
                tenant_id=tenant_id,
                original_name=session.originalName,
                safe_name=session.safeName,
                mime_type=session.mimeType,
                file_type=session.fileType,
                extension=session.extension,
                size_bytes=session.fileSizeBytes,
                storage_bucket=session.storageBucket,
                storage_object_key=session.storageObjectKey,
                # A single presigned PUT only gives us object size/ETag, not a verifiable sha256.
                # Keep client-declared contentHash off the durable file row until a trusted
                # server-side hash pass exists.
                content_hash=None,
                preview_supported=_preview_supported(
                    session.mimeType, session.extension, session.fileType
                ),
                metadata={},
                now=now,
                source=source,
                lifecycle=lifecycle,
                expires_at=expires_at,
                chat_session_id=chat_session_id,
            )
        except Exception as exc:  # noqa: BLE001 - mapped only for documented completion race
            if is_unique_violation(exc):
                self.connection.rollback()
                raise ApiError(
                    409,
                    "LIBRARY_UPLOAD_ALREADY_COMPLETED",
                    "Upload session has already been completed",
                ) from exc
            raise

        self.repo.set_upload_session_status(session.id, "completed", now, completed=True)
        self.connection.commit()
        return record

    def resolve_turn_attachments(
        self, principal: Principal, session_id: str, file_ids: list[str], *, bind: bool
    ) -> list[LibraryFileRecord]:
        """Load and §5-authorize the files a turn references, auto-binding temporaries (§7.3).

        Authorization by kind:
        - permanent: readable by its owner in any session.
        - temporary, unbound (chat_session_id is null): readable by its owner. With bind=True it is
          bound to this session (once); with bind=False (pre-flight) it is allowed as-is.
        - temporary, bound to this session: readable while not expired.
        - temporary, bound to another session: rejected.

        Raises rather than silently dropping an unauthorized id, so a turn never half-references
        files it was denied. bind=True commits the binding.
        """
        records: list[LibraryFileRecord] = []
        user_id, tenant_id = self._owner(principal)
        bound_any = False
        for file_id in file_ids:
            record = self.repo.get_file(user_id, tenant_id, file_id)
            if record is None:
                raise ApiError(404, "LIBRARY_FILE_NOT_FOUND", f"Library file not found: {file_id}")
            if record.lifecycle == "temporary":
                if record.expiresAt is None or _expired(record.expiresAt):
                    raise ApiError(
                        403, "LIBRARY_FILE_FORBIDDEN", f"Attachment has expired: {file_id}"
                    )
                if record.chatSessionId is None and bind:
                    # First turn to reference this file binds it to this session (once). A
                    # concurrent turn in another session may win the race, so re-read the outcome.
                    bound = self.repo.bind_temporary_file_session(
                        user_id, tenant_id, file_id, session_id, _now_iso()
                    )
                    record = bound or self.repo.get_file(user_id, tenant_id, file_id) or record
                    bound_any = True
                if record.chatSessionId is not None and record.chatSessionId != session_id:
                    raise ApiError(
                        403,
                        "LIBRARY_FILE_FORBIDDEN",
                        f"Attachment is bound to another session: {file_id}",
                    )
            records.append(record)
        if bound_any:
            self.connection.commit()
        return records

    @staticmethod
    def attachment_snapshot(records: list[LibraryFileRecord], attached_at: str) -> list[dict]:
        """Denormalized per-turn provenance snapshot (§9). Self-contained by design."""
        return [
            {
                "fileId": record.id,
                "name": record.originalName,
                "mimeType": record.mimeType,
                "sizeBytes": record.sizeBytes,
                "lifecycle": record.lifecycle,
                "attachedAt": attached_at,
            }
            for record in records
        ]

    def attachment_delivery_url(self, record: LibraryFileRecord) -> str:
        """Presigned GET URL for URL-based delivery (§8.2, option A).

        The engine receives a short-lived URL instead of inlined content, and fetches the file
        itself. Works uniformly for every type (text, DOCX, image, PDF). The TTL is sized to
        outlive a full turn (attachment_delivery_url_ttl_seconds).
        """
        return self.store.presigned_get_url(
            record.storageObjectKey,
            expires=timedelta(seconds=self.settings.attachment_delivery_url_ttl_seconds),
        )

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

    def expire_stale_sessions(self) -> int:
        """Expire timed-out upload sessions and remove their orphan objects."""
        now = _now_iso()
        sessions = self.repo.list_expired_upload_sessions(now)
        reclaimed = 0
        for session in sessions:
            if remove_if_present(self.store, session.storageObjectKey):
                self.repo.set_upload_session_status(session.id, "expired", now)
                reclaimed += 1
        self.connection.commit()
        return reclaimed

    def purge_deleted_files(self, limit: int = 100) -> int:
        deleted = self.repo.list_deleted(limit)
        purged = 0
        for file_id, storage_key in deleted:
            if remove_if_present(self.store, storage_key):
                self.repo.hard_delete_file(file_id)
                purged += 1
        self.connection.commit()
        return purged

    def purge_expired_temporary_files(self, limit: int = 100) -> int:
        """Temporary-file GC pass (§12.2).

        Hard-delete the rows of expired temporary attachments and remove their objects (the
        default: §9's provenance snapshot already preserves history, so the row need not linger).
        Promotion clears expires_at, so promoted files are excluded. There is no on-disk delivery
        copy to reclaim -- delivery is content-only (§12.3).
        """
        now = _now_iso()
        expired = self.repo.list_expired_temporary_files(now, limit)
        purged = 0
        for file_id, storage_key in expired:
            if remove_if_present(self.store, storage_key):
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
        lifecycle=record.lifecycle,
        expiresAt=record.expiresAt,
        updatedAt=record.updatedAt,
        createdAt=record.createdAt,
        previewSupported=_record_preview_supported(record),
    )


def _object_key(tenant_id: str, user_id: str, file_id: str, safe_name: str) -> str:
    return f"library/{tenant_id}/users/{user_id}/{file_id}/{_ascii_key_name(safe_name)}"


def _ascii_key_name(safe_name: str) -> str:
    """ASCII-only name for the storage object key.

    Non-ASCII object keys (e.g. Chinese filenames) force PyJWT to emit \\uXXXX escapes inside the
    signed presigned-URL token; clients that re-encode the URL strip those backslashes and corrupt
    the signature (401). The display name is kept separately as original_name, so the key name is
    cosmetic -- collapse anything outside [A-Za-z0-9._-] to '_' and preserve the extension.
    """
    stem, dot, ext = safe_name.rpartition(".")
    base = stem if dot else safe_name
    ext = ext if dot else ""
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._-") or "file"
    ext = re.sub(r"[^A-Za-z0-9]+", "", ext)
    return f"{base}.{ext}" if ext else base


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


def _expired(value: str) -> bool:
    expires_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)
