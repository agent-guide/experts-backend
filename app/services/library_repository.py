from __future__ import annotations

from typing import Any

from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.library import LibraryFileRecord, LibrarySort, LibraryUploadSessionRecord
from app.services._sql import execute, fetch_all, fetch_one, json_load, json_param, rowcount


_COLUMNS = (
    "id, user_id, tenant_id, original_name, safe_name, mime_type, file_type, extension, "
    "size_bytes, storage_bucket, storage_object_key, content_hash, preview_supported, "
    "metadata, source, lifecycle, expires_at, promoted_at, chat_session_id, created_at, updated_at"
)

_SESSION_COLUMNS = (
    "id, file_id, user_id, tenant_id, original_name, safe_name, mime_type, file_type, extension, "
    "file_size_bytes, storage_bucket, storage_object_key, content_hash, status, expires_at, "
    "completed_at, chat_session_id, created_at, updated_at"
)


def validate_lifecycle_invariant(
    *, lifecycle: str, chat_session_id: str | None, expires_at: str | None
) -> None:
    """Re-validate the §3.4 cross-column lifecycle invariant in application code.

    The DB check covers fresh databases and existing PostgreSQL, but cannot be retrofitted onto an
    existing SQLite table, so every write path re-validates here to guarantee the invariant
    uniformly. A violation is a backend bug, not user input, so it surfaces as a 500.

    A temporary file always has an expiry; its chat_session_id may be null (unbound) until it is
    bound to a session on first turn use (§5/§7).
    """
    del chat_session_id  # no longer part of the invariant; kept for call-site symmetry
    if lifecycle == "temporary":
        if expires_at is None:
            raise ApiError(
                500,
                "LIBRARY_LIFECYCLE_INVARIANT_VIOLATION",
                "A temporary file must have expires_at",
            )
    elif lifecycle == "permanent":
        if expires_at is not None:
            raise ApiError(
                500,
                "LIBRARY_LIFECYCLE_INVARIANT_VIOLATION",
                "A permanent file must not have expires_at",
            )
    else:
        raise ApiError(
            500, "LIBRARY_LIFECYCLE_INVARIANT_VIOLATION", f"Unknown lifecycle: {lifecycle}"
        )

_SORT_SQL: dict[str, str] = {
    "updatedAt_desc": "updated_at desc, id asc",
    "updatedAt_asc": "updated_at asc, id asc",
    "name_asc": "lower(original_name) asc, id asc",
    "name_desc": "lower(original_name) desc, id asc",
    "size_desc": "size_bytes desc, id asc",
    "size_asc": "size_bytes asc, id asc",
}


class LibraryRepository:
    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection

    def create_file(
        self,
        *,
        file_id: str,
        user_id: str,
        tenant_id: str,
        original_name: str,
        safe_name: str,
        mime_type: str | None,
        file_type: str,
        extension: str | None,
        size_bytes: int,
        storage_bucket: str,
        storage_object_key: str,
        content_hash: str | None,
        preview_supported: bool,
        metadata: dict[str, Any],
        now: str,
        source: str = "library",
        lifecycle: str = "permanent",
        expires_at: str | None = None,
        promoted_at: str | None = None,
        chat_session_id: str | None = None,
    ) -> LibraryFileRecord:
        validate_lifecycle_invariant(
            lifecycle=lifecycle, chat_session_id=chat_session_id, expires_at=expires_at
        )
        execute(
            self.connection,
            """
            insert into library_files (
              id, user_id, tenant_id, original_name, safe_name, mime_type, file_type,
              extension, size_bytes, storage_bucket, storage_object_key, content_hash,
              preview_supported, metadata, source, lifecycle, expires_at, promoted_at,
              chat_session_id, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                user_id,
                tenant_id,
                original_name,
                safe_name,
                mime_type,
                file_type,
                extension,
                size_bytes,
                storage_bucket,
                storage_object_key,
                content_hash,
                preview_supported,
                json_param(self.connection, metadata),
                source,
                lifecycle,
                expires_at,
                promoted_at,
                chat_session_id,
                now,
                now,
            ),
        )
        file = self.get_file(user_id, tenant_id, file_id)
        assert file is not None
        return file

    def create_upload_session(
        self,
        *,
        session_id: str,
        file_id: str,
        user_id: str,
        tenant_id: str,
        original_name: str,
        safe_name: str,
        mime_type: str | None,
        file_type: str,
        extension: str | None,
        file_size_bytes: int,
        storage_bucket: str,
        storage_object_key: str,
        content_hash: str | None,
        expires_at: str,
        now: str,
        chat_session_id: str | None = None,
    ) -> None:
        execute(
            self.connection,
            """
            insert into library_upload_sessions (
              id, file_id, user_id, tenant_id, original_name, safe_name, mime_type, file_type,
              extension, file_size_bytes, storage_bucket, storage_object_key, content_hash,
              status, expires_at, chat_session_id, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'initiated', ?, ?, ?, ?)
            """,
            (
                session_id,
                file_id,
                user_id,
                tenant_id,
                original_name,
                safe_name,
                mime_type,
                file_type,
                extension,
                file_size_bytes,
                storage_bucket,
                storage_object_key,
                content_hash,
                expires_at,
                chat_session_id,
                now,
                now,
            ),
        )

    def get_upload_session(self, session_id: str) -> LibraryUploadSessionRecord | None:
        row = fetch_one(
            self.connection,
            f"select {_SESSION_COLUMNS} from library_upload_sessions where id = ? limit 1",
            (session_id,),
        )
        return _map_session(row)

    def set_upload_session_status(
        self,
        session_id: str,
        status: str,
        now: str,
        *,
        completed: bool = False,
    ) -> None:
        completed_at = now if completed else None
        execute(
            self.connection,
            """
            update library_upload_sessions
            set status = ?, completed_at = coalesce(?, completed_at), updated_at = ?
            where id = ?
            """,
            (status, completed_at, now, session_id),
        )

    def list_expired_upload_sessions(self, before: str) -> list[LibraryUploadSessionRecord]:
        rows = fetch_all(
            self.connection,
            f"""
            select {_SESSION_COLUMNS} from library_upload_sessions
            where status = 'initiated' and expires_at < ?
            """,
            (before,),
        )
        return [s for s in (_map_session(row) for row in rows) if s is not None]

    def get_file(
        self, user_id: str, tenant_id: str, file_id: str
    ) -> LibraryFileRecord | None:
        row = fetch_one(
            self.connection,
            f"""
            select {_COLUMNS} from library_files
            where id = ? and user_id = ? and tenant_id = ? and deleted_at is null
            limit 1
            """,
            (file_id, user_id, tenant_id),
        )
        return _map_file(row)

    def list_files(
        self,
        *,
        user_id: str,
        tenant_id: str,
        keyword: str | None,
        file_type: str | None,
        sort: LibrarySort,
        limit: int,
        offset: int,
        lifecycle: str = "permanent",
        chat_session_id: str | None = None,
        now: str | None = None,
    ) -> tuple[list[LibraryFileRecord], int]:
        # user_id + tenant_id are always in the where clause, so this is the real ownership
        # boundary regardless of the lifecycle filter (§11).
        where = ["user_id = ?", "tenant_id = ?", "deleted_at is null"]
        params: list[Any] = [user_id, tenant_id]
        if lifecycle == "temporary":
            # Temporary listing (§11): owner-scoped and never expired. Without a session it returns
            # all of the caller's temporary files (bound and unbound); with one, only that session's
            # bound files. Both stay owner-scoped, so there is no cross-user exposure.
            where.append("lifecycle = 'temporary'")
            where.append("expires_at > ?")
            params.append(now)
            if chat_session_id is not None:
                where.append("chat_session_id = ?")
                params.append(chat_session_id)
        else:
            # §11 safeguard: the default listing is permanent-only, unconditionally. A caller that
            # does not explicitly ask for temporary files never sees them.
            where.append("lifecycle = 'permanent'")
        if file_type is not None:
            where.append("file_type = ?")
            params.append(file_type)
        if keyword:
            where.append("lower(original_name) like ?")
            params.append(f"%{keyword.lower()}%")
        where_sql = " and ".join(where)
        total_row = fetch_one(
            self.connection,
            f"select count(*) as count from library_files where {where_sql}",
            params,
        )
        rows = fetch_all(
            self.connection,
            f"""
            select {_COLUMNS} from library_files
            where {where_sql}
            order by {_SORT_SQL[sort]}
            limit ? offset ?
            """,
            [*params, limit, offset],
        )
        return [f for f in (_map_file(row) for row in rows) if f is not None], int(
            total_row["count"] if total_row else 0
        )

    def promote_file(
        self, user_id: str, tenant_id: str, file_id: str, now: str
    ) -> LibraryFileRecord | None:
        """Flip a live temporary file to permanent with no byte copy (§10).

        The expiry guard lives in the SQL where clause so a promotion racing the GC pass cannot
        resurrect an already-expired file. Returns None if nothing matched (expired, already
        permanent, or deleted).
        """
        cursor = execute(
            self.connection,
            """
            update library_files
            set lifecycle = 'permanent', expires_at = null, promoted_at = ?, updated_at = ?
            where id = ? and user_id = ? and tenant_id = ?
              and deleted_at is null
              and lifecycle = 'temporary'
              and expires_at > ?
            """,
            (now, now, file_id, user_id, tenant_id, now),
        )
        if rowcount(cursor) == 0:
            return None
        return self.get_file(user_id, tenant_id, file_id)

    def bind_temporary_file_session(
        self, user_id: str, tenant_id: str, file_id: str, session_id: str, now: str
    ) -> LibraryFileRecord | None:
        """Bind an unbound temporary file to a session, exactly once (§7 auto-bind).

        The `chat_session_id is null` guard makes the bind idempotent and race-safe: a second
        attempt (or a concurrent turn in another session) matches no row. Returns None when nothing
        was bound; the caller re-reads to see who won.
        """
        cursor = execute(
            self.connection,
            """
            update library_files
            set chat_session_id = ?, updated_at = ?
            where id = ? and user_id = ? and tenant_id = ?
              and deleted_at is null
              and lifecycle = 'temporary'
              and chat_session_id is null
              and expires_at > ?
            """,
            (session_id, now, file_id, user_id, tenant_id, now),
        )
        if rowcount(cursor) == 0:
            return None
        return self.get_file(user_id, tenant_id, file_id)

    def list_expired_temporary_files(self, now: str, limit: int = 100) -> list[tuple[str, str]]:
        """Temporary files past their deadline (§12.2). Returns (file_id, storage_object_key)."""
        rows = fetch_all(
            self.connection,
            """
            select id, storage_object_key from library_files
            where lifecycle = 'temporary' and deleted_at is null and expires_at < ?
            order by expires_at asc
            limit ?
            """,
            (now, limit),
        )
        return [(str(row["id"]), str(row["storage_object_key"])) for row in rows]

    def soft_delete_file(self, user_id: str, tenant_id: str, file_id: str, now: str) -> bool:
        cursor = execute(
            self.connection,
            """
            update library_files
            set deleted_at = ?, updated_at = ?
            where id = ? and user_id = ? and tenant_id = ? and deleted_at is null
            """,
            (now, now, file_id, user_id, tenant_id),
        )
        return rowcount(cursor) > 0

    def list_deleted(self, limit: int) -> list[tuple[str, str]]:
        rows = fetch_all(
            self.connection,
            """
            select id, storage_object_key from library_files
            where deleted_at is not null
            order by deleted_at asc
            limit ?
            """,
            (limit,),
        )
        return [(str(row["id"]), str(row["storage_object_key"])) for row in rows]

    def hard_delete_file(self, file_id: str) -> None:
        execute(self.connection, "delete from library_files where id = ?", (file_id,))


def _map_file(row: dict[str, Any] | None) -> LibraryFileRecord | None:
    if not row:
        return None
    return LibraryFileRecord(
        id=str(row["id"]),
        userId=str(row["user_id"]),
        tenantId=str(row["tenant_id"]),
        originalName=str(row["original_name"]),
        safeName=str(row["safe_name"]),
        mimeType=str(row["mime_type"]) if row.get("mime_type") is not None else None,
        fileType=str(row["file_type"]),
        extension=str(row["extension"]) if row.get("extension") is not None else None,
        sizeBytes=int(row["size_bytes"]),
        storageBucket=str(row["storage_bucket"]),
        storageObjectKey=str(row["storage_object_key"]),
        contentHash=str(row["content_hash"]) if row.get("content_hash") is not None else None,
        previewSupported=bool(row["preview_supported"]),
        metadata=json_load(row["metadata"]),
        source=str(row["source"]) if row.get("source") is not None else "library",
        lifecycle=str(row["lifecycle"]) if row.get("lifecycle") is not None else "permanent",
        expiresAt=str(row["expires_at"]) if row.get("expires_at") is not None else None,
        promotedAt=str(row["promoted_at"]) if row.get("promoted_at") is not None else None,
        chatSessionId=str(row["chat_session_id"]) if row.get("chat_session_id") is not None else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _map_session(row: dict[str, Any] | None) -> LibraryUploadSessionRecord | None:
    if not row:
        return None
    return LibraryUploadSessionRecord(
        id=str(row["id"]),
        fileId=str(row["file_id"]),
        userId=str(row["user_id"]),
        tenantId=str(row["tenant_id"]),
        originalName=str(row["original_name"]),
        safeName=str(row["safe_name"]),
        mimeType=str(row["mime_type"]) if row.get("mime_type") is not None else None,
        fileType=str(row["file_type"]),
        extension=str(row["extension"]) if row.get("extension") is not None else None,
        fileSizeBytes=int(row["file_size_bytes"]),
        storageBucket=str(row["storage_bucket"]),
        storageObjectKey=str(row["storage_object_key"]),
        contentHash=str(row["content_hash"]) if row.get("content_hash") is not None else None,
        status=str(row["status"]),
        expiresAt=str(row["expires_at"]),
        completedAt=str(row["completed_at"]) if row.get("completed_at") is not None else None,
        chatSessionId=str(row["chat_session_id"]) if row.get("chat_session_id") is not None else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )
