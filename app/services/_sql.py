from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from typing import Any

from app.db import DatabaseConnection


def prepare_sql(connection: DatabaseConnection, sql: str) -> str:
    if isinstance(connection, sqlite3.Connection):
        return sql
    return sql.replace("?", "%s")


def execute(connection: DatabaseConnection, sql: str, params: Sequence[Any] = ()) -> Any:
    return connection.execute(prepare_sql(connection, sql), params)


def fetch_one(
    connection: DatabaseConnection, sql: str, params: Sequence[Any] = ()
) -> dict[str, Any] | None:
    cursor = execute(connection, sql, params)
    return _row_to_dict(cursor.fetchone())


def fetch_all(
    connection: DatabaseConnection, sql: str, params: Sequence[Any] = ()
) -> list[dict[str, Any]]:
    cursor = execute(connection, sql, params)
    return [_row_to_dict(row) or {} for row in cursor.fetchall()]


def rowcount(cursor: Any) -> int:
    count = getattr(cursor, "rowcount", 0)
    return count if isinstance(count, int) and count >= 0 else 0


def is_unique_violation(exc: BaseException) -> bool:
    """True if `exc` is a UNIQUE/primary-key violation, across SQLite and PostgreSQL.

    complete-upload relies on the documents primary key (and storage_key unique index) as the
    concurrency guard: two requests that both pass the session-status check collide on insert, and
    the loser is mapped to 409 rather than surfacing a 500.
    """
    if isinstance(exc, sqlite3.IntegrityError):
        message = str(exc).lower()
        return "unique constraint failed" in message or "primary key" in message
    try:
        from psycopg import errors
    except ImportError:  # pragma: no cover - PostgreSQL dependency is optional in tests
        return False
    return isinstance(exc, errors.UniqueViolation)


def _row_to_dict(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return dict(row)


def json_param(connection: DatabaseConnection, value: Any) -> Any:
    """Adapt a JSON value for the active backend.

    SQLite stores JSON as text; psycopg binds it as jsonb via the Jsonb wrapper.
    """
    if isinstance(connection, sqlite3.Connection):
        return json.dumps(value)
    try:
        from psycopg.types.json import Jsonb
    except ImportError:  # pragma: no cover - PostgreSQL dependency is optional in tests
        return json.dumps(value)
    return Jsonb(value)


def json_load(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}
