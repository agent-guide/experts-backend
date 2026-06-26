from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db import DatabaseConnection
from app.domain.knowledge import Document
from app.services._sql import execute, fetch_all, fetch_one, json_load, json_param, rowcount


@dataclass
class UploadSession:
    id: str
    knowledge_base_id: str
    document_id: str
    actor_user_id: str
    file_name: str
    file_type: str
    content_type: str | None
    file_size_bytes: int
    object_bucket: str
    object_key: str
    status: str
    expires_at: str


_DOC_COLUMNS = (
    "id, knowledge_base_id, file_name, file_type, mime_type, storage_key, object_bucket, "
    "object_version, content_hash, file_size_bytes, parse_status, index_status, metadata, "
    "created_at, updated_at"
)

_SESSION_COLUMNS = (
    "id, knowledge_base_id, document_id, actor_user_id, file_name, file_type, content_type, "
    "file_size_bytes, object_bucket, object_key, status, expires_at"
)


class DocumentRepository:
    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection

    # upload_sessions ------------------------------------------------------------

    def create_session(
        self,
        *,
        session_id: str,
        knowledge_base_id: str,
        document_id: str,
        actor_user_id: str,
        file_name: str,
        file_type: str,
        content_type: str | None,
        file_size_bytes: int,
        object_bucket: str,
        object_key: str,
        expires_at: str,
        now: str,
    ) -> None:
        execute(
            self.connection,
            """
            insert into upload_sessions (
              id, knowledge_base_id, document_id, actor_user_id, upload_mode, file_name,
              file_type, content_type, file_size_bytes, object_bucket, object_key, status,
              expires_at, created_at, updated_at
            )
            values (?, ?, ?, ?, 'single_put', ?, ?, ?, ?, ?, ?, 'initiated', ?, ?, ?)
            """,
            (
                session_id,
                knowledge_base_id,
                document_id,
                actor_user_id,
                file_name,
                file_type,
                content_type,
                file_size_bytes,
                object_bucket,
                object_key,
                expires_at,
                now,
                now,
            ),
        )

    def get_session(self, session_id: str) -> UploadSession | None:
        row = fetch_one(
            self.connection,
            f"select {_SESSION_COLUMNS} from upload_sessions where id = ? limit 1",
            (session_id,),
        )
        return _map_session(row)

    def set_session_status(self, session_id: str, status: str, now: str) -> None:
        completed = now if status == "completed" else None
        execute(
            self.connection,
            """
            update upload_sessions
            set status = ?, completed_at = ?, updated_at = ?
            where id = ?
            """,
            (status, completed, now, session_id),
        )

    def list_expired_sessions(self, before: str) -> list[UploadSession]:
        rows = fetch_all(
            self.connection,
            f"""
            select {_SESSION_COLUMNS} from upload_sessions
            where status = 'initiated' and expires_at < ?
            """,
            (before,),
        )
        return [s for s in (_map_session(row) for row in rows) if s is not None]

    # documents ------------------------------------------------------------------

    def create_document(
        self,
        *,
        document_id: str,
        knowledge_base_id: str,
        file_name: str,
        file_type: str,
        mime_type: str | None,
        storage_key: str,
        object_bucket: str,
        content_hash: str | None,
        file_size_bytes: int,
        created_by: str,
        now: str,
    ) -> Document:
        execute(
            self.connection,
            """
            insert into documents (
              id, knowledge_base_id, file_name, file_type, mime_type, storage_key, object_bucket,
              object_version, content_hash, file_size_bytes, parse_status, index_status,
              created_by, metadata, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'pending', ?, ?, ?, ?)
            """,
            (
                document_id,
                knowledge_base_id,
                file_name,
                file_type,
                mime_type,
                storage_key,
                object_bucket,
                None,  # object_version
                content_hash,
                file_size_bytes,
                created_by,
                json_param(self.connection, {}),
                now,
                now,
            ),
        )
        document = self.get_document(knowledge_base_id, document_id)
        assert document is not None  # just inserted
        return document

    def get_document(self, knowledge_base_id: str, document_id: str) -> Document | None:
        row = fetch_one(
            self.connection,
            f"""
            select {_DOC_COLUMNS} from documents
            where id = ? and knowledge_base_id = ? and deleted_at is null
            limit 1
            """,
            (document_id, knowledge_base_id),
        )
        return _map_document(row)

    def list_documents(self, knowledge_base_id: str) -> list[Document]:
        rows = fetch_all(
            self.connection,
            f"""
            select {_DOC_COLUMNS} from documents
            where knowledge_base_id = ? and deleted_at is null
            order by created_at desc, id asc
            """,
            (knowledge_base_id,),
        )
        return [d for d in (_map_document(row) for row in rows) if d is not None]

    def update_document(
        self,
        knowledge_base_id: str,
        document_id: str,
        *,
        file_name: str,
        metadata: dict[str, Any],
        now: str,
    ) -> Document | None:
        execute(
            self.connection,
            """
            update documents
            set file_name = ?, metadata = ?, updated_at = ?
            where id = ? and knowledge_base_id = ? and deleted_at is null
            """,
            (file_name, json_param(self.connection, metadata), now, document_id, knowledge_base_id),
        )
        return self.get_document(knowledge_base_id, document_id)

    def soft_delete_document(self, knowledge_base_id: str, document_id: str, now: str) -> bool:
        cursor = execute(
            self.connection,
            """
            update documents
            set deleted_at = ?, updated_at = ?
            where id = ? and knowledge_base_id = ? and deleted_at is null
            """,
            (now, now, document_id, knowledge_base_id),
        )
        return rowcount(cursor) > 0

    def list_deleted(self, limit: int) -> list[tuple[str, str]]:
        rows = fetch_all(
            self.connection,
            "select id, storage_key from documents where deleted_at is not null order by deleted_at asc limit ?",
            (limit,),
        )
        return [(str(row["id"]), str(row["storage_key"])) for row in rows]

    def hard_delete_document(self, document_id: str) -> None:
        execute(self.connection, "delete from documents where id = ?", (document_id,))

    # knowledge-base purge (GC) ---------------------------------------------------
    # These ignore deleted_at: when a knowledge base is purged, every object it ever held must be
    # reclaimed -- soft-deleted documents and never-completed upload sessions included.

    def list_object_keys_for_kb(self, knowledge_base_id: str) -> list[str]:
        """Every object key the knowledge base may own: document bodies plus upload-session
        objects (an `initiated` session may have an uploaded-but-never-completed orphan object)."""
        doc_rows = fetch_all(
            self.connection,
            "select storage_key from documents where knowledge_base_id = ?",
            (knowledge_base_id,),
        )
        session_rows = fetch_all(
            self.connection,
            "select object_key from upload_sessions where knowledge_base_id = ?",
            (knowledge_base_id,),
        )
        keys = [str(row["storage_key"]) for row in doc_rows]
        keys += [str(row["object_key"]) for row in session_rows]
        return keys

    def delete_rows_for_kb(self, knowledge_base_id: str) -> None:
        """Drop the child rows of a knowledge base. Done explicitly rather than relying on the
        ON DELETE CASCADE so reclamation is correct even where foreign keys are not enforced
        (e.g. SQLite without `pragma foreign_keys = on`)."""
        execute(
            self.connection,
            "delete from documents where knowledge_base_id = ?",
            (knowledge_base_id,),
        )
        execute(
            self.connection,
            "delete from upload_sessions where knowledge_base_id = ?",
            (knowledge_base_id,),
        )


def _map_document(row: dict[str, Any] | None) -> Document | None:
    if not row:
        return None
    return Document(
        id=str(row["id"]),
        knowledgeBaseId=str(row["knowledge_base_id"]),
        fileName=str(row["file_name"]),
        fileType=str(row["file_type"]),
        mimeType=str(row["mime_type"]) if row["mime_type"] is not None else None,
        fileSizeBytes=int(row["file_size_bytes"]),
        storageKey=str(row["storage_key"]),
        contentHash=str(row["content_hash"]) if row["content_hash"] is not None else None,
        parseStatus=str(row["parse_status"]),
        indexStatus=str(row["index_status"]),
        metadata=json_load(row["metadata"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _map_session(row: dict[str, Any] | None) -> UploadSession | None:
    if not row:
        return None
    return UploadSession(
        id=str(row["id"]),
        knowledge_base_id=str(row["knowledge_base_id"]),
        document_id=str(row["document_id"]),
        actor_user_id=str(row["actor_user_id"]),
        file_name=str(row["file_name"]),
        file_type=str(row["file_type"]),
        content_type=str(row["content_type"]) if row["content_type"] is not None else None,
        file_size_bytes=int(row["file_size_bytes"]),
        object_bucket=str(row["object_bucket"]),
        object_key=str(row["object_key"]),
        status=str(row["status"]),
        expires_at=str(row["expires_at"]),
    )
