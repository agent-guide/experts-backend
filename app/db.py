from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.core.config import Settings


SqliteConnection = sqlite3.Connection
DatabaseConnection = SqliteConnection | Any


def migrate_database(settings: Settings) -> None:
    schema_dir = Path(settings.database_schema_dir)
    files = sorted(schema_dir.glob("*.sql"))
    if not files:
        raise RuntimeError(f"No SQL schema files found under {schema_dir}")

    if _is_sqlite_url(settings.database_url):
        with open_database_connection(settings) as connection:
            _migrate_sqlite(connection, files)
        return

    if _is_postgres_url(settings.database_url):
        _migrate_postgres(settings.database_url, files)
        return

    raise RuntimeError(f"Unsupported database URL: {settings.database_url}")


@contextmanager
def open_database_connection(settings: Settings) -> Iterator[DatabaseConnection]:
    if _is_sqlite_url(settings.database_url):
        connection = _open_sqlite(settings.database_url)
        try:
            yield connection
        finally:
            connection.close()
        return

    if _is_postgres_url(settings.database_url):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - exercised only without optional dependency
            raise RuntimeError("PostgreSQL requires the psycopg dependency.") from exc

        with psycopg.connect(settings.database_url, row_factory=dict_row) as connection:
            yield connection
        return

    raise RuntimeError(f"Unsupported database URL: {settings.database_url}")


def _migrate_sqlite(connection: SqliteConnection, files: list[Path]) -> None:
    connection.execute("pragma foreign_keys = on")
    for file in files:
        sql = _sqlite_compatible_sql(file.read_text(encoding="utf-8"))
        for statement in _split_sql_statements(sql):
            _execute_sqlite_statement(connection, statement)
    connection.commit()


def _migrate_postgres(database_url: str, files: list[Path]) -> None:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - exercised only without optional dependency
        raise RuntimeError("PostgreSQL requires the psycopg dependency.") from exc

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            for file in files:
                cursor.execute(file.read_text(encoding="utf-8"))
        connection.commit()


def _execute_sqlite_statement(connection: SqliteConnection, statement: str) -> None:
    statement = _strip_sql_comments(statement)
    if not statement:
        return
    normalized = " ".join(statement.lower().split())

    add_column = re.match(
        r"alter\s+table\s+(\w+)\s+add\s+column\s+if\s+not\s+exists\s+(\w+)\s+(.+)",
        statement,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if add_column:
        table, column, definition = add_column.groups()
        if _sqlite_column_exists(connection, table, column):
            return
        connection.execute(f"alter table {table} add column {column} {definition}")
        return

    drop_column = re.match(
        r"alter\s+table\s+(\w+)\s+drop\s+column\s+if\s+exists\s+(\w+)",
        statement,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if drop_column:
        table, column = drop_column.groups()
        if _sqlite_column_exists(connection, table, column):
            connection.execute(f"alter table {table} drop column {column}")
        return

    if (
        " alter column " in f" {normalized} "
        or " add constraint " in f" {normalized} "
        or " drop constraint " in f" {normalized} "
    ):
        return

    connection.execute(statement)


def _sqlite_column_exists(connection: SqliteConnection, table: str, column: str) -> bool:
    rows = connection.execute(f"pragma table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def _sqlite_compatible_sql(sql: str) -> str:
    sql = re.sub(r"do\s+\$\$.*?\$\$;", "", sql, flags=re.IGNORECASE | re.DOTALL)
    replacements = [
        (r"'(\{\}|\[\])'::jsonb", r"'\1'"),
        (r"::jsonb", ""),
        (r"\btimestamptz\b", "text"),
        (r"\bjsonb\b", "text"),
        (r"\bbigint\b", "integer"),
        (r"\bboolean\b", "integer"),
        (r"default\s+now\(\)", "default CURRENT_TIMESTAMP"),
        (r"default\s+false\b", "default 0"),
        (r"default\s+true\b", "default 1"),
    ]
    for pattern, replacement in replacements:
        sql = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)
    return sql


def _strip_sql_comments(statement: str) -> str:
    lines = []
    for line in statement.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _split_sql_statements(sql: str) -> list[str]:
    statements = []
    current: list[str] = []
    in_single_quote = False
    index = 0

    while index < len(sql):
        char = sql[index]
        current.append(char)
        if char == "'" and sql[index - 1 : index] != "\\":
            in_single_quote = not in_single_quote
        if char == ";" and not in_single_quote:
            statement = "".join(current).strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            current = []
        index += 1

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def _open_sqlite(database_url: str) -> SqliteConnection:
    path = _sqlite_path(database_url)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    # Foreign keys are off by default per SQLite connection. Enable them so runtime FK behavior
    # (e.g. ON DELETE CASCADE) matches PostgreSQL, where constraints are always enforced.
    connection.execute("pragma foreign_keys = on")
    return connection


def _sqlite_path(database_url: str) -> str:
    if database_url == "sqlite:///:memory:":
        return ":memory:"
    if database_url.startswith("sqlite:///"):
        return database_url.removeprefix("sqlite:///")
    raise RuntimeError(f"Unsupported sqlite URL: {database_url}")


def _is_sqlite_url(database_url: str) -> bool:
    return database_url.startswith("sqlite:///")


def _is_postgres_url(database_url: str) -> bool:
    return database_url.startswith(("postgres://", "postgresql://"))
