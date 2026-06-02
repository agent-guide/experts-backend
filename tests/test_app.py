from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_opaque_token, hash_password
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


def test_auth_register_login_refresh_logout_persists_to_sqlite(tmp_path: Path) -> None:
    database_path = tmp_path / "auth.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_tenant(settings)

        register_response = client.post(
            "/api/v1/auth/register",
            json={"email": "User@Example.com", "password": "secret123", "name": "Test User"},
        )
        assert register_response.status_code == 201
        registered = register_response.json()
        assert registered["accessToken"]
        assert registered["refreshToken"]

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "secret123"},
        )
        assert login_response.status_code == 200

        refresh_response = client.post(
            "/api/v1/auth/refresh",
            json={"refreshToken": registered["refreshToken"]},
        )
        assert refresh_response.status_code == 200
        refreshed = refresh_response.json()
        assert refreshed["refreshToken"] != registered["refreshToken"]

        reused_refresh_response = client.post(
            "/api/v1/auth/refresh",
            json={"refreshToken": registered["refreshToken"]},
        )
        assert reused_refresh_response.status_code == 401

        logout_response = client.post(
            "/api/v1/auth/logout",
            json={"refreshToken": refreshed["refreshToken"]},
        )
        assert logout_response.status_code == 204

        logged_out_refresh_response = client.post(
            "/api/v1/auth/refresh",
            json={"refreshToken": refreshed["refreshToken"]},
        )
        assert logged_out_refresh_response.status_code == 401

    with open_database_connection(settings) as connection:
        user = connection.execute(
            "select id, tenant_id, email from users where email = 'user@example.com'"
        ).fetchone()
        role = connection.execute(
            "select role from user_roles where tenant_id = ? and user_id = ?",
            ("tenant_default", user["id"]),
        ).fetchone()

    assert user["tenant_id"] == "tenant_default"
    assert role["role"] == "User"


def test_admin_activation_updates_password_and_allows_login(tmp_path: Path) -> None:
    database_path = tmp_path / "activation.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    activation_token = "activation-token"

    with TestClient(test_app) as client:
        _seed_tenant(settings)
        with open_database_connection(settings) as connection:
            connection.execute(
                """
                insert into users (id, tenant_id, email, password_hash, name, status)
                values (?, ?, ?, ?, ?, 'active')
                """,
                (
                    "admin_user",
                    "tenant_default",
                    "admin@example.com",
                    hash_password("placeholder"),
                    "Admin",
                ),
            )
            connection.execute(
                """
                insert into user_roles (id, tenant_id, user_id, role, assigned_by)
                values (?, ?, ?, ?, ?)
                """,
                ("admin_role", "tenant_default", "admin_user", "Admin", "admin_user"),
            )
            connection.execute(
                """
                insert into admin_activation_tokens
                  (id, tenant_id, user_id, token_hash, expires_at)
                values (?, ?, ?, ?, ?)
                """,
                (
                    "activation_1",
                    "tenant_default",
                    "admin_user",
                    hash_opaque_token(activation_token),
                    "2999-01-01T00:00:00+00:00",
                ),
            )
            connection.commit()

        activation_response = client.post(
            "/api/v1/auth/admin/activate",
            json={"token": activation_token, "newPassword": "new-secret", "name": "Root Admin"},
        )
        assert activation_response.status_code == 200
        assert activation_response.json() == {
            "message": "Admin account activated",
            "userId": "admin_user",
            "tenantId": "tenant_default",
            "email": "admin@example.com",
        }

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "new-secret"},
        )
        assert login_response.status_code == 200

    with open_database_connection(settings) as connection:
        token = connection.execute(
            "select used_at from admin_activation_tokens where id = 'activation_1'"
        ).fetchone()
        user = connection.execute("select name from users where id = 'admin_user'").fetchone()

    assert token["used_at"] is not None
    assert user["name"] == "Root Admin"


def _seed_tenant(settings: Settings) -> None:
    with open_database_connection(settings) as connection:
        connection.execute(
            """
            insert into tenants (id, name, slug, status)
            values ('tenant_default', 'Default Tenant', 'default', 'active')
            on conflict (id) do nothing
            """
        )
        connection.commit()
