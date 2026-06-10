from __future__ import annotations

import posixpath
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.config import Settings
from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.knowledge import (
    BatchItemError,
    CompleteUploadRequest,
    CompleteUploadResult,
    CompleteUploadsRequest,
    CompleteUploadsResponse,
    Document,
    DownloadUrlResponse,
    UpdateDocumentRequest,
    UploadUrlRequest,
    UploadUrlResponse,
    UploadUrlResult,
    UploadUrlsRequest,
    UploadUrlsResponse,
)
from app.services._sql import is_unique_violation
from app.services.document_repository import DocumentRepository
from app.services.kb_authz import authorize_kb_access
from app.services.knowledge_base_repository import KnowledgeBaseRepository
from app.services.object_store import ObjectStore


# Extension -> documents.file_type whitelist. The upload-url request carries an arbitrary
# fileName/mimeType, so it is mapped to the enum here before signing; unknown types are rejected
# (otherwise complete-upload would violate the documents.file_type CHECK). See design section 7.5.
_EXTENSION_FILE_TYPE = {
    "pdf": "pdf",
    "docx": "docx",
    "pptx": "pptx",
    "xlsx": "xlsx",
    "md": "md",
    "markdown": "md",
    "txt": "txt",
    "text": "txt",
    "html": "html",
    "htm": "html",
    "csv": "csv",
    "json": "json",
}


class DocumentService:
    def __init__(
        self,
        connection: DatabaseConnection,
        object_store: ObjectStore | None,
        settings: Settings,
    ) -> None:
        self.connection = connection
        self.docs = DocumentRepository(connection)
        self.kbs = KnowledgeBaseRepository(connection)
        self._object_store = object_store
        self.settings = settings

    @property
    def store(self) -> ObjectStore:
        # Object storage is only needed to mint/verify presigned URLs and to GC objects. Read,
        # list, update and soft-delete are pure DB operations and pass object_store=None, so they
        # never depend on MinIO being configured or reachable.
        if self._object_store is None:
            raise RuntimeError("This operation requires an object store but none was provided.")
        return self._object_store

    # upload flow ----------------------------------------------------------------

    def create_upload_url(
        self, principal: Principal, knowledge_base_id: str, request: UploadUrlRequest
    ) -> UploadUrlResponse:
        self._authorized_kb(principal, knowledge_base_id, "doc")
        if request.fileSizeBytes <= 0:
            raise ApiError(400, "DOC_INVALID_SIZE", "fileSizeBytes must be positive")

        safe_name = _safe_file_name(request.fileName)
        file_type = _resolve_file_type(safe_name, request.mimeType)

        document_id = f"doc_{uuid4().hex}"
        session_id = f"upl_{uuid4().hex}"
        object_key = _object_key(knowledge_base_id, document_id, safe_name)
        now = _now()
        expires = now + timedelta(seconds=self.settings.presigned_url_ttl_seconds)

        self.docs.create_session(
            session_id=session_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            actor_user_id=principal.user_id,
            file_name=safe_name,
            file_type=file_type,
            content_type=request.mimeType,
            file_size_bytes=request.fileSizeBytes,
            object_bucket=self.store.bucket,
            object_key=object_key,
            expires_at=_iso(expires),
            now=_iso(now),
        )
        upload_url = self.store.presigned_put_url(
            object_key,
            expires=timedelta(seconds=self.settings.presigned_url_ttl_seconds),
            content_type=request.mimeType,
        )
        self.connection.commit()

        headers = {"Content-Type": request.mimeType} if request.mimeType else {}
        return UploadUrlResponse(
            uploadSessionId=session_id,
            documentId=document_id,
            uploadUrl=upload_url,
            headers=headers,
            objectKey=object_key,
            expiresAt=_iso(expires),
        )

    def create_upload_urls(
        self, principal: Principal, knowledge_base_id: str, request: UploadUrlsRequest
    ) -> UploadUrlsResponse:
        # Non-atomic batch: each file is its own transaction. A failure is captured as a per-item
        # error instead of aborting the rest, so the caller can retry only the failed files.
        results: list[UploadUrlResult] = []
        for file_request in request.files:
            try:
                upload = self.create_upload_url(principal, knowledge_base_id, file_request)
                results.append(
                    UploadUrlResult(fileName=file_request.fileName, status="created", upload=upload)
                )
            except ApiError as exc:
                results.append(
                    UploadUrlResult(
                        fileName=file_request.fileName, status="failed", error=_batch_error(exc)
                    )
                )
        return UploadUrlsResponse(items=results)

    def complete_upload(
        self, principal: Principal, knowledge_base_id: str, request: CompleteUploadRequest
    ) -> Document:
        self._authorized_kb(principal, knowledge_base_id, "doc")

        session = self.docs.get_session(request.uploadSessionId)
        if not session:
            raise ApiError(404, "UPLOAD_SESSION_NOT_FOUND", "Upload session not found")
        if session.knowledge_base_id != knowledge_base_id:
            raise ApiError(400, "UPLOAD_SESSION_MISMATCH", "Session does not belong to this knowledge base")
        if session.status != "initiated":
            raise ApiError(409, "UPLOAD_SESSION_NOT_ACTIVE", "Upload session is not active")
        if _expired(session.expires_at):
            self.docs.set_session_status(session.id, "expired", _iso(_now()))
            self.connection.commit()
            raise ApiError(409, "UPLOAD_SESSION_EXPIRED", "Upload session has expired")

        # HEAD the object and enforce the declared size. A presigned PUT does not bound the
        # written size, so the client could upload more than declared; the stored object size
        # (HEAD) is authoritative, never the client-provided fileSizeBytes. See design section 5.3.
        stat = self.store.stat(session.object_key)
        if stat.size != session.file_size_bytes:
            self.docs.set_session_status(session.id, "failed", _iso(_now()))
            self.connection.commit()
            _best_effort_remove(self.store, session.object_key)
            raise ApiError(
                400,
                "UPLOAD_SIZE_MISMATCH",
                "Uploaded object size does not match the declared size",
                {"declared": session.file_size_bytes, "actual": stat.size},
            )

        now = _iso(_now())
        # The status check above is not a lock: two concurrent requests can both read `initiated`
        # before either commits. The documents primary key (session.document_id) is the real guard
        # -- the loser collides on insert and is mapped to 409 instead of surfacing a 500.
        try:
            document = self.docs.create_document(
                document_id=session.document_id,
                knowledge_base_id=knowledge_base_id,
                file_name=session.file_name,
                file_type=session.file_type,
                mime_type=session.content_type,
                storage_key=session.object_key,
                object_bucket=session.object_bucket,
                # ETag is the object MD5 for single PUT, not the sha256 the client may have declared,
                # so contentHash is not verifiable here -- left null, recomputed at build time.
                content_hash=None,
                file_size_bytes=session.file_size_bytes,
                created_by=principal.user_id,
                now=now,
            )
        except Exception as exc:  # noqa: BLE001 - re-raised unless it is the documented race
            if is_unique_violation(exc):
                # Roll back the poisoned transaction (required on PostgreSQL) and report the
                # already-in-progress completion. The winning request owns the document.
                self.connection.rollback()
                raise ApiError(
                    409,
                    "UPLOAD_ALREADY_COMPLETED",
                    "Upload session has already been completed",
                ) from exc
            raise
        self.docs.set_session_status(session.id, "completed", now)
        self.connection.commit()
        return document

    def complete_uploads(
        self, principal: Principal, knowledge_base_id: str, request: CompleteUploadsRequest
    ) -> CompleteUploadsResponse:
        # Non-atomic batch: complete_upload commits per item and leaves the connection clean on
        # ApiError (it commits or rolls back before raising), so a failed item is reported and the
        # loop continues. The caller retries only the failures.
        results: list[CompleteUploadResult] = []
        for item in request.items:
            try:
                document = self.complete_upload(principal, knowledge_base_id, item)
                results.append(
                    CompleteUploadResult(
                        uploadSessionId=item.uploadSessionId, status="completed", document=document
                    )
                )
            except ApiError as exc:
                results.append(
                    CompleteUploadResult(
                        uploadSessionId=item.uploadSessionId,
                        status="failed",
                        error=_batch_error(exc),
                    )
                )
        return CompleteUploadsResponse(items=results)

    # read / update / delete ------------------------------------------------------

    def list_documents(self, principal: Principal, knowledge_base_id: str) -> list[Document]:
        self._authorized_kb(principal, knowledge_base_id, "read")
        return self.docs.list_documents(knowledge_base_id)

    def get_document(
        self, principal: Principal, knowledge_base_id: str, document_id: str
    ) -> Document:
        self._authorized_kb(principal, knowledge_base_id, "read")
        document = self.docs.get_document(knowledge_base_id, document_id)
        if not document:
            raise ApiError(404, "DOC_NOT_FOUND", "Document not found")
        return document

    def update_document(
        self,
        principal: Principal,
        knowledge_base_id: str,
        document_id: str,
        request: UpdateDocumentRequest,
    ) -> Document:
        self._authorized_kb(principal, knowledge_base_id, "doc")
        existing = self.docs.get_document(knowledge_base_id, document_id)
        if not existing:
            raise ApiError(404, "DOC_NOT_FOUND", "Document not found")
        now = _iso(_now())
        updated = self.docs.update_document(
            knowledge_base_id,
            document_id,
            file_name=_safe_file_name(request.fileName) if request.fileName else existing.fileName,
            metadata=request.metadata if request.metadata is not None else existing.metadata,
            now=now,
        )
        if not updated:
            raise ApiError(404, "DOC_NOT_FOUND", "Document not found")
        self.connection.commit()
        return updated

    def delete_document(
        self, principal: Principal, knowledge_base_id: str, document_id: str
    ) -> None:
        self._authorized_kb(principal, knowledge_base_id, "doc")
        now = _iso(_now())
        # Soft delete: retrieval must filter documents.deleted_at is null so the delete is
        # effective immediately. The MinIO object is removed asynchronously by GC. See section 6.
        deleted = self.docs.soft_delete_document(knowledge_base_id, document_id, now)
        if not deleted:
            raise ApiError(404, "DOC_NOT_FOUND", "Document not found")
        self.connection.commit()

    def download_url(
        self, principal: Principal, knowledge_base_id: str, document_id: str
    ) -> DownloadUrlResponse:
        self._authorized_kb(principal, knowledge_base_id, "read")
        storage_key = self.docs.get_storage_key(knowledge_base_id, document_id)
        if not storage_key:
            raise ApiError(404, "DOC_NOT_FOUND", "Document not found")
        ttl = timedelta(seconds=self.settings.presigned_url_ttl_seconds)
        url = self.store.presigned_get_url(storage_key, expires=ttl)
        return DownloadUrlResponse(
            downloadUrl=url,
            expiresAt=_iso(_now() + ttl),
        )

    # garbage collection (section 11) ---------------------------------------------

    def expire_stale_sessions(self) -> int:
        """Expire upload sessions past their TTL and remove their orphan objects.

        A client may fetch an upload URL and never call complete-upload, leaving an
        `initiated` session and a possibly-orphan MinIO object. This reclaims both.
        """
        now = _iso(_now())
        sessions = self.docs.list_expired_sessions(now)
        reclaimed = 0
        for session in sessions:
            if _remove_if_present(self.store, session.object_key):
                self.docs.set_session_status(session.id, "expired", now)
                reclaimed += 1
        self.connection.commit()
        return reclaimed

    def purge_deleted_objects(self, limit: int = 100) -> int:
        """Physically remove objects of soft-deleted documents, then drop the rows.

        Soft delete (deleted_at) takes the document out of all queries immediately; this
        background pass reclaims the underlying MinIO object by storage_key.
        """
        deleted = self.docs.list_deleted(limit)
        purged = 0
        for document_id, storage_key in deleted:
            if _remove_if_present(self.store, storage_key):
                self.docs.hard_delete_document(document_id)
                purged += 1
        self.connection.commit()
        return purged

    def purge_deleted_knowledge_bases(self, limit: int = 50) -> int:
        """Reclaim objects of soft-deleted knowledge bases, then hard-delete their rows.

        KB delete is a soft delete precisely so this pass can run: it removes every object the
        base held (document bodies + orphan upload-session objects) before dropping the document,
        upload_session and knowledge_base rows. Object removal is best-effort and keyed, so a
        partial failure is retried on the next pass.
        """
        kb_ids = self.kbs.list_soft_deleted(limit)
        purged = 0
        for kb_id in kb_ids:
            object_keys = set(self.docs.list_object_keys_for_kb(kb_id))
            if not all(_remove_if_present(self.store, object_key) for object_key in object_keys):
                continue
            self.docs.delete_rows_for_kb(kb_id)
            self.kbs.delete(kb_id)
            purged += 1
        self.connection.commit()
        return purged

    # helpers ----------------------------------------------------------------------

    def _authorized_kb(self, principal: Principal, knowledge_base_id: str, action: str):
        kb = self.kbs.get(knowledge_base_id)
        if not kb:
            raise ApiError(404, "KB_NOT_FOUND", "Knowledge base not found")
        authorize_kb_access(principal, kb, action)  # type: ignore[arg-type]
        return kb


def _resolve_file_type(file_name: str, mime_type: str | None) -> str:
    ext = posixpath.splitext(file_name)[1].lstrip(".").lower()
    if ext in _EXTENSION_FILE_TYPE:
        return _EXTENSION_FILE_TYPE[ext]
    raise ApiError(
        400,
        "DOC_UNSUPPORTED_TYPE",
        "Unsupported file type",
        {"fileName": file_name, "mimeType": mime_type},
    )


def _safe_file_name(file_name: str) -> str:
    # Strip path separators and control characters; keep a clean basename for the object key.
    base = posixpath.basename(file_name.replace("\\", "/")).strip()
    base = re.sub(r"[\x00-\x1f\x7f]", "", base)
    if not base or base in {".", ".."}:
        raise ApiError(400, "DOC_INVALID_FILE_NAME", "Invalid file name")
    return base


def _object_key(knowledge_base_id: str, document_id: str, safe_file_name: str) -> str:
    return f"knowledge-bases/{knowledge_base_id}/documents/{document_id}/{safe_file_name}"


def _batch_error(exc: ApiError) -> BatchItemError:
    return BatchItemError(code=exc.code, message=exc.message, details=exc.details)


def _best_effort_remove(store: ObjectStore, object_key: str) -> None:
    try:
        store.remove(object_key)
    except Exception:  # noqa: BLE001 - cleanup is best-effort; GC will retry by key
        pass


def _remove_if_present(store: ObjectStore, object_key: str) -> bool:
    try:
        store.remove(object_key)
        return True
    except ApiError as exc:
        return exc.status_code == 404
    except Exception:  # noqa: BLE001 - keep DB rows so GC can retry later
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _expired(expires_at: str) -> bool:
    return _parse(expires_at) <= _now()


def _parse(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
