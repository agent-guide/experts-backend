from __future__ import annotations

from typing import Any

from app.db import DatabaseConnection
from app.domain.experts import ExpertCategory, ExpertMarketCategory
from app.services._sql import execute, fetch_all, fetch_one, rowcount


class ExpertCategoryRepository:
    """Raw SQL data access for expert categories."""

    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection

    def list(self) -> list[ExpertCategory]:
        rows = fetch_all(
            self.connection,
            """
            select id, name, description, created_at, updated_at
            from expert_categories
            order by created_at desc, id asc
            """,
        )
        return [_map_category(row) for row in rows]

    def list_market(self) -> list[ExpertMarketCategory]:
        rows = fetch_all(
            self.connection,
            """
            select distinct c.id, c.name, c.description
            from expert_categories c
            inner join experts e on e.category_id = c.id
            where e.status = 'published'
            order by c.name asc, c.id asc
            """,
        )
        return [_map_market_category(row) for row in rows]

    def get(self, category_id: str) -> ExpertCategory | None:
        row = fetch_one(
            self.connection,
            """
            select id, name, description, created_at, updated_at
            from expert_categories
            where id = ?
            limit 1
            """,
            (category_id,),
        )
        return _map_category(row) if row else None

    def insert(self, category_id: str, name: str, description: str | None) -> None:
        execute(
            self.connection,
            "insert into expert_categories (id, name, description) values (?, ?, ?)",
            (category_id, name, description),
        )

    def update(self, category_id: str, name: str, description: str | None) -> None:
        execute(
            self.connection,
            """
            update expert_categories
            set name = ?, description = ?, updated_at = CURRENT_TIMESTAMP
            where id = ?
            """,
            (name, description, category_id),
        )

    def delete(self, category_id: str) -> int:
        cursor = execute(
            self.connection,
            "delete from expert_categories where id = ?",
            (category_id,),
        )
        return rowcount(cursor)

    def is_used_by_expert(self, category_id: str) -> bool:
        row = fetch_one(
            self.connection,
            "select id from experts where category_id = ? limit 1",
            (category_id,),
        )
        return row is not None


def _map_category(row: dict[str, Any]) -> ExpertCategory:
    return ExpertCategory(
        id=str(row["id"]),
        name=str(row["name"]),
        description=str(row["description"]) if row["description"] is not None else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _map_market_category(row: dict[str, Any]) -> ExpertMarketCategory:
    return ExpertMarketCategory(
        id=str(row["id"]),
        name=str(row["name"]),
        description=str(row["description"]) if row["description"] is not None else None,
    )
