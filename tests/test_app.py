from pathlib import Path
from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_ngent_client, get_skill_storage
from app.clients.ngent import NgentClient
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
    assert "/api/v1/users/register" in paths
    assert "/api/v1/users" in paths
    assert "/api/v1/users/{user_id}" in paths
    assert "/api/v1/users/{user_id}/status" in paths
    assert "/api/v1/users/{user_id}/tenants" in paths
    assert "/api/v1/users/platform/activate" in paths
    assert "/api/v1/users/platform" in paths
    assert "/api/v1/tenants" in paths
    assert "/api/v1/tenants/{tenant_id}" in paths
    assert "/api/v1/tenants/{tenant_id}/status" in paths
    assert "/api/v1/tenants/{tenant_id}/members" in paths
    assert "/api/v1/tenants/{tenant_id}/members/{user_id}" in paths
    assert "/api/v1/expert-categories" in paths
    assert "/api/v1/expert-categories/{category_id}" in paths
    assert "/api/v1/experts" in paths
    assert "/api/v1/experts/stats/summary" in paths
    assert "/api/v1/experts/{expert_id}" in paths
    assert "/api/v1/experts/{expert_id}/status" in paths
    assert "/api/v1/expert-market/categories" in paths
    assert "/api/v1/expert-market/experts" in paths
    assert "/api/v1/expert-market/experts/{expert_id}" in paths
    assert "/api/v1/rbac/tenant/users" in paths
    assert "/api/v1/rbac/tenant/users/{user_id}/roles" in paths
    assert "/api/v1/rbac/tenant/users/{user_id}" in paths
    assert "/api/v1/rbac/platform/users/{user_id}/roles" in paths
    assert "/api/v1/rbac/platform/users/{user_id}/roles/{role}" in paths
    assert "/api/v1/admin/users" not in paths
    assert "/api/v1/knowledge-bases" in paths
    assert "/api/v1/knowledge-bases/official" not in paths
    assert "/api/v1/chat/sessions/{session_id}/turns" in paths
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
        chat_turn_columns = {
            row["name"] for row in connection.execute("pragma table_info(chat_turns)").fetchall()
        }

    assert "tenants" in tables
    assert "knowledge_bases" in tables
    assert "chat_sessions" in tables
    assert "chat_turns" in tables
    # Old proxy-era tables were removed once the local store became the system of record.
    assert "chat_tasks" not in tables
    assert "chat_task_events" not in tables
    assert "chat_messages" not in tables
    assert "request_text" in chat_turn_columns
    assert "response_text" in chat_turn_columns
    assert "expert_categories" in tables
    assert "experts" in tables
    assert "expert_skills" in tables
    assert "expert_knowledge_bases" in tables


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
        register_response = client.post(
            "/api/v1/users/register",
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
            "select id, email from users where email = 'user@example.com'"
        ).fetchone()
        membership = connection.execute(
            "select tenant_id, role from tenant_members where user_id = ?",
            (user["id"],),
        ).fetchone()
        tenant = connection.execute(
            "select type, owner_user_id from tenants where id = ?",
            (membership["tenant_id"],),
        ).fetchone()

    assert user["email"] == "user@example.com"
    assert membership["role"] == "admin"
    assert tenant["type"] == "personal"
    assert tenant["owner_user_id"] == user["id"]


def test_platform_user_activation_updates_password_and_allows_login(tmp_path: Path) -> None:
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
                insert into users (id, email, password_hash, name, status)
                values (?, ?, ?, ?, 'active')
                """,
                (
                    "admin_user",
                    "admin@example.com",
                    hash_password("placeholder"),
                    "Admin",
                ),
            )
            connection.execute(
                """
                insert into tenant_members (id, tenant_id, user_id, role)
                values (?, ?, ?, ?)
                """,
                ("admin_member", "tenant_default", "admin_user", "admin"),
            )
            connection.execute(
                """
                insert into platform_activation_tokens
                  (id, user_id, token_hash, expires_at)
                values (?, ?, ?, ?)
                """,
                (
                    "activation_1",
                    "admin_user",
                    hash_opaque_token(activation_token),
                    "2999-01-01T00:00:00+00:00",
                ),
            )
            connection.commit()

        activation_response = client.post(
            "/api/v1/users/platform/activate",
            json={
                "token": activation_token,
                "newPassword": "new-secret",
                "name": "Platform User",
            },
        )
        assert activation_response.status_code == 200
        assert activation_response.json() == {
            "message": "Platform user activated",
            "userId": "admin_user",
            "email": "admin@example.com",
        }

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "new-secret"},
        )
        assert login_response.status_code == 200

    with open_database_connection(settings) as connection:
        token = connection.execute(
            "select used_at from platform_activation_tokens where id = 'activation_1'"
        ).fetchone()
        user = connection.execute("select name from users where id = 'admin_user'").fetchone()

    assert token["used_at"] is not None
    assert user["name"] == "Platform User"


def test_rbac_admin_lists_users_and_grants_roles(tmp_path: Path) -> None:
    database_path = tmp_path / "rbac.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_tenant(settings)
        _seed_tenant_user(
            settings,
            "admin_user",
            "admin@example.com",
            "Admin User",
            "admin-secret",
            "admin",
        )
        _seed_tenant_user(
            settings,
            "target_user",
            "target@example.com",
            "Target User",
            "target-secret",
            "member",
        )

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "admin-secret"},
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["accessToken"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "x-tenant-id": "tenant_default",
        }

        list_response = client.get("/api/v1/rbac/tenant/users", headers=headers)
        assert list_response.status_code == 200
        items = {item["id"]: item for item in list_response.json()["items"]}
        assert items["admin_user"]["tenantRoles"] == ["admin"]
        assert "tenant:user_manage" in items["admin_user"]["tenantPermissions"]
        assert "system:ops" not in items["admin_user"]["platformPermissions"]
        assert items["target_user"]["tenantRoles"] == ["member"]
        # Tenant roles only consume (chat); capability authoring is platform-side.
        assert "chat:ask" in items["target_user"]["tenantPermissions"]
        assert "kb:delete" not in items["target_user"]["tenantPermissions"]
        assert "tenant:user_manage" not in items["target_user"]["tenantPermissions"]

        grant_response = client.post(
            "/api/v1/rbac/tenant/users/target_user/roles",
            headers=headers,
            json={"role": "admin"},
        )
        assert grant_response.status_code == 204

        updated_response = client.get("/api/v1/rbac/tenant/users", headers=headers)
        assert updated_response.status_code == 200
        updated_items = {item["id"]: item for item in updated_response.json()["items"]}
        assert updated_items["target_user"]["tenantRoles"] == ["admin"]
        assert "tenant:user_manage" in updated_items["target_user"]["tenantPermissions"]

    with open_database_connection(settings) as connection:
        roles = [
            row["role"]
            for row in connection.execute(
                """
                select role from tenant_members
                where tenant_id = ? and user_id = ?
                order by created_at asc
                """,
                ("tenant_default", "target_user"),
            ).fetchall()
        ]

    assert roles == ["admin"]


def test_rbac_revoke_tenant_member_and_last_admin_guard(tmp_path: Path) -> None:
    database_path = tmp_path / "rbac_revoke.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_tenant(settings)
        _seed_tenant_user(
            settings, "admin_user", "admin@example.com", "Admin User", "admin-secret", "admin"
        )
        _seed_tenant_user(
            settings, "target_user", "target@example.com", "Target User", "target-secret", "member"
        )

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "admin-secret"},
        )
        access_token = login_response.json()["accessToken"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "x-tenant-id": "tenant_default",
        }

        # The sole admin cannot demote themselves to member.
        self_demote = client.post(
            "/api/v1/rbac/tenant/users/admin_user/roles",
            headers=headers,
            json={"role": "member"},
        )
        assert self_demote.status_code == 409

        # The sole admin cannot remove their own membership.
        self_remove = client.delete("/api/v1/rbac/tenant/users/admin_user", headers=headers)
        assert self_remove.status_code == 409

        # A regular member can be removed.
        remove_member = client.delete("/api/v1/rbac/tenant/users/target_user", headers=headers)
        assert remove_member.status_code == 204

        # Removing a non-member returns 404.
        remove_again = client.delete("/api/v1/rbac/tenant/users/target_user", headers=headers)
        assert remove_again.status_code == 404

    with open_database_connection(settings) as connection:
        members = connection.execute(
            "select user_id from tenant_members where tenant_id = 'tenant_default'"
        ).fetchall()

    assert [row["user_id"] for row in members] == ["admin_user"]


def test_rbac_tenant_role_changes_invalidate_existing_access_token(tmp_path: Path) -> None:
    database_path = tmp_path / "rbac_stale_tenant_token.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_tenant(settings)
        _seed_tenant_user(
            settings, "admin_user", "admin@example.com", "Admin User", "admin-secret", "admin"
        )
        _seed_tenant_user(
            settings, "second_admin", "second@example.com", "Second Admin", "second-secret", "admin"
        )

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "admin-secret"},
        )
        stale_headers = {
            "Authorization": f"Bearer {admin_login.json()['accessToken']}",
            "x-tenant-id": "tenant_default",
        }

        second_login = client.post(
            "/api/v1/auth/login",
            json={"email": "second@example.com", "password": "second-secret"},
        )
        second_headers = {
            "Authorization": f"Bearer {second_login.json()['accessToken']}",
            "x-tenant-id": "tenant_default",
        }

        remove_admin = client.delete(
            "/api/v1/rbac/tenant/users/admin_user", headers=second_headers
        )
        assert remove_admin.status_code == 204

        stale_request = client.get("/api/v1/rbac/tenant/users", headers=stale_headers)
        assert stale_request.status_code == 403


def test_rbac_platform_admin_grants_and_revokes_platform_role(tmp_path: Path) -> None:
    database_path = tmp_path / "rbac_platform_revoke.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_platform_user(
            settings, "platform_admin", "padmin@example.com", "Platform Admin", "admin-secret", "admin"
        )
        _seed_user(settings, "target_user", "target@example.com", "Target User", "target-secret")

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "padmin@example.com", "password": "admin-secret"},
        )
        access_token = login_response.json()["accessToken"]
        headers = {"Authorization": f"Bearer {access_token}"}

        grant = client.post(
            "/api/v1/rbac/platform/users/target_user/roles",
            headers=headers,
            json={"role": "expert"},
        )
        assert grant.status_code == 204

        revoke = client.delete(
            "/api/v1/rbac/platform/users/target_user/roles/expert", headers=headers
        )
        assert revoke.status_code == 204

        # Revoking an already-absent role is idempotent.
        revoke_again = client.delete(
            "/api/v1/rbac/platform/users/target_user/roles/expert", headers=headers
        )
        assert revoke_again.status_code == 204

        missing_user = client.delete(
            "/api/v1/rbac/platform/users/missing_user/roles/expert", headers=headers
        )
        assert missing_user.status_code == 404

    with open_database_connection(settings) as connection:
        roles = connection.execute(
            "select role from platform_user_roles where user_id = 'target_user'"
        ).fetchall()

    assert roles == []


def test_rbac_platform_roles_list_requires_platform_role_grant(tmp_path: Path) -> None:
    database_path = tmp_path / "rbac_platform_roles.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_platform_user(
            settings, "platform_admin", "padmin@example.com", "Platform Admin", "admin-secret", "admin"
        )

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": "padmin@example.com", "password": "admin-secret"},
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

        response = client.get("/api/v1/rbac/platform/roles", headers=admin_headers)
        assert response.status_code == 200
        by_role = {item["role"]: item for item in response.json()["items"]}
        assert set(by_role) == {"admin", "expert", "operator"}
        assert by_role["admin"]["name"] == "admin"
        assert "platform:role_grant" in by_role["admin"]["permissions"]
        assert "kb:create" in by_role["expert"]["permissions"]
        assert "kb:read" in by_role["operator"]["permissions"]

        tenant_register = client.post(
            "/api/v1/users/register",
            json={"email": "tenant@example.com", "password": "secret123", "name": "Tenant User"},
        )
        assert tenant_register.status_code == 201
        tenant_headers = {"Authorization": f"Bearer {tenant_register.json()['accessToken']}"}
        forbidden = client.get("/api/v1/rbac/platform/roles", headers=tenant_headers)
        assert forbidden.status_code == 403


def test_rbac_platform_last_admin_guard(tmp_path: Path) -> None:
    database_path = tmp_path / "rbac_platform_last_admin.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_platform_user(
            settings, "platform_admin", "padmin@example.com", "Platform Admin", "admin-secret", "admin"
        )

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "padmin@example.com", "password": "admin-secret"},
        )
        headers = {"Authorization": f"Bearer {login_response.json()['accessToken']}"}

        revoke_last_admin = client.delete(
            "/api/v1/rbac/platform/users/platform_admin/roles/admin", headers=headers
        )
        assert revoke_last_admin.status_code == 409


def test_rbac_platform_role_changes_invalidate_existing_access_token(tmp_path: Path) -> None:
    database_path = tmp_path / "rbac_stale_platform_token.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_platform_user(
            settings, "platform_admin", "padmin@example.com", "Platform Admin", "admin-secret", "admin"
        )
        _seed_platform_user(
            settings, "expert_user", "expert@example.com", "Expert User", "expert-secret", "expert"
        )

        expert_login = client.post(
            "/api/v1/auth/login",
            json={"email": "expert@example.com", "password": "expert-secret"},
        )
        stale_headers = {"Authorization": f"Bearer {expert_login.json()['accessToken']}"}

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": "padmin@example.com", "password": "admin-secret"},
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

        revoke_expert = client.delete(
            "/api/v1/rbac/platform/users/expert_user/roles/expert", headers=admin_headers
        )
        assert revoke_expert.status_code == 204

        stale_request = client.post(
            "/api/v1/knowledge-bases",
            headers=stale_headers,
            json={"name": "KB", "description": "test"},
        )
        assert stale_request.status_code == 403


def test_losing_tenant_membership_keeps_platform_access(tmp_path: Path) -> None:
    database_path = tmp_path / "stale_tenant_platform.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        # A user who is both a platform admin and a member of a team tenant.
        _seed_platform_user(
            settings, "dual_user", "dual@example.com", "Dual User", "dual-secret", "admin"
        )
        with open_database_connection(settings) as connection:
            connection.execute(
                """
                insert into tenants (id, type, name, slug, status)
                values ('team_x', 'team', 'Team X', 'team-x', 'active')
                """
            )
            connection.execute(
                """
                insert into tenant_members (id, tenant_id, user_id, role)
                values ('member_x', 'team_x', 'dual_user', 'member')
                """
            )
            connection.commit()

        login = client.post(
            "/api/v1/auth/login",
            json={"email": "dual@example.com", "password": "dual-secret"},
        )
        # Token now carries activeTenantId=team_x.
        token = login.json()["accessToken"]
        platform_headers = {"Authorization": f"Bearer {token}"}

        # Simulate the user being removed from the team tenant.
        with open_database_connection(settings) as connection:
            connection.execute("delete from tenant_members where user_id = 'dual_user'")
            connection.commit()

        # Platform access must survive the loss of the tenant membership.
        platform_call = client.post(
            "/api/v1/users/platform",
            headers=platform_headers,
            json={"email": "invitee@example.com", "name": "Invitee", "roles": ["expert"]},
        )
        assert platform_call.status_code == 201

        # Tenant-scoped access for the now-stale tenant is still rejected.
        tenant_call = client.get(
            "/api/v1/rbac/tenant/users",
            headers={**platform_headers, "x-tenant-id": "team_x"},
        )
        assert tenant_call.status_code == 403


def test_rbac_ops_cannot_grant_admin(tmp_path: Path) -> None:
    database_path = tmp_path / "rbac_ops.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_platform_user(
            settings,
            "ops_user",
            "ops@example.com",
            "Ops User",
            "ops-secret",
            "operator",
        )
        _seed_user(settings, "target_user", "target@example.com", "Target User", "target-secret")

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "ops@example.com", "password": "ops-secret"},
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["accessToken"]

        grant_response = client.post(
            "/api/v1/rbac/platform/users/target_user/roles",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={"role": "admin"},
        )
        assert grant_response.status_code == 403

        create_admin_response = client.post(
            "/api/v1/users/platform",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "email": "new-admin@example.com",
                "name": "New Admin",
                "roles": ["admin"],
            },
        )
        assert create_admin_response.status_code == 403


def test_platform_admin_creates_platform_user_invitation_and_user_activates(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "platform_invite.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_platform_user(
            settings,
            "platform_admin",
            "platform-admin@example.com",
            "Platform Admin",
            "admin-secret",
            "admin",
        )

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "platform-admin@example.com", "password": "admin-secret"},
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["accessToken"]

        create_response = client.post(
            "/api/v1/users/platform",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "email": "Invited-Expert@Example.com",
                "name": "Invited Expert",
                "roles": ["expert"],
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["email"] == "invited-expert@example.com"
        assert created["status"] == "pending_activation"
        assert created["platformRoles"] == ["expert"]
        assert created["activationToken"]
        assert created["activationExpiresAt"]

        pending_login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "invited-expert@example.com", "password": "new-secret"},
        )
        assert pending_login_response.status_code == 401

        activation_response = client.post(
            "/api/v1/users/platform/activate",
            json={
                "token": created["activationToken"],
                "newPassword": "new-secret",
            },
        )
        assert activation_response.status_code == 200
        assert activation_response.json()["userId"] == created["id"]

        invited_login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "invited-expert@example.com", "password": "new-secret"},
        )
        assert invited_login_response.status_code == 200

    with open_database_connection(settings) as connection:
        user = connection.execute(
            "select id, status from users where email = 'invited-expert@example.com'"
        ).fetchone()
        roles = [
            row["role"]
            for row in connection.execute(
                "select role from platform_user_roles where user_id = ?",
                (user["id"],),
            ).fetchall()
        ]
        token = connection.execute(
            "select used_at from platform_activation_tokens where user_id = ?",
            (user["id"],),
        ).fetchone()

    assert user["status"] == "active"
    assert roles == ["expert"]
    assert token["used_at"] is not None


def test_platform_user_list_requires_platform_user_manage(tmp_path: Path) -> None:
    database_path = tmp_path / "platform_user_list.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_platform_user(
            settings,
            "platform_admin",
            "platform-admin@example.com",
            "Platform Admin",
            "admin-secret",
            "admin",
        )

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": "platform-admin@example.com", "password": "admin-secret"},
        )
        assert admin_login.status_code == 200
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

        create_response = client.post(
            "/api/v1/users/platform",
            headers=admin_headers,
            json={
                "email": "invited-expert@example.com",
                "name": "Invited Expert",
                "roles": ["expert"],
            },
        )
        assert create_response.status_code == 201

        list_response = client.get("/api/v1/users/platform", headers=admin_headers)
        assert list_response.status_code == 200
        by_email = {item["email"]: item for item in list_response.json()["items"]}
        assert by_email["platform-admin@example.com"]["platformRoles"] == ["admin"]
        assert by_email["invited-expert@example.com"]["name"] == "Invited Expert"
        assert by_email["invited-expert@example.com"]["status"] == "pending_activation"
        assert by_email["invited-expert@example.com"]["platformRoles"] == ["expert"]
        assert "kb:create" in by_email["invited-expert@example.com"]["platformPermissions"]
        assert by_email["invited-expert@example.com"]["tenantRoles"] == []

        tenant_register = client.post(
            "/api/v1/users/register",
            json={"email": "tenant@example.com", "password": "secret123", "name": "Tenant User"},
        )
        assert tenant_register.status_code == 201
        tenant_headers = {"Authorization": f"Bearer {tenant_register.json()['accessToken']}"}
        forbidden = client.get("/api/v1/users/platform", headers=tenant_headers)
        assert forbidden.status_code == 403


def test_managed_users_crud_and_tenants_require_platform_user_manage(tmp_path: Path) -> None:
    database_path = tmp_path / "managed_users.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_tenant(settings)
        _seed_platform_user(
            settings,
            "platform_admin",
            "platform-admin@example.com",
            "Platform Admin",
            "admin-secret",
            "admin",
        )
        _seed_tenant_user(
            settings,
            "tenant_user",
            "tenant@example.com",
            "Tenant User",
            "tenant-secret",
            "member",
        )
        with open_database_connection(settings) as connection:
            connection.execute(
                """
                insert into tenants (id, type, name, slug, owner_user_id, status)
                values ('team_extra', 'team', 'Extra Team', 'extra-team', 'tenant_user', 'active')
                """
            )
            connection.execute(
                """
                insert into tenant_members (id, tenant_id, user_id, role)
                values ('tenant_user_extra_member', 'team_extra', 'tenant_user', 'admin')
                """
            )
            connection.commit()

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": "platform-admin@example.com", "password": "admin-secret"},
        )
        assert admin_login.status_code == 200
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

        list_response = client.get("/api/v1/users", headers=admin_headers)
        assert list_response.status_code == 200
        listed_by_email = {item["email"]: item for item in list_response.json()["items"]}
        assert "tenant@example.com" in listed_by_email
        assert "platform-admin@example.com" not in listed_by_email
        assert listed_by_email["tenant@example.com"]["tenantCount"] == 2
        assert listed_by_email["tenant@example.com"]["platformRoles"] == []

        detail = client.get("/api/v1/users/tenant_user", headers=admin_headers)
        assert detail.status_code == 200
        detail_body = detail.json()
        assert detail_body["email"] == "tenant@example.com"
        assert {tenant["id"] for tenant in detail_body["tenants"]} == {
            "tenant_default",
            "team_extra",
        }

        tenants = client.get("/api/v1/users/tenant_user/tenants", headers=admin_headers)
        assert tenants.status_code == 200
        assert len(tenants.json()["items"]) == 2

        patched = client.patch(
            "/api/v1/users/tenant_user",
            headers=admin_headers,
            json={"name": "Renamed Tenant User"},
        )
        assert patched.status_code == 200
        assert patched.json()["name"] == "Renamed Tenant User"

        disabled = client.patch(
            "/api/v1/users/tenant_user/status",
            headers=admin_headers,
            json={"status": "disabled"},
        )
        assert disabled.status_code == 200
        assert disabled.json()["status"] == "disabled"

        disabled_login = client.post(
            "/api/v1/auth/login",
            json={"email": "tenant@example.com", "password": "tenant-secret"},
        )
        assert disabled_login.status_code == 401

        missing = client.get("/api/v1/users/missing_user", headers=admin_headers)
        assert missing.status_code == 404

        tenant_register = client.post(
            "/api/v1/users/register",
            json={"email": "plain@example.com", "password": "secret123", "name": "Plain User"},
        )
        assert tenant_register.status_code == 201
        tenant_headers = {"Authorization": f"Bearer {tenant_register.json()['accessToken']}"}
        forbidden = client.get("/api/v1/users", headers=tenant_headers)
        assert forbidden.status_code == 403


def test_platform_tenant_management_crud_members_and_guards(tmp_path: Path) -> None:
    database_path = tmp_path / "tenant_management.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_platform_user(
            settings,
            "platform_admin",
            "platform-admin@example.com",
            "Platform Admin",
            "admin-secret",
            "admin",
        )
        _seed_user(settings, "owner_user", "owner@example.com", "Owner User", "owner-secret")
        _seed_user(settings, "member_user", "member@example.com", "Member User", "member-secret")

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": "platform-admin@example.com", "password": "admin-secret"},
        )
        assert admin_login.status_code == 200
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

        created = client.post(
            "/api/v1/tenants",
            headers=admin_headers,
            json={"name": "Acme Team", "slug": "acme-team", "ownerUserId": "owner_user"},
        )
        assert created.status_code == 201, created.text
        tenant = created.json()
        tenant_id = tenant["id"]
        assert tenant["type"] == "team"
        assert tenant["slug"] == "acme-team"
        assert tenant["ownerUserName"] == "Owner User"
        assert tenant["memberCount"] == 1

        listed = client.get("/api/v1/tenants", headers=admin_headers)
        assert listed.status_code == 200
        assert any(item["id"] == tenant_id for item in listed.json()["items"])

        got = client.get(f"/api/v1/tenants/{tenant_id}", headers=admin_headers)
        assert got.status_code == 200
        assert got.json()["memberCount"] == 1

        members = client.get(f"/api/v1/tenants/{tenant_id}/members", headers=admin_headers)
        assert members.status_code == 200
        assert members.json()["items"] == [
            {
                "userId": "owner_user",
                "email": "owner@example.com",
                "name": "Owner User",
                "status": "active",
                "role": "admin",
                "joinedAt": members.json()["items"][0]["joinedAt"],
            }
        ]

        added = client.post(
            f"/api/v1/tenants/{tenant_id}/members",
            headers=admin_headers,
            json={"userId": "member_user", "role": "member"},
        )
        assert added.status_code == 201
        assert added.json()["role"] == "member"

        promoted = client.patch(
            f"/api/v1/tenants/{tenant_id}/members/member_user",
            headers=admin_headers,
            json={"role": "admin"},
        )
        assert promoted.status_code == 200
        assert promoted.json()["role"] == "admin"

        patched = client.patch(
            f"/api/v1/tenants/{tenant_id}",
            headers=admin_headers,
            json={"name": "Acme Renamed", "slug": "acme-renamed", "ownerUserId": "member_user"},
        )
        assert patched.status_code == 200
        assert patched.json()["name"] == "Acme Renamed"
        assert patched.json()["ownerUserName"] == "Member User"

        demoted_owner = client.patch(
            f"/api/v1/tenants/{tenant_id}/members/owner_user",
            headers=admin_headers,
            json={"role": "member"},
        )
        assert demoted_owner.status_code == 200
        assert demoted_owner.json()["role"] == "member"

        remove_last_admin = client.delete(
            f"/api/v1/tenants/{tenant_id}/members/member_user",
            headers=admin_headers,
        )
        assert remove_last_admin.status_code == 409

        disabled = client.patch(
            f"/api/v1/tenants/{tenant_id}/status",
            headers=admin_headers,
            json={"status": "disabled"},
        )
        assert disabled.status_code == 200
        assert disabled.json()["status"] == "disabled"

        duplicate = client.post(
            "/api/v1/tenants",
            headers=admin_headers,
            json={"name": "Duplicate", "slug": "acme-renamed", "ownerUserId": "owner_user"},
        )
        assert duplicate.status_code == 409

        missing_owner = client.post(
            "/api/v1/tenants",
            headers=admin_headers,
            json={"name": "Missing Owner", "slug": "missing-owner", "ownerUserId": "missing"},
        )
        assert missing_owner.status_code == 404

        tenant_register = client.post(
            "/api/v1/users/register",
            json={"email": "plain@example.com", "password": "secret123", "name": "Plain User"},
        )
        assert tenant_register.status_code == 201
        tenant_headers = {"Authorization": f"Bearer {tenant_register.json()['accessToken']}"}
        forbidden = client.get("/api/v1/tenants", headers=tenant_headers)
        assert forbidden.status_code == 403


def test_expert_category_crud_permissions_and_delete_guard(tmp_path: Path) -> None:
    database_path = tmp_path / "expert_categories.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_platform_user(
            settings,
            "platform_admin",
            "platform-admin@example.com",
            "Platform Admin",
            "admin-secret",
            "admin",
        )
        _seed_platform_user(
            settings,
            "operator_user",
            "operator@example.com",
            "Operator User",
            "operator-secret",
            "operator",
        )

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": "platform-admin@example.com", "password": "admin-secret"},
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

        created = client.post(
            "/api/v1/expert-categories",
            headers=admin_headers,
            json={"name": "Amazon Operations", "description": "Marketplace experts"},
        )
        assert created.status_code == 201, created.text
        category = created.json()
        assert category["name"] == "Amazon Operations"
        assert category["description"] == "Marketplace experts"

        listed = client.get("/api/v1/expert-categories", headers=admin_headers)
        assert listed.status_code == 200
        assert any(item["id"] == category["id"] for item in listed.json()["items"])

        got = client.get(f"/api/v1/expert-categories/{category['id']}", headers=admin_headers)
        assert got.status_code == 200
        assert got.json()["id"] == category["id"]

        patched = client.patch(
            f"/api/v1/expert-categories/{category['id']}",
            headers=admin_headers,
            json={"name": "Amazon Growth", "description": None},
        )
        assert patched.status_code == 200
        assert patched.json()["name"] == "Amazon Growth"
        assert patched.json()["description"] == "Marketplace experts"

        duplicate = client.post(
            "/api/v1/expert-categories",
            headers=admin_headers,
            json={"name": "Amazon Growth"},
        )
        assert duplicate.status_code == 409

        operator_login = client.post(
            "/api/v1/auth/login",
            json={"email": "operator@example.com", "password": "operator-secret"},
        )
        operator_headers = {"Authorization": f"Bearer {operator_login.json()['accessToken']}"}
        operator_list = client.get("/api/v1/expert-categories", headers=operator_headers)
        assert operator_list.status_code == 200
        operator_create = client.post(
            "/api/v1/expert-categories",
            headers=operator_headers,
            json={"name": "Operator Category"},
        )
        assert operator_create.status_code == 403

        with open_database_connection(settings) as connection:
            connection.execute(
                """
                insert into experts (id, category_id, name, ability_intro, status)
                values ('expert_in_use', ?, 'In Use', 'Used by delete guard.', 'draft')
                """,
                (category["id"],),
            )
            connection.commit()

        in_use_delete = client.delete(
            f"/api/v1/expert-categories/{category['id']}", headers=admin_headers
        )
        assert in_use_delete.status_code == 409

        with open_database_connection(settings) as connection:
            connection.execute("delete from experts where id = 'expert_in_use'")
            connection.commit()

        deleted = client.delete(
            f"/api/v1/expert-categories/{category['id']}", headers=admin_headers
        )
        assert deleted.status_code == 204
        missing = client.get(f"/api/v1/expert-categories/{category['id']}", headers=admin_headers)
        assert missing.status_code == 404


def test_expert_crud_relations_status_and_permissions(tmp_path: Path) -> None:
    database_path = tmp_path / "experts.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_platform_user(
            settings,
            "platform_admin",
            "platform-admin@example.com",
            "Platform Admin",
            "admin-secret",
            "admin",
        )
        _seed_platform_user(
            settings,
            "operator_user",
            "operator@example.com",
            "Operator User",
            "operator-secret",
            "operator",
        )
        with open_database_connection(settings) as connection:
            connection.execute(
                """
                insert into expert_categories (id, name, description)
                values ('expert_cat_ops', 'Operations', 'Operations experts')
                """
            )
            connection.execute(
                """
                insert into expert_categories (id, name, description)
                values ('expert_cat_growth', 'Growth', 'Growth experts')
                """
            )
            connection.execute(
                """
                insert into skills (
                  id, slug, name, description, allowed_tools, file_paths, tags, storage_uri
                )
                values (
                  'skill_ops', 'ops-skill', 'Ops Skill', 'Ops helper', '[]', '[]', '[]',
                  'local://ops-skill'
                )
                """
            )
            connection.execute(
                """
                insert into skills (
                  id, slug, name, description, allowed_tools, file_paths, tags, storage_uri
                )
                values (
                  'skill_growth', 'growth-skill', 'Growth Skill', 'Growth helper', '[]',
                  '[]', '[]', 'local://growth-skill'
                )
                """
            )
            connection.execute(
                """
                insert into knowledge_bases (id, owner_user_id, name, status, metadata)
                values ('kb_ops', 'platform_admin', 'Ops KB', 'active', '{}')
                """
            )
            connection.execute(
                """
                insert into knowledge_bases (id, owner_user_id, name, status, metadata)
                values ('kb_growth', 'platform_admin', 'Growth KB', 'active', '{}')
                """
            )
            connection.commit()

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": "platform-admin@example.com", "password": "admin-secret"},
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

        created = client.post(
            "/api/v1/experts",
            headers=admin_headers,
            json={
                "name": "Listing Expert",
                "categoryId": "expert_cat_ops",
                "abilityIntro": "Helps optimize listings.",
                "tags": ["listing", "ops", "listing"],
                "status": "draft",
                "skillIds": ["skill_ops"],
                "knowledgeBaseIds": ["kb_ops"],
                "guideQuestions": ["How to improve listing?", "Why did traffic drop?"],
                "summonButtonText": "Ask expert",
            },
        )
        assert created.status_code == 201, created.text
        expert = created.json()
        expert_id = expert["id"]
        assert expert["categoryName"] == "Operations"
        assert expert["tags"] == ["listing", "ops"]
        assert expert["skillIds"] == ["skill_ops"]
        assert expert["knowledgeBaseIds"] == ["kb_ops"]

        listed = client.get("/api/v1/experts", headers=admin_headers)
        assert listed.status_code == 200
        assert any(item["id"] == expert_id for item in listed.json()["items"])

        got = client.get(f"/api/v1/experts/{expert_id}", headers=admin_headers)
        assert got.status_code == 200
        assert got.json()["guideQuestions"] == [
            "How to improve listing?",
            "Why did traffic drop?",
        ]

        patched = client.patch(
            f"/api/v1/experts/{expert_id}",
            headers=admin_headers,
            json={
                "name": "Growth Expert",
                "categoryId": "expert_cat_growth",
                "abilityIntro": "Helps grow conversion.",
                "tags": ["growth"],
                "skillIds": ["skill_growth"],
                "knowledgeBaseIds": ["kb_growth"],
                "guideQuestions": [],
                "summonButtonText": "Start",
            },
        )
        assert patched.status_code == 200
        patched_body = patched.json()
        assert patched_body["name"] == "Growth Expert"
        assert patched_body["categoryName"] == "Growth"
        assert patched_body["skillIds"] == ["skill_growth"]
        assert patched_body["knowledgeBaseIds"] == ["kb_growth"]
        assert patched_body["guideQuestions"] == []

        published = client.patch(
            f"/api/v1/experts/{expert_id}/status",
            headers=admin_headers,
            json={"status": "published"},
        )
        assert published.status_code == 200
        assert published.json()["status"] == "published"

        # A soft-deleted knowledge base must drop out of the expert's knowledgeBaseIds
        # (the join-table ON DELETE CASCADE only fires at GC purge time).
        with open_database_connection(settings) as connection:
            connection.execute(
                "update knowledge_bases set deleted_at = '2026-06-09T00:00:00+00:00'"
                " where id = ?",
                ("kb_growth",),
            )
            connection.commit()
        after_soft_delete = client.get(f"/api/v1/experts/{expert_id}", headers=admin_headers)
        assert after_soft_delete.status_code == 200
        assert after_soft_delete.json()["knowledgeBaseIds"] == []

        missing_skill = client.post(
            "/api/v1/experts",
            headers=admin_headers,
            json={
                "name": "Broken Expert",
                "categoryId": "expert_cat_ops",
                "abilityIntro": "Broken.",
                "skillIds": ["missing_skill"],
            },
        )
        assert missing_skill.status_code == 404

        too_many_questions = client.post(
            "/api/v1/experts",
            headers=admin_headers,
            json={
                "name": "Too Many Questions",
                "categoryId": "expert_cat_ops",
                "abilityIntro": "Too many.",
                "guideQuestions": ["q1", "q2", "q3", "q4"],
            },
        )
        assert too_many_questions.status_code == 422

        operator_login = client.post(
            "/api/v1/auth/login",
            json={"email": "operator@example.com", "password": "operator-secret"},
        )
        operator_headers = {"Authorization": f"Bearer {operator_login.json()['accessToken']}"}
        operator_list = client.get("/api/v1/experts", headers=operator_headers)
        assert operator_list.status_code == 200
        operator_create = client.post(
            "/api/v1/experts",
            headers=operator_headers,
            json={
                "name": "Operator Expert",
                "categoryId": "expert_cat_ops",
                "abilityIntro": "Not allowed.",
            },
        )
        assert operator_create.status_code == 403

        deleted = client.delete(f"/api/v1/experts/{expert_id}", headers=admin_headers)
        assert deleted.status_code == 204
        missing = client.get(f"/api/v1/experts/{expert_id}", headers=admin_headers)
        assert missing.status_code == 404
        with open_database_connection(settings) as connection:
            links = connection.execute(
                "select id from expert_skills where expert_id = ?", (expert_id,)
            ).fetchall()
        assert links == []


def test_expert_stats_summary_counts_statuses(tmp_path: Path) -> None:
    database_path = tmp_path / "expert_stats.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_platform_user(
            settings,
            "platform_admin",
            "platform-admin@example.com",
            "Platform Admin",
            "admin-secret",
            "admin",
        )
        with open_database_connection(settings) as connection:
            connection.execute(
                """
                insert into expert_categories (id, name, description)
                values ('expert_cat_stats', 'Stats', 'Stats experts')
                """
            )
            for expert_id, status in [
                ("expert_published_1", "published"),
                ("expert_published_2", "published"),
                ("expert_draft", "draft"),
                ("expert_unlisted", "unlisted"),
            ]:
                connection.execute(
                    """
                    insert into experts (id, category_id, name, ability_intro, status)
                    values (?, 'expert_cat_stats', ?, 'Stats helper.', ?)
                    """,
                    (expert_id, expert_id, status),
                )
            connection.commit()

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": "platform-admin@example.com", "password": "admin-secret"},
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

        response = client.get("/api/v1/experts/stats/summary", headers=admin_headers)
        assert response.status_code == 200
        assert response.json() == {
            "total": 4,
            "published": 2,
            "draft": 1,
            "unlisted": 1,
        }


def test_expert_search_by_name_category_and_status(tmp_path: Path) -> None:
    database_path = tmp_path / "expert_search.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_platform_user(
            settings,
            "platform_admin",
            "platform-admin@example.com",
            "Platform Admin",
            "admin-secret",
            "admin",
        )
        with open_database_connection(settings) as connection:
            connection.execute(
                """
                insert into expert_categories (id, name, description)
                values ('expert_cat_ops', 'Operations', null)
                """
            )
            connection.execute(
                """
                insert into expert_categories (id, name, description)
                values ('expert_cat_ads', 'Advertising', null)
                """
            )
            for expert_id, category_id, name, status in [
                ("expert_listing", "expert_cat_ops", "Listing Expert", "published"),
                ("expert_store", "expert_cat_ops", "Store Operations Expert", "draft"),
                ("expert_ads", "expert_cat_ads", "Advertising Expert", "unlisted"),
            ]:
                connection.execute(
                    """
                    insert into experts (id, category_id, name, ability_intro, status)
                    values (?, ?, ?, 'Search helper.', ?)
                    """,
                    (expert_id, category_id, name, status),
                )
            connection.commit()

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": "platform-admin@example.com", "password": "admin-secret"},
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

        by_name = client.get(
            "/api/v1/experts",
            headers=admin_headers,
            params={"name": "listing"},
        )
        assert by_name.status_code == 200
        assert [item["id"] for item in by_name.json()["items"]] == ["expert_listing"]

        by_category = client.get(
            "/api/v1/experts",
            headers=admin_headers,
            params={"categoryId": "expert_cat_ops"},
        )
        assert by_category.status_code == 200
        assert {item["id"] for item in by_category.json()["items"]} == {
            "expert_listing",
            "expert_store",
        }

        by_status = client.get(
            "/api/v1/experts",
            headers=admin_headers,
            params={"status": "unlisted"},
        )
        assert by_status.status_code == 200
        assert [item["id"] for item in by_status.json()["items"]] == ["expert_ads"]

        # Filters compose on the single list endpoint.
        combined = client.get(
            "/api/v1/experts",
            headers=admin_headers,
            params={"categoryId": "expert_cat_ops", "status": "published"},
        )
        assert combined.status_code == 200
        assert [item["id"] for item in combined.json()["items"]] == ["expert_listing"]


def test_expert_market_is_public_and_only_lists_published_experts(tmp_path: Path) -> None:
    database_path = tmp_path / "expert_market.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        with open_database_connection(settings) as connection:
            connection.execute(
                """
                insert into expert_categories (id, name, description)
                values ('expert_cat_ops', 'Operations', 'Operations experts')
                """
            )
            connection.execute(
                """
                insert into expert_categories (id, name, description)
                values ('expert_cat_ads', 'Advertising', 'Advertising experts')
                """
            )
            for expert_id, category_id, name, status in [
                ("expert_listing", "expert_cat_ops", "Listing Expert", "published"),
                ("expert_store", "expert_cat_ops", "Store Expert", "draft"),
                ("expert_ads", "expert_cat_ads", "Ads Expert", "unlisted"),
            ]:
                connection.execute(
                    """
                    insert into experts (
                      id, category_id, name, ability_intro, tags, status,
                      guide_questions, summon_button_text
                    )
                    values (?, ?, ?, 'Public helper.', '["tag"]', ?, '["q1"]', 'Ask')
                    """,
                    (expert_id, category_id, name, status),
                )
            connection.commit()

        categories = client.get("/api/v1/expert-market/categories")
        assert categories.status_code == 200
        assert categories.json()["items"] == [
            {
                "id": "expert_cat_ops",
                "name": "Operations",
                "description": "Operations experts",
            }
        ]

        experts = client.get("/api/v1/expert-market/experts")
        assert experts.status_code == 200
        assert [item["id"] for item in experts.json()["items"]] == ["expert_listing"]

        by_category = client.get(
            "/api/v1/expert-market/experts",
            params={"categoryId": "expert_cat_ads"},
        )
        assert by_category.status_code == 200
        assert by_category.json()["items"] == []

        detail = client.get("/api/v1/expert-market/experts/expert_listing")
        assert detail.status_code == 200
        assert detail.json() == {
            "id": "expert_listing",
            "name": "Listing Expert",
            "categoryId": "expert_cat_ops",
            "categoryName": "Operations",
            "abilityIntro": "Public helper.",
            "tags": ["tag"],
            "guideQuestions": ["q1"],
            "summonButtonText": "Ask",
        }

        hidden = client.get("/api/v1/expert-market/experts/expert_store")
        assert hidden.status_code == 404


def test_skills_upload_list_get_file_update_and_delete(tmp_path: Path) -> None:
    database_path = tmp_path / "skills.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
        skill_storage_backend="local",
        skill_storage_local_dir=str(tmp_path / "skill-storage"),
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_platform_user(
            settings,
            "expert_user",
            "expert@example.com",
            "Expert User",
            "expert-secret",
            "expert",
        )
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "expert@example.com", "password": "expert-secret"},
        )
        assert login_response.status_code == 200
        headers = {
            "Authorization": f"Bearer {login_response.json()['accessToken']}",
        }

        upload_response = client.post(
            "/api/v1/skills",
            headers=headers,
            files={"file": ("skill.zip", _skill_zip(), "application/zip")},
        )
        assert upload_response.status_code == 201
        uploaded = upload_response.json()
        assert uploaded["slug"] == "amazon-review-analyzer"
        assert uploaded["allowedTools"] == ["Bash(python scripts/analyze_reviews.py:*)"]
        assert uploaded["filePaths"] == ["SKILL.md", "scripts/analyze_reviews.py"]
        assert uploaded["tags"] == ["amazon", "reviews"]

        list_response = client.get("/api/v1/skills?tags=amazon&search=review", headers=headers)
        assert list_response.status_code == 200
        list_body = list_response.json()
        assert [item["slug"] for item in list_body["items"]] == ["amazon-review-analyzer"]
        assert list_body["total"] == 1
        assert list_body["hasMore"] is False

        file_response = client.get(
            "/api/v1/skills/amazon-review-analyzer/file?path=SKILL.md",
            headers=headers,
        )
        assert file_response.status_code == 200
        assert "Analyze Amazon review trends" in file_response.text

        update_response = client.put(
            "/api/v1/skills/amazon-review-analyzer",
            headers=headers,
            json={"description": "Updated description", "tags": ["amazon", "feedback"]},
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["description"] == "Updated description"
        assert updated["tags"] == ["amazon", "feedback"]

        delete_response = client.delete(
            "/api/v1/skills/amazon-review-analyzer?delete_files=true",
            headers=headers,
        )
        assert delete_response.status_code == 204

        missing_response = client.get("/api/v1/skills/amazon-review-analyzer", headers=headers)
        assert missing_response.status_code == 404
        assert not (tmp_path / "skill-storage" / "skills" / "amazon-review-analyzer").exists()


def _skill_test_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'skills.sqlite3'}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
        skill_storage_backend="local",
        skill_storage_local_dir=str(tmp_path / "skill-storage"),
    )


def _login_skill_expert(client: TestClient, settings: Settings) -> dict[str, str]:
    _seed_platform_user(
        settings, "expert_user", "expert@example.com", "Expert User", "expert-secret", "expert"
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "expert@example.com", "password": "expert-secret"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def _skill_md_zip(skill_md: str, *, root: str = "pkg") -> BytesIO:
    content = BytesIO()
    with ZipFile(content, "w") as archive:
        archive.writestr(f"{root}/SKILL.md", skill_md)
    content.seek(0)
    return content


def _binary_skill_zip() -> BytesIO:
    content = BytesIO()
    with ZipFile(content, "w") as archive:
        archive.writestr(
            "pkg/SKILL.md",
            "---\nname: binary-skill\ndescription: Contains a binary asset.\n---\n",
        )
        archive.writestr("pkg/assets/blob.bin", b"\xff\xfe\x00")
    content.seek(0)
    return content


def test_skills_duplicate_slug_conflict(tmp_path: Path) -> None:
    settings = _skill_test_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        headers = _login_skill_expert(client, settings)
        first = client.post(
            "/api/v1/skills",
            headers=headers,
            files={"file": ("skill.zip", _skill_zip(), "application/zip")},
        )
        assert first.status_code == 201
        second = client.post(
            "/api/v1/skills",
            headers=headers,
            files={"file": ("skill.zip", _skill_zip(), "application/zip")},
        )
        assert second.status_code == 409
        assert second.json()["code"] == "SKILL_EXISTS"


def test_skills_upload_slug_accepts_multipart_form_field(tmp_path: Path) -> None:
    settings = _skill_test_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        headers = _login_skill_expert(client, settings)
        response = client.post(
            "/api/v1/skills",
            headers=headers,
            data={"slug": "custom-skill"},
            files={"file": ("skill.zip", _skill_zip(), "application/zip")},
        )
        assert response.status_code == 201
        assert response.json()["slug"] == "custom-skill"


def test_skills_upload_storage_failure_rolls_back_metadata(tmp_path: Path) -> None:
    class FailingSkillStorage:
        deleted = False

        def uri_for(self, slug: str) -> str:
            return f"/skills/{slug}"

        def put_files(self, slug: str, files: dict[str, bytes]) -> str:
            raise RuntimeError("storage unavailable")

        def get_file(self, slug: str, path: str) -> bytes:
            raise AssertionError("not used")

        def delete_skill(self, slug: str) -> None:
            self.deleted = True

    settings = _skill_test_settings(tmp_path)
    storage = FailingSkillStorage()
    test_app = create_app(settings)
    test_app.dependency_overrides[get_skill_storage] = lambda: storage
    with TestClient(test_app, raise_server_exceptions=False) as client:
        headers = _login_skill_expert(client, settings)
        response = client.post(
            "/api/v1/skills",
            headers=headers,
            files={"file": ("skill.zip", _skill_zip(), "application/zip")},
        )
        assert response.status_code == 500

    with open_database_connection(settings) as connection:
        row = connection.execute(
            "select count(*) as count from skills where slug = ?",
            ("amazon-review-analyzer",),
        ).fetchone()
    assert row["count"] == 0
    assert storage.deleted is True


def test_skills_list_pagination(tmp_path: Path) -> None:
    settings = _skill_test_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        headers = _login_skill_expert(client, settings)
        for slug in ("skill-a", "skill-b"):
            response = client.post(
                "/api/v1/skills",
                headers=headers,
                data={"slug": slug},
                files={"file": ("skill.zip", _skill_zip(), "application/zip")},
            )
            assert response.status_code == 201

        page = client.get("/api/v1/skills?limit=1", headers=headers).json()
        assert page["total"] == 2
        assert len(page["items"]) == 1
        assert page["hasMore"] is True

        last = client.get("/api/v1/skills?limit=1&offset=1", headers=headers).json()
        assert last["total"] == 2
        assert last["hasMore"] is False


def test_skills_file_content_type_by_extension(tmp_path: Path) -> None:
    settings = _skill_test_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        headers = _login_skill_expert(client, settings)
        client.post(
            "/api/v1/skills",
            headers=headers,
            files={"file": ("skill.zip", _skill_zip(), "application/zip")},
        )
        response = client.get(
            "/api/v1/skills/amazon-review-analyzer/file?path=scripts/analyze_reviews.py",
            headers=headers,
        )
        assert response.status_code == 200
        content_type = response.headers["content-type"]
        assert "markdown" not in content_type


def test_skills_file_returns_binary_content(tmp_path: Path) -> None:
    settings = _skill_test_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        headers = _login_skill_expert(client, settings)
        upload = client.post(
            "/api/v1/skills",
            headers=headers,
            files={"file": ("skill.zip", _binary_skill_zip(), "application/zip")},
        )
        assert upload.status_code == 201

        response = client.get(
            "/api/v1/skills/binary-skill/file?path=assets/blob.bin",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"
        assert response.content == b"\xff\xfe\x00"


def test_skills_zip_too_many_files(tmp_path: Path) -> None:
    settings = _skill_test_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        headers = _login_skill_expert(client, settings)
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr(
                "pkg/SKILL.md",
                "---\nname: big-skill\ndescription: Too many files.\n---\n",
            )
            for index in range(501):
                archive.writestr(f"pkg/file_{index}.txt", "x")
        buffer.seek(0)
        response = client.post(
            "/api/v1/skills",
            headers=headers,
            files={"file": ("skill.zip", buffer, "application/zip")},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "SKILL_ZIP_TOO_MANY_FILES"


def test_skills_frontmatter_unclosed_block(tmp_path: Path) -> None:
    settings = _skill_test_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        headers = _login_skill_expert(client, settings)
        skill_md = "---\nname: broken\ndescription: No closing fence.\n# body without close\n"
        response = client.post(
            "/api/v1/skills",
            headers=headers,
            files={"file": ("skill.zip", _skill_md_zip(skill_md), "application/zip")},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "SKILL_INVALID_FRONTMATTER"


def test_skills_frontmatter_inline_lists_and_dashes(tmp_path: Path) -> None:
    settings = _skill_test_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        headers = _login_skill_expert(client, settings)
        skill_md = (
            "---\n"
            "name: dash-skill\n"
            "description: Values with dashes and inline lists.\n"
            "tags: [alpha-one, beta]\n"
            "allowed-tools:\n"
            "  - Bash(some-tool --flag)\n"
            "---\n# Dash Skill\n"
        )
        response = client.post(
            "/api/v1/skills",
            headers=headers,
            files={"file": ("skill.zip", _skill_md_zip(skill_md), "application/zip")},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["tags"] == ["alpha-one", "beta"]
        assert body["allowedTools"] == ["Bash(some-tool --flag)"]


def test_chat_turn_uses_ngent_input_protocol(tmp_path: Path) -> None:
    database_path = tmp_path / "chat_ngent.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
        ngent_base_url="http://ngent.test",
        ngent_default_cwd=str(tmp_path / "ngent-workspace"),
    )
    fake_ngent = FakeNgentClient()
    test_app = create_app(settings)
    test_app.dependency_overrides[get_ngent_client] = lambda: fake_ngent

    with TestClient(test_app) as client:
        _seed_tenant(settings)
        _seed_tenant_user(
            settings,
            "tenant_user",
            "tenant@example.com",
            "Tenant User",
            "tenant-secret",
            "member",
        )
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "tenant@example.com",
                "password": "tenant-secret",
                "tenantId": "tenant_default",
            },
        )
        assert login.status_code == 200
        headers = {
            "Authorization": f"Bearer {login.json()['accessToken']}",
            "x-tenant-id": "tenant_default",
        }

        created = client.post(
            "/api/v1/chat/sessions",
            headers=headers,
            json={"title": "Protocol Test"},
        )
        assert created.status_code == 201
        session_id = created.json()["id"]

        turn = client.post(
            f"/api/v1/chat/sessions/{session_id}/turns",
            headers=headers,
            json={
                "question": "hello",
                "knowledgeBaseIds": ["kb_1"],
                "llmModel": "model_1",
                "queryRewrite": True,
                "multiHop": {"enabled": True},
            },
        )

        assert turn.status_code == 200
        assert "event: turn_completed" in turn.text
        assert fake_ngent.stream_calls == [
            {
                "method": "POST",
                "path": f"/v1/threads/{session_id}/turns",
                "tenant_id": "tenant_default",
                "json": {"input": "hello", "stream": True},
            }
        ]
        assert "prompt" not in fake_ngent.stream_calls[0]["json"]
        assert "agentOptions" not in fake_ngent.stream_calls[0]["json"]

        messages = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=headers)
        assert messages.status_code == 200
        assert messages.json()["items"][0]["responseText"] == "ok"


def test_ngent_preserves_remote_posix_cwd() -> None:
    client = NgentClient(Settings(ngent_default_cwd="/usr/local/ngent-workspace"))

    assert client.prepare_cwd("tenant_default") == "/usr/local/ngent-workspace"

    tenant_client = NgentClient(
        Settings(
            ngent_default_cwd="/unused",
            ngent_cwd_base="/usr/local/ngent-workspace/tenants",
        )
    )
    assert (
        tenant_client.prepare_cwd("tenant_default")
        == "/usr/local/ngent-workspace/tenants/tenant_default"
    )


def _seed_tenant(settings: Settings) -> None:
    with open_database_connection(settings) as connection:
        connection.execute(
            """
            insert into tenants (id, type, name, slug, status)
            values ('tenant_default', 'team', 'Default Tenant', 'default', 'active')
            on conflict (id) do nothing
            """
        )
        connection.commit()


def _seed_user(
    settings: Settings,
    user_id: str,
    email: str,
    name: str,
    password: str,
) -> None:
    with open_database_connection(settings) as connection:
        connection.execute(
            """
            insert into users (id, email, password_hash, name, status)
            values (?, ?, ?, ?, 'active')
            """,
            (user_id, email, hash_password(password), name),
        )
        connection.commit()


def _seed_tenant_user(
    settings: Settings,
    user_id: str,
    email: str,
    name: str,
    password: str,
    role: str,
) -> None:
    _seed_user(settings, user_id, email, name, password)
    with open_database_connection(settings) as connection:
        connection.execute(
            """
            insert into tenant_members (id, tenant_id, user_id, role)
            values (?, ?, ?, ?)
            """,
            (f"{user_id}_member", "tenant_default", user_id, role),
        )
        connection.commit()


def _seed_platform_user(
    settings: Settings,
    user_id: str,
    email: str,
    name: str,
    password: str,
    role: str,
) -> None:
    _seed_user(settings, user_id, email, name, password)
    with open_database_connection(settings) as connection:
        connection.execute(
            """
            insert into platform_user_roles (id, user_id, role, assigned_by)
            values (?, ?, ?, ?)
            """,
            (f"{user_id}_platform_role", user_id, role, user_id),
        )
        connection.commit()


class FakeNgentClient:
    def __init__(self) -> None:
        self.default_agent = "codex"
        self.default_cwd = "/tmp/ngent"
        self.stream_calls: list[dict] = []

    def prepare_cwd(self, tenant_id: str | None = None) -> str:
        return self.default_cwd

    async def request(
        self, method: str, path: str, *, tenant_id: str | None = None, **kwargs
    ) -> dict:
        assert method == "POST"
        assert path == "/v1/threads"
        assert tenant_id == "tenant_default"
        assert kwargs["json"]["agent"] == self.default_agent
        assert kwargs["json"]["cwd"] == self.default_cwd
        return {"threadId": "thread_1"}

    async def stream(
        self, method: str, path: str, *, tenant_id: str | None = None, **kwargs
    ):
        self.stream_calls.append(
            {
                "method": method,
                "path": path,
                "tenant_id": tenant_id,
                "json": kwargs["json"],
            }
        )
        yield "event: turn_started"
        yield 'data: {"turnId": "turn_1"}'
        yield ""
        yield "event: message_delta"
        yield 'data: {"delta": "ok"}'
        yield ""
        yield "event: turn_completed"
        yield 'data: {"stopReason": "end_turn"}'
        yield ""


def _skill_zip() -> BytesIO:
    content = BytesIO()
    with ZipFile(content, "w") as archive:
        archive.writestr(
            "amazon-review-analyzer/SKILL.md",
            """---
name: amazon-review-analyzer
description: Analyze Amazon review trends and customer feedback.
version: 1.0.0
allowed-tools:
  - Bash(python scripts/analyze_reviews.py:*)
tags:
  - amazon
  - reviews
---
# Amazon Review Analyzer
""",
        )
        archive.writestr(
            "amazon-review-analyzer/scripts/analyze_reviews.py",
            "print('ok')\n",
        )
    content.seek(0)
    return content


# Knowledge base + document redesign -------------------------------------------------

from app.api.deps import get_object_store  # noqa: E402
from app.services.object_store import ObjectStat, ObjectStore  # noqa: E402


class FakeObjectStore(ObjectStore):
    """In-memory stand-in for MinIO. Tests simulate the client PUT via `put`."""

    def __init__(self, bucket: str = "expert-docs") -> None:
        self._bucket = bucket
        self.objects: dict[str, int] = {}
        self.removed: list[str] = []
        self.fail_remove: set[str] = set()

    @property
    def bucket(self) -> str:
        return self._bucket

    def presigned_put_url(self, object_key, *, expires, content_type=None) -> str:
        return f"https://minio.test/{self._bucket}/{object_key}?put"

    def presigned_get_url(self, object_key, *, expires) -> str:
        return f"https://minio.test/{self._bucket}/{object_key}?get"

    def stat(self, object_key: str) -> ObjectStat:
        if object_key not in self.objects:
            from app.core.errors import ApiError

            raise ApiError(404, "DOC_OBJECT_NOT_FOUND", "Uploaded object not found")
        return ObjectStat(size=self.objects[object_key], etag="fake-md5")

    def remove(self, object_key: str) -> None:
        if object_key in self.fail_remove:
            raise RuntimeError("remove failed")
        self.removed.append(object_key)
        self.objects.pop(object_key, None)

    # test helper
    def put(self, object_key: str, size: int) -> None:
        self.objects[object_key] = size


def _kb_test_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'kb.sqlite3'}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )


def _kb_app(settings: Settings, store: FakeObjectStore):
    app = create_app(settings)
    app.dependency_overrides[get_object_store] = lambda: store
    return app


def _login(client: TestClient, settings: Settings, user_id: str, email: str, role: str) -> dict[str, str]:
    _seed_platform_user(settings, user_id, email, f"{user_id} name", "secret-pass", role)
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret-pass"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def test_kb_crud_has_no_tenant(tmp_path: Path) -> None:
    settings = _kb_test_settings(tmp_path)
    store = FakeObjectStore()
    with TestClient(_kb_app(settings, store)) as client:
        headers = _login(client, settings, "expert_user", "expert@example.com", "expert")
        created = client.post("/api/v1/knowledge-bases", headers=headers, json={"name": "KB One"})
        assert created.status_code == 201, created.text
        body = created.json()
        assert "tenantId" not in body
        assert body["ownerUserId"] == "expert_user"
        assert body["ownerUserName"] == "expert_user name"
        # Removed fields are gone from the contract entirely.
        for gone in ("scope", "visibility", "buildProvider", "buildStatus", "activeBuildId"):
            assert gone not in body
        assert body["status"] == "active"
        kb_id = body["id"]

        got = client.get(f"/api/v1/knowledge-bases/{kb_id}", headers=headers)
        assert got.status_code == 200
        listed = client.get("/api/v1/knowledge-bases", headers=headers)
        assert listed.status_code == 200
        listed_item = next(item for item in listed.json()["items"] if item["id"] == kb_id)
        assert listed_item["ownerUserName"] == "expert_user name"

        patched = client.patch(
            f"/api/v1/knowledge-bases/{kb_id}", headers=headers, json={"name": "KB Renamed"}
        )
        assert patched.status_code == 200
        assert patched.json()["name"] == "KB Renamed"

        deleted = client.delete(f"/api/v1/knowledge-bases/{kb_id}", headers=headers)
        assert deleted.status_code == 204
        assert client.get(f"/api/v1/knowledge-bases/{kb_id}", headers=headers).status_code == 404


def test_document_upload_flow(tmp_path: Path) -> None:
    settings = _kb_test_settings(tmp_path)
    store = FakeObjectStore()
    with TestClient(_kb_app(settings, store)) as client:
        headers = _login(client, settings, "expert_user", "expert@example.com", "expert")
        kb_id = client.post(
            "/api/v1/knowledge-bases", headers=headers, json={"name": "Docs KB"}
        ).json()["id"]

        url_resp = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/upload-url",
            headers=headers,
            json={"fileName": "guide.pdf", "mimeType": "application/pdf", "fileSizeBytes": 1024},
        )
        assert url_resp.status_code == 200, url_resp.text
        payload = url_resp.json()
        assert payload["objectKey"].startswith(f"knowledge-bases/{kb_id}/documents/")
        assert "tenants/" not in payload["objectKey"]

        # Simulate the client PUT to MinIO with the declared size.
        store.put(payload["objectKey"], 1024)

        completed = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/complete-upload",
            headers=headers,
            json={"uploadSessionId": payload["uploadSessionId"], "fileSizeBytes": 1024},
        )
        assert completed.status_code == 201, completed.text
        doc = completed.json()
        assert doc["fileType"] == "pdf"
        assert doc["parseStatus"] == "pending"

        listed = client.get(f"/api/v1/knowledge-bases/{kb_id}/docs", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 1

        dl = client.get(
            f"/api/v1/knowledge-bases/{kb_id}/docs/{doc['id']}/download-url", headers=headers
        )
        assert dl.status_code == 200
        assert dl.json()["downloadUrl"].endswith("?get")

        deleted = client.delete(
            f"/api/v1/knowledge-bases/{kb_id}/docs/{doc['id']}", headers=headers
        )
        assert deleted.status_code == 204
        assert client.get(f"/api/v1/knowledge-bases/{kb_id}/docs", headers=headers).json()["items"] == []


def test_document_batch_upload_flow(tmp_path: Path) -> None:
    settings = _kb_test_settings(tmp_path)
    store = FakeObjectStore()
    with TestClient(_kb_app(settings, store)) as client:
        headers = _login(client, settings, "expert_user", "expert@example.com", "expert")
        kb_id = client.post(
            "/api/v1/knowledge-bases", headers=headers, json={"name": "Batch Docs KB"}
        ).json()["id"]

        url_resp = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/upload-urls",
            headers=headers,
            json={
                "files": [
                    {"fileName": "guide.pdf", "mimeType": "application/pdf", "fileSizeBytes": 1024},
                    {"fileName": "notes.txt", "mimeType": "text/plain", "fileSizeBytes": 12},
                ]
            },
        )
        assert url_resp.status_code == 200, url_resp.text
        uploads = url_resp.json()["items"]
        assert len(uploads) == 2

        store.put(uploads[0]["objectKey"], 1024)
        store.put(uploads[1]["objectKey"], 12)

        completed = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/complete-uploads",
            headers=headers,
            json={
                "items": [
                    {"uploadSessionId": uploads[0]["uploadSessionId"], "fileSizeBytes": 1024},
                    {"uploadSessionId": uploads[1]["uploadSessionId"], "fileSizeBytes": 12},
                ]
            },
        )
        assert completed.status_code == 201, completed.text
        docs = completed.json()["items"]
        assert {doc["fileName"] for doc in docs} == {"guide.pdf", "notes.txt"}

        listed = client.get(f"/api/v1/knowledge-bases/{kb_id}/docs", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 2


def test_complete_upload_size_mismatch_is_rejected(tmp_path: Path) -> None:
    settings = _kb_test_settings(tmp_path)
    store = FakeObjectStore()
    with TestClient(_kb_app(settings, store)) as client:
        headers = _login(client, settings, "expert_user", "expert@example.com", "expert")
        kb_id = client.post(
            "/api/v1/knowledge-bases", headers=headers, json={"name": "KB"}
        ).json()["id"]
        payload = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/upload-url",
            headers=headers,
            json={"fileName": "a.txt", "fileSizeBytes": 100},
        ).json()

        # Client uploaded a larger object than declared.
        store.put(payload["objectKey"], 999)
        resp = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/complete-upload",
            headers=headers,
            json={"uploadSessionId": payload["uploadSessionId"]},
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == "UPLOAD_SIZE_MISMATCH"
        # No document created, object removed.
        assert client.get(f"/api/v1/knowledge-bases/{kb_id}/docs", headers=headers).json()["items"] == []
        assert payload["objectKey"] in store.removed


def test_kb_delete_is_soft_and_gc_reclaims_objects(tmp_path: Path) -> None:
    settings = _kb_test_settings(tmp_path)
    store = FakeObjectStore()
    with TestClient(_kb_app(settings, store)) as client:
        headers = _login(client, settings, "expert_user", "expert@example.com", "expert")
        kb_id = client.post(
            "/api/v1/knowledge-bases", headers=headers, json={"name": "Doomed KB"}
        ).json()["id"]

        payload = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/upload-url",
            headers=headers,
            json={"fileName": "guide.pdf", "mimeType": "application/pdf", "fileSizeBytes": 512},
        ).json()
        object_key = payload["objectKey"]
        store.put(object_key, 512)
        completed = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/complete-upload",
            headers=headers,
            json={"uploadSessionId": payload["uploadSessionId"], "fileSizeBytes": 512},
        )
        assert completed.status_code == 201, completed.text

        # Delete is a soft delete: the base disappears from all reads at once, but the object is
        # NOT reclaimed inline -- a hard cascade would have stranded it.
        assert client.delete(f"/api/v1/knowledge-bases/{kb_id}", headers=headers).status_code == 204
        assert client.get(f"/api/v1/knowledge-bases/{kb_id}", headers=headers).status_code == 404
        assert all(
            item["id"] != kb_id
            for item in client.get("/api/v1/knowledge-bases", headers=headers).json()["items"]
        )
        assert object_key not in store.removed

        # GC reclaims the object, then hard-deletes the rows; a second pass is a no-op.
        from app.db import open_database_connection
        from app.services.document_service import DocumentService

        with open_database_connection(settings) as connection:
            service = DocumentService(connection, store, settings)
            assert service.purge_deleted_knowledge_bases() == 1
            assert service.purge_deleted_knowledge_bases() == 0
        assert object_key in store.removed


def test_complete_upload_concurrent_completion_maps_to_409(tmp_path: Path, monkeypatch) -> None:
    settings = _kb_test_settings(tmp_path)
    store = FakeObjectStore()
    with TestClient(_kb_app(settings, store)) as client:
        headers = _login(client, settings, "expert_user", "expert@example.com", "expert")
        kb_id = client.post(
            "/api/v1/knowledge-bases", headers=headers, json={"name": "KB"}
        ).json()["id"]
        payload = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/upload-url",
            headers=headers,
            json={"fileName": "a.txt", "fileSizeBytes": 64},
        ).json()
        store.put(payload["objectKey"], 64)
        body = {"uploadSessionId": payload["uploadSessionId"], "fileSizeBytes": 64}

        first = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/complete-upload", headers=headers, json=body
        )
        assert first.status_code == 201, first.text

        # Simulate a second request that read the session as still `initiated` (the lost race):
        # it passes the status gate and collides on the documents primary key. The guard must
        # turn that into a 409, never a 500.
        from app.services.document_repository import DocumentRepository

        original_get_session = DocumentRepository.get_session

        def stale_get_session(self, session_id):
            session = original_get_session(self, session_id)
            if session is not None:
                session.status = "initiated"
            return session

        monkeypatch.setattr(DocumentRepository, "get_session", stale_get_session)
        second = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/complete-upload", headers=headers, json=body
        )
        assert second.status_code == 409, second.text
        assert second.json()["code"] == "UPLOAD_ALREADY_COMPLETED"
        # Still exactly one document.
        listed = client.get(f"/api/v1/knowledge-bases/{kb_id}/docs", headers=headers)
        assert len(listed.json()["items"]) == 1


def test_document_reads_do_not_require_object_store(tmp_path: Path) -> None:
    settings = _kb_test_settings(tmp_path)
    store = FakeObjectStore()
    app = create_app(settings)
    app.dependency_overrides[get_object_store] = lambda: store
    with TestClient(app) as client:
        headers = _login(client, settings, "expert_user", "expert@example.com", "expert")
        kb_id = client.post(
            "/api/v1/knowledge-bases", headers=headers, json={"name": "KB"}
        ).json()["id"]
        payload = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/upload-url",
            headers=headers,
            json={"fileName": "a.txt", "fileSizeBytes": 32},
        ).json()
        store.put(payload["objectKey"], 32)
        doc_id = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/complete-upload",
            headers=headers,
            json={"uploadSessionId": payload["uploadSessionId"], "fileSizeBytes": 32},
        ).json()["id"]

        # Object storage is now unavailable. Pure-DB routes must not depend on it.
        def broken_store() -> ObjectStore:
            raise RuntimeError("object store is down")

        app.dependency_overrides[get_object_store] = broken_store
        assert client.get(f"/api/v1/knowledge-bases/{kb_id}/docs", headers=headers).status_code == 200
        assert (
            client.get(f"/api/v1/knowledge-bases/{kb_id}/docs/{doc_id}", headers=headers).status_code
            == 200
        )
        assert (
            client.patch(
                f"/api/v1/knowledge-bases/{kb_id}/docs/{doc_id}",
                headers=headers,
                json={"fileName": "b.txt"},
            ).status_code
            == 200
        )
        assert (
            client.delete(
                f"/api/v1/knowledge-bases/{kb_id}/docs/{doc_id}", headers=headers
            ).status_code
            == 204
        )

        # Routes that genuinely mint presigned URLs still surface the broken store.
        with pytest.raises(RuntimeError):
            client.post(
                f"/api/v1/knowledge-bases/{kb_id}/docs/upload-url",
                headers=headers,
                json={"fileName": "c.txt", "fileSizeBytes": 10},
            )


def test_storage_gc_endpoint_reclaims_all_three_classes(tmp_path: Path) -> None:
    settings = _kb_test_settings(tmp_path)
    store = FakeObjectStore()
    with TestClient(_kb_app(settings, store)) as client:
        admin = _login(client, settings, "admin_user", "admin@example.com", "admin")

        kb_id = client.post(
            "/api/v1/knowledge-bases", headers=admin, json={"name": "KB"}
        ).json()["id"]

        # (a) A soft-deleted document -> purgedDocuments.
        doc_payload = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/upload-url",
            headers=admin,
            json={"fileName": "doc.txt", "fileSizeBytes": 16},
        ).json()
        store.put(doc_payload["objectKey"], 16)
        doc_id = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/complete-upload",
            headers=admin,
            json={"uploadSessionId": doc_payload["uploadSessionId"], "fileSizeBytes": 16},
        ).json()["id"]
        client.delete(f"/api/v1/knowledge-bases/{kb_id}/docs/{doc_id}", headers=admin)

        # (b) An expired, never-completed upload session -> expiredSessions.
        orphan = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/upload-url",
            headers=admin,
            json={"fileName": "orphan.txt", "fileSizeBytes": 8},
        ).json()
        store.put(orphan["objectKey"], 8)
        # Force the session past its TTL without waiting on the clock.
        with open_database_connection(settings) as connection:
            connection.execute(
                "update upload_sessions set expires_at = ? where id = ?",
                ("2000-01-01T00:00:00+00:00", orphan["uploadSessionId"]),
            )
            connection.commit()

        # (c) A soft-deleted knowledge base -> purgedKnowledgeBases.
        kb2_id = client.post(
            "/api/v1/knowledge-bases", headers=admin, json={"name": "KB2"}
        ).json()["id"]
        kb2_doc = client.post(
            f"/api/v1/knowledge-bases/{kb2_id}/docs/upload-url",
            headers=admin,
            json={"fileName": "k2.txt", "fileSizeBytes": 4},
        ).json()
        store.put(kb2_doc["objectKey"], 4)
        client.post(
            f"/api/v1/knowledge-bases/{kb2_id}/docs/complete-upload",
            headers=admin,
            json={"uploadSessionId": kb2_doc["uploadSessionId"], "fileSizeBytes": 4},
        )
        client.delete(f"/api/v1/knowledge-bases/{kb2_id}", headers=admin)

        resp = client.post("/api/v1/ops/storage/gc", headers=admin)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body == {
            "expiredSessions": 1,
            "purgedDocuments": 1,
            "purgedKnowledgeBases": 1,
        }
        for key in (doc_payload["objectKey"], orphan["objectKey"], kb2_doc["objectKey"]):
            assert key in store.removed

        # Idempotent: a second pass reclaims nothing.
        assert client.post("/api/v1/ops/storage/gc", headers=admin).json() == {
            "expiredSessions": 0,
            "purgedDocuments": 0,
            "purgedKnowledgeBases": 0,
        }


def test_storage_gc_keeps_rows_when_object_remove_fails(tmp_path: Path) -> None:
    settings = _kb_test_settings(tmp_path)
    store = FakeObjectStore()
    with TestClient(_kb_app(settings, store)) as client:
        admin = _login(client, settings, "admin_user", "admin@example.com", "admin")
        kb_id = client.post(
            "/api/v1/knowledge-bases", headers=admin, json={"name": "KB"}
        ).json()["id"]

        deleted_doc = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/upload-url",
            headers=admin,
            json={"fileName": "deleted.txt", "fileSizeBytes": 16},
        ).json()
        store.put(deleted_doc["objectKey"], 16)
        deleted_doc_id = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/complete-upload",
            headers=admin,
            json={"uploadSessionId": deleted_doc["uploadSessionId"], "fileSizeBytes": 16},
        ).json()["id"]
        assert (
            client.delete(
                f"/api/v1/knowledge-bases/{kb_id}/docs/{deleted_doc_id}", headers=admin
            ).status_code
            == 204
        )

        orphan = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/upload-url",
            headers=admin,
            json={"fileName": "orphan.txt", "fileSizeBytes": 8},
        ).json()
        store.put(orphan["objectKey"], 8)
        with open_database_connection(settings) as connection:
            connection.execute(
                "update upload_sessions set expires_at = ? where id = ?",
                ("2000-01-01T00:00:00+00:00", orphan["uploadSessionId"]),
            )
            connection.commit()

        kb2_id = client.post(
            "/api/v1/knowledge-bases", headers=admin, json={"name": "KB2"}
        ).json()["id"]
        kb_doc = client.post(
            f"/api/v1/knowledge-bases/{kb2_id}/docs/upload-url",
            headers=admin,
            json={"fileName": "kb.txt", "fileSizeBytes": 4},
        ).json()
        store.put(kb_doc["objectKey"], 4)
        client.post(
            f"/api/v1/knowledge-bases/{kb2_id}/docs/complete-upload",
            headers=admin,
            json={"uploadSessionId": kb_doc["uploadSessionId"], "fileSizeBytes": 4},
        )
        assert client.delete(f"/api/v1/knowledge-bases/{kb2_id}", headers=admin).status_code == 204

        store.fail_remove.update(
            {deleted_doc["objectKey"], orphan["objectKey"], kb_doc["objectKey"]}
        )
        assert client.post("/api/v1/ops/storage/gc", headers=admin).json() == {
            "expiredSessions": 0,
            "purgedDocuments": 0,
            "purgedKnowledgeBases": 0,
        }

        with open_database_connection(settings) as connection:
            doc_row = connection.execute(
                "select id from documents where id = ?", (deleted_doc_id,)
            ).fetchone()
            session_row = connection.execute(
                "select status from upload_sessions where id = ?", (orphan["uploadSessionId"],)
            ).fetchone()
            kb_row = connection.execute(
                "select id from knowledge_bases where id = ?", (kb2_id,)
            ).fetchone()
        assert doc_row is not None
        assert session_row["status"] == "initiated"
        assert kb_row is not None

        store.fail_remove.clear()
        assert client.post("/api/v1/ops/storage/gc", headers=admin).json() == {
            "expiredSessions": 1,
            "purgedDocuments": 1,
            "purgedKnowledgeBases": 1,
        }


def test_sqlite_unique_violation_detection_is_specific() -> None:
    import sqlite3

    from app.services._sql import is_unique_violation

    assert is_unique_violation(sqlite3.IntegrityError("UNIQUE constraint failed: documents.id"))
    assert is_unique_violation(sqlite3.IntegrityError("PRIMARY KEY must be unique"))
    assert not is_unique_violation(sqlite3.IntegrityError("CHECK constraint failed: file_type"))
    assert not is_unique_violation(sqlite3.IntegrityError("FOREIGN KEY constraint failed"))


def test_storage_gc_endpoint_requires_system_ops(tmp_path: Path) -> None:
    settings = _kb_test_settings(tmp_path)
    store = FakeObjectStore()
    with TestClient(_kb_app(settings, store)) as client:
        # `expert` authors knowledge bases but holds no system:ops permission.
        expert = _login(client, settings, "expert_user", "expert@example.com", "expert")
        resp = client.post("/api/v1/ops/storage/gc", headers=expert)
        assert resp.status_code == 403


def test_upload_url_rejects_unsupported_type(tmp_path: Path) -> None:
    settings = _kb_test_settings(tmp_path)
    store = FakeObjectStore()
    with TestClient(_kb_app(settings, store)) as client:
        headers = _login(client, settings, "expert_user", "expert@example.com", "expert")
        kb_id = client.post(
            "/api/v1/knowledge-bases", headers=headers, json={"name": "KB"}
        ).json()["id"]
        resp = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/upload-url",
            headers=headers,
            json={"fileName": "malware.exe", "fileSizeBytes": 10},
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == "DOC_UNSUPPORTED_TYPE"


def test_kb_access_is_permission_based_not_owner_based(tmp_path: Path) -> None:
    settings = _kb_test_settings(tmp_path)
    store = FakeObjectStore()
    with TestClient(_kb_app(settings, store)) as client:
        creator = _login(client, settings, "creator_user", "creator@example.com", "expert")
        other = _login(client, settings, "other_user", "other@example.com", "expert")
        kb_id = client.post(
            "/api/v1/knowledge-bases", headers=creator, json={"name": "Platform KB"}
        ).json()["id"]
        # Knowledge bases are platform-owned: any platform user holding kb:delete may delete
        # one, regardless of who created it. ownerUserId is attribution, not access control.
        resp = client.delete(f"/api/v1/knowledge-bases/{kb_id}", headers=other)
        assert resp.status_code == 204


def test_build_endpoint_is_stub(tmp_path: Path) -> None:
    settings = _kb_test_settings(tmp_path)
    store = FakeObjectStore()
    with TestClient(_kb_app(settings, store)) as client:
        headers = _login(client, settings, "expert_user", "expert@example.com", "expert")
        kb_id = client.post(
            "/api/v1/knowledge-bases", headers=headers, json={"name": "KB"}
        ).json()["id"]
        resp = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/build", headers=headers, json={}
        )
        assert resp.status_code == 501
        assert resp.json()["status"] == "not_implemented"

        # A missing knowledge base is a 404, not a 501 -- the placeholder still honours resource
        # semantics rather than acknowledging arbitrary ids.
        missing = client.post(
            "/api/v1/knowledge-bases/kb_does_not_exist/build", headers=headers, json={}
        )
        assert missing.status_code == 404
        assert missing.json()["code"] == "KB_NOT_FOUND"
