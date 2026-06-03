from __future__ import annotations

from typing import Any

from app.db import DatabaseConnection
from app.domain.knowledge import KnowledgeBase
from app.services._sql import execute, fetch_all, fetch_one, json_load, json_param, rowcount


_COLUMNS = (
    "id, owner_user_id, name, description, status, metadata, created_at, updated_at"
)


class KnowledgeBaseRepository:
    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection

    def create(self, kb: KnowledgeBase) -> KnowledgeBase:
        execute(
            self.connection,
            f"""
            insert into knowledge_bases ({_COLUMNS})
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kb.id,
                kb.ownerUserId,
                kb.name,
                kb.description,
                kb.status,
                json_param(self.connection, kb.metadata),
                kb.createdAt,
                kb.updatedAt,
            ),
        )
        return kb

    def get(self, knowledge_base_id: str) -> KnowledgeBase | None:
        row = fetch_one(
            self.connection,
            f"select {_COLUMNS} from knowledge_bases "
            "where id = ? and deleted_at is null limit 1",
            (knowledge_base_id,),
        )
        return _map_kb(row)

    def update(
        self,
        knowledge_base_id: str,
        *,
        name: str,
        description: str | None,
        metadata: dict[str, Any],
        updated_at: str,
    ) -> KnowledgeBase | None:
        execute(
            self.connection,
            """
            update knowledge_bases
            set name = ?, description = ?, metadata = ?, updated_at = ?
            where id = ?
            """,
            (
                name,
                description,
                json_param(self.connection, metadata),
                updated_at,
                knowledge_base_id,
            ),
        )
        return self.get(knowledge_base_id)

    def soft_delete(self, knowledge_base_id: str, now: str) -> bool:
        cursor = execute(
            self.connection,
            """
            update knowledge_bases
            set deleted_at = ?, updated_at = ?
            where id = ? and deleted_at is null
            """,
            (now, now, knowledge_base_id),
        )
        return rowcount(cursor) > 0

    def delete(self, knowledge_base_id: str) -> None:
        """Hard delete. Used only by GC after the objects have been reclaimed -- the API delete
        path is a soft delete (see soft_delete)."""
        execute(
            self.connection,
            "delete from knowledge_bases where id = ?",
            (knowledge_base_id,),
        )

    def list_soft_deleted(self, limit: int) -> list[str]:
        rows = fetch_all(
            self.connection,
            """
            select id from knowledge_bases
            where deleted_at is not null
            order by deleted_at asc
            limit ?
            """,
            (limit,),
        )
        return [str(row["id"]) for row in rows]

    def list_for_platform(self) -> list[KnowledgeBase]:
        rows = fetch_all(
            self.connection,
            f"""
            select {_COLUMNS} from knowledge_bases
            where status = 'active' and deleted_at is null
            order by created_at desc, id asc
            """,
        )
        return [kb for kb in (_map_kb(row) for row in rows) if kb is not None]


def _map_kb(row: dict[str, Any] | None) -> KnowledgeBase | None:
    if not row:
        return None
    return KnowledgeBase(
        id=str(row["id"]),
        ownerUserId=str(row["owner_user_id"]) if row["owner_user_id"] is not None else None,
        name=str(row["name"]),
        description=str(row["description"]) if row["description"] is not None else None,
        status=str(row["status"]),
        metadata=json_load(row["metadata"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )
