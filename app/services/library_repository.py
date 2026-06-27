from __future__ import annotations

from typing import Any

from app.db import DatabaseConnection
from app.domain.library import LibraryFileRecord, LibrarySort, LibraryUploadSessionRecord
from app.services._sql import execute, fetch_all, fetch_one, json_load, json_param, rowcount


_COLUMNS = (
    "id, user_id, tenant_id, original_name, safe_name, mime_type, file_type, extension, "
    "size_bytes, storage_bucket, storage_object_key, content_hash, preview_supported, "
    "metadata, created_at, updated_at"
)

_SESSION_COLUMNS = (
    "id, file_id, user_id, tenant_id, original_name, safe_name, mime_type, file_type, extension, "
    "file_size_bytes, storage_bucket, storage_object_key, content_hash, status, expires_at, "
    "completed_at, created_at, updated_at"
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
    ) -> LibraryFileRecord:
        execute(
            self.connection,
            """
            insert into library_files (
              id, user_id, tenant_id, original_name, safe_name, mime_type, file_type,
              extension, size_bytes, storage_bucket, storage_object_key, content_hash,
              preview_supported, metadata, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    ) -> None:
        execute(
            self.connection,
            """
            insert into library_upload_sessions (
              id, file_id, user_id, tenant_id, original_name, safe_name, mime_type, file_type,
              extension, file_size_bytes, storage_bucket, storage_object_key, content_hash,
              status, expires_at, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'initiated', ?, ?, ?)
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
    ) -> tuple[list[LibraryFileRecord], int]:
        where = ["user_id = ?", "tenant_id = ?", "deleted_at is null"]
        params: list[Any] = [user_id, tenant_id]
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
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )
