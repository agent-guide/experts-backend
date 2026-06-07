from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.experts import (
    CreateExpertCategoryRequest,
    ExpertCategory,
    UpdateExpertCategoryRequest,
)
from app.services._sql import execute, fetch_all, fetch_one, is_unique_violation, rowcount


class ExpertCategoryService:
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

    def get(self, category_id: str) -> ExpertCategory:
        row = self._category_row(category_id)
        if not row:
            raise ApiError(404, "EXPERT_CATEGORY_NOT_FOUND", "Expert category not found")
        return _map_category(row)

    def create(self, request: CreateExpertCategoryRequest) -> ExpertCategory:
        category_id = f"expert_cat_{uuid4().hex}"
        try:
            execute(
                self.connection,
                """
                insert into expert_categories (id, name, description)
                values (?, ?, ?)
                """,
                (category_id, request.name, request.description),
            )
            self.connection.commit()
        except Exception as exc:
            if is_unique_violation(exc):
                raise ApiError(
                    409, "EXPERT_CATEGORY_NAME_EXISTS", "Expert category name already exists"
                ) from exc
            raise
        return self.get(category_id)

    def update(
        self, category_id: str, request: UpdateExpertCategoryRequest
    ) -> ExpertCategory:
        current = self.get(category_id)
        next_name = request.name if request.name is not None else current.name
        next_description = (
            request.description if request.description is not None else current.description
        )
        try:
            execute(
                self.connection,
                """
                update expert_categories
                set name = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                where id = ?
                """,
                (next_name, next_description, category_id),
            )
            self.connection.commit()
        except Exception as exc:
            if is_unique_violation(exc):
                raise ApiError(
                    409, "EXPERT_CATEGORY_NAME_EXISTS", "Expert category name already exists"
                ) from exc
            raise
        return self.get(category_id)

    def delete(self, category_id: str) -> None:
        self.get(category_id)
        in_use = fetch_one(
            self.connection,
            "select id from experts where category_id = ? limit 1",
            (category_id,),
        )
        if in_use:
            raise ApiError(
                409,
                "EXPERT_CATEGORY_IN_USE",
                "Expert category is used by one or more experts",
            )
        cursor = execute(
            self.connection,
            "delete from expert_categories where id = ?",
            (category_id,),
        )
        if rowcount(cursor) <= 0:
            raise ApiError(404, "EXPERT_CATEGORY_NOT_FOUND", "Expert category not found")
        self.connection.commit()

    def _category_row(self, category_id: str) -> dict[str, Any] | None:
        return fetch_one(
            self.connection,
            """
            select id, name, description, created_at, updated_at
            from expert_categories
            where id = ?
            limit 1
            """,
            (category_id,),
        )


def _map_category(row: dict[str, Any]) -> ExpertCategory:
    return ExpertCategory(
        id=str(row["id"]),
        name=str(row["name"]),
        description=str(row["description"]) if row["description"] is not None else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )
