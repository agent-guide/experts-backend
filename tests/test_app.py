from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db import migrate_database, open_database_connection
from app.main import app, create_app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "amazon-experts-backend"}


def test_openapi_loads() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/knowledge-bases" in paths
    assert "/api/v1/chat/tasks" in paths
    assert "/api/v1/skills" in paths


def test_sqlite_migration_uses_infra_sql(tmp_path: Path) -> None:
    database_path = tmp_path / "expert.sqlite3"
    settings = Settings(database_url=f"sqlite:///{database_path}")

    migrate_database(settings)

    with open_database_connection(settings) as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        }
        chat_task_columns = {
            row["name"] for row in connection.execute("pragma table_info(chat_tasks)").fetchall()
        }

    assert "tenants" in tables
    assert "knowledge_bases" in tables
    assert "chat_tasks" in tables
    assert "chat_task_events" in tables
    assert "priority" in chat_task_columns
    assert "multi_hop_config" in chat_task_columns


def test_app_startup_migrates_sqlite(tmp_path: Path) -> None:
    database_path = tmp_path / "startup.sqlite3"
    settings = Settings(database_url=f"sqlite:///{database_path}")
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    with open_database_connection(settings) as connection:
        row = connection.execute(
            "select name from sqlite_master where type = 'table' and name = 'tenants'"
        ).fetchone()
    assert row is not None
