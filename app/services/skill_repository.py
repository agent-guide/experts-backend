from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from typing import Any

from app.db import DatabaseConnection
from app.domain.skills import Skill


class SkillRepository:
    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection

    def create(self, skill: Skill) -> Skill:
        _execute(
            self.connection,
            """
            insert into skills (
              id, slug, name, description, version, allowed_tools,
              file_paths, tags, storage_uri, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                skill.id,
                skill.slug,
                skill.name,
                skill.description,
                skill.version,
                _json_param(self.connection, skill.allowedTools),
                _json_param(self.connection, skill.filePaths),
                _json_param(self.connection, skill.tags),
                skill.storageUri,
                skill.createdAt,
                skill.updatedAt,
            ),
        )
        return skill

    def update(
        self,
        slug: str,
        *,
        name: str,
        description: str,
        version: str | None,
        allowed_tools: list[str],
        tags: list[str],
        updated_at: str,
    ) -> Skill | None:
        _execute(
            self.connection,
            """
            update skills
            set name = ?,
                description = ?,
                version = ?,
                allowed_tools = ?,
                tags = ?,
                updated_at = ?
            where slug = ?
            """,
            (
                name,
                description,
                version,
                _json_param(self.connection, allowed_tools),
                _json_param(self.connection, tags),
                updated_at,
                slug,
            ),
        )
        return self.get(slug)

    def get(self, slug: str) -> Skill | None:
        row = _fetch_one(
            self.connection,
            """
            select id, slug, name, description, version, allowed_tools, file_paths,
                   tags, storage_uri, created_at, updated_at
            from skills
            where slug = ?
            limit 1
            """,
            (slug,),
        )
        return _map_skill(row)

    def delete(self, slug: str) -> Skill | None:
        skill = self.get(slug)
        if not skill:
            return None
        _execute(self.connection, "delete from skills where slug = ?", (slug,))
        return skill

    def list(
        self,
        *,
        tags: list[str],
        search: str | None,
        limit: int,
        offset: int,
    ) -> list[Skill]:
        rows = _fetch_all(
            self.connection,
            """
            select id, slug, name, description, version, allowed_tools, file_paths,
                   tags, storage_uri, created_at, updated_at
            from skills
            order by created_at desc, slug asc
            """,
        )
        items = [_map_skill(row) for row in rows]
        filtered = [item for item in items if item is not None]
        if tags:
            wanted = set(tags)
            filtered = [item for item in filtered if wanted.intersection(item.tags)]
        if search:
            needle = search.casefold()
            filtered = [
                item
                for item in filtered
                if needle in item.name.casefold()
                or needle in item.slug.casefold()
                or needle in item.description.casefold()
            ]
        return filtered[offset : offset + limit]


def _map_skill(row: dict[str, Any] | None) -> Skill | None:
    if not row:
        return None
    return Skill(
        id=str(row["id"]),
        slug=str(row["slug"]),
        name=str(row["name"]),
        description=str(row["description"]),
        version=str(row["version"]) if row["version"] is not None else None,
        allowedTools=_json_list(row["allowed_tools"]),
        filePaths=_json_list(row["file_paths"]),
        tags=_json_list(row["tags"]),
        storageUri=str(row["storage_uri"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _execute(connection: DatabaseConnection, sql: str, params: Sequence[Any] = ()) -> Any:
    return connection.execute(_prepare_sql(connection, sql), params)


def _fetch_one(
    connection: DatabaseConnection, sql: str, params: Sequence[Any] = ()
) -> dict[str, Any] | None:
    cursor = _execute(connection, sql, params)
    row = cursor.fetchone()
    return _row_to_dict(row)


def _fetch_all(
    connection: DatabaseConnection, sql: str, params: Sequence[Any] = ()
) -> list[dict[str, Any]]:
    cursor = _execute(connection, sql, params)
    return [_row_to_dict(row) or {} for row in cursor.fetchall()]


def _row_to_dict(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return dict(row)


def _prepare_sql(connection: DatabaseConnection, sql: str) -> str:
    if isinstance(connection, sqlite3.Connection):
        return sql
    return sql.replace("?", "%s")


def _json_param(connection: DatabaseConnection, value: list[str]) -> Any:
    if isinstance(connection, sqlite3.Connection):
        return json.dumps(value)
    try:
        from psycopg.types.json import Jsonb
    except ImportError:  # pragma: no cover - PostgreSQL dependency is optional in tests
        return json.dumps(value)
    return Jsonb(value)


def _json_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return []
