import asyncio
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_acp_gateway_client,
    get_skill_storage,
)
from app.clients.acp_gateway import AcpGatewayClient
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
    assert "/api/v1/expert-groups" in paths
    assert "/api/v1/expert-groups/{group_id}" in paths
    assert "/api/v1/expert-groups/{group_id}/experts" in paths
    assert "/api/v1/plans" in paths
    assert "/api/v1/plans/{plan_id}" in paths
    assert "/api/v1/plans/{plan_id}/prices" in paths
    assert "/api/v1/plans/{plan_id}/entitlements" in paths
    assert "/api/v1/plans/{plan_id}/expert-groups" in paths
    assert "/api/v1/plan-market/plans" in paths
    assert "/api/v1/plan-market/current-subscription" in paths
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
    assert "plans" in tables
    assert "plan_prices" in tables
    assert "plan_entitlements" in tables
    assert "expert_groups" in tables
    assert "expert_group_members" in tables
    assert "plan_expert_groups" in tables
    assert "tenant_subscriptions" in tables
    assert "subscription_entitlement_snapshots" in tables


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
        list_body = list_response.json()
        assert list_body["total"] == 1
        assert list_body["page"] == 1
        assert list_body["pageSize"] == 50
        listed_by_email = {item["email"]: item for item in list_body["items"]}
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


def test_managed_users_include_subscription_usage_filters_and_detail(tmp_path: Path) -> None:
    database_path = tmp_path / "managed_users_subscription.sqlite3"
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
                insert into tenant_subscriptions (
                  id,
                  tenant_id,
                  plan_id,
                  status,
                  billing_period,
                  current_period_start,
                  current_period_end,
                  cancel_at_period_end
                )
                values (
                  'sub_tenant_user_pro',
                  'tenant_default',
                  'plan_pro',
                  'active',
                  'monthly',
                  CURRENT_TIMESTAMP,
                  datetime('now', '+9 days'),
                  false
                )
                """
            )
            connection.execute(
                """
                insert into subscription_entitlement_snapshots (
                  id,
                  subscription_id,
                  plan_code,
                  plan_name,
                  billing_period,
                  price_snapshot,
                  entitlements_snapshot,
                  starts_at
                )
                values (
                  'snap_tenant_user_pro',
                  'sub_tenant_user_pro',
                  'pro',
                  '专业版',
                  'monthly',
                  '{"billingPeriod":"monthly","currency":"CNY","amountCents":9900}',
                  '{"monthlyQuestionLimit":100,"monthlyTokenLimit":50000}',
                  CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                insert into chat_sessions (
                  id,
                  tenant_id,
                  user_id,
                  title,
                  agent_options,
                  status
                )
                values (
                  'session_tenant_user',
                  'tenant_default',
                  'tenant_user',
                  'Usage Session',
                  '{}',
                  'active'
                )
                """
            )
            connection.execute(
                """
                insert into chat_turns (
                  id,
                  session_id,
                  tenant_id,
                  user_id,
                  request_text,
                  response_text,
                  status,
                  is_internal
                )
                values
                  (
                    'turn_tenant_user_1',
                    'session_tenant_user',
                    'tenant_default',
                    'tenant_user',
                    'Question 1',
                    'Answer 1',
                    'completed',
                    false
                  ),
                  (
                    'turn_tenant_user_2',
                    'session_tenant_user',
                    'tenant_default',
                    'tenant_user',
                    'Question 2',
                    'Answer 2',
                    'completed',
                    false
                  )
                """
            )
            connection.commit()

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": "platform-admin@example.com", "password": "admin-secret"},
        )
        assert admin_login.status_code == 200
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

        response = client.get(
            "/api/v1/users",
            headers=admin_headers,
            params={
                "search": "专业版",
                "subscriptionStatus": "即将到期",
                "subscriptionType": "专业版 · 月付",
                "sort": "monthlyUsage",
                "page": 1,
                "pageSize": 10,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["page"] == 1
        assert body["pageSize"] == 10
        item = body["items"][0]
        assert item["id"] == "tenant_user"
        assert item["currentSubscription"]["subscriptionId"] == "sub_tenant_user_pro"
        assert item["currentSubscription"]["planName"] == "专业版"
        assert item["currentSubscription"]["billingPeriod"] == "monthly"
        assert item["currentSubscription"]["status"] == "expiring_soon"
        assert item["currentSubscription"]["statusLabel"] == "即将到期"
        assert item["currentSubscription"]["priceLabel"] == "¥99 / 月"
        assert item["monthlyUsage"]["questionUsed"] == 2
        assert item["monthlyUsage"]["questionLimit"] == 100
        assert item["monthlyUsage"]["tokenUsed"] == 0
        assert item["monthlyUsage"]["tokenLimit"] == 50000
        assert item["monthlyUsage"]["status"] == "expiring_soon"
        assert item["orderSummary"] == {
            "totalAmountCents": 0,
            "orderCount": 0,
            "recentOrders": [],
        }
        assert item["usageLifetime"]["usageDays"] >= 1

        detail = client.get("/api/v1/users/tenant_user", headers=admin_headers)
        assert detail.status_code == 200
        detail_body = detail.json()
        assert detail_body["currentSubscription"]["tenantId"] == "tenant_default"
        assert detail_body["monthlyUsage"]["questionUsagePercent"] == 2
        assert detail_body["tenants"][0]["id"] == "tenant_default"


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
        assert tenant["ownerUserEmail"] == "owner@example.com"
        assert tenant["memberCount"] == 1
        assert tenant["currentSubscription"]["planCode"] == "free"
        assert tenant["currentPlan"]["code"] == "free"
        assert tenant["monthlyUsage"]["questionUsed"] == 0

        listed = client.get("/api/v1/tenants", headers=admin_headers)
        assert listed.status_code == 200
        listed_body = listed.json()
        assert listed_body["total"] >= 1
        assert any(item["id"] == tenant_id for item in listed_body["items"])

        got = client.get(f"/api/v1/tenants/{tenant_id}", headers=admin_headers)
        assert got.status_code == 200
        got_body = got.json()
        assert got_body["memberCount"] == 1
        assert got_body["members"][0]["userId"] == "owner_user"

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

        subscription = client.patch(
            f"/api/v1/tenants/{tenant_id}/subscription",
            headers=admin_headers,
            json={"planId": "plan_pro", "billingPeriod": "monthly"},
        )
        assert subscription.status_code == 200, subscription.text
        assert subscription.json()["currentSubscription"]["planCode"] == "pro"
        assert subscription.json()["currentSubscription"]["billingPeriod"] == "monthly"
        assert subscription.json()["currentPlan"]["id"] == "plan_pro"

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


def test_tenant_management_subscription_usage_filters_and_personal_guards(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "tenant_management_subscription.sqlite3"
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
                update tenants
                set type = 'personal',
                    owner_user_id = 'tenant_user'
                where id = 'tenant_default'
                """
            )
            connection.execute(
                """
                insert into tenant_subscriptions (
                  id,
                  tenant_id,
                  plan_id,
                  status,
                  billing_period,
                  current_period_start,
                  current_period_end,
                  cancel_at_period_end
                )
                values (
                  'sub_tenant_default_pro',
                  'tenant_default',
                  'plan_pro',
                  'active',
                  'monthly',
                  CURRENT_TIMESTAMP,
                  datetime('now', '+9 days'),
                  false
                )
                """
            )
            connection.execute(
                """
                insert into subscription_entitlement_snapshots (
                  id,
                  subscription_id,
                  plan_code,
                  plan_name,
                  billing_period,
                  price_snapshot,
                  entitlements_snapshot,
                  starts_at
                )
                values (
                  'snap_tenant_default_pro',
                  'sub_tenant_default_pro',
                  'pro',
                  'Pro',
                  'monthly',
                  '{"billingPeriod":"monthly","currency":"CNY","amountCents":9900}',
                  '{"monthlyQuestionLimit":100,"monthlyTokenLimit":50000}',
                  CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                insert into chat_sessions (
                  id,
                  tenant_id,
                  user_id,
                  title,
                  agent_options,
                  status
                )
                values (
                  'session_tenant_default',
                  'tenant_default',
                  'tenant_user',
                  'Usage Session',
                  '{}',
                  'active'
                )
                """
            )
            connection.execute(
                """
                insert into chat_turns (
                  id,
                  session_id,
                  tenant_id,
                  user_id,
                  request_text,
                  response_text,
                  status,
                  is_internal
                )
                values
                  (
                    'turn_tenant_default_1',
                    'session_tenant_default',
                    'tenant_default',
                    'tenant_user',
                    'Question 1',
                    'Answer 1',
                    'completed',
                    false
                  ),
                  (
                    'turn_tenant_default_2',
                    'session_tenant_default',
                    'tenant_default',
                    'tenant_user',
                    'Question 2',
                    'Answer 2',
                    'completed',
                    false
                  )
                """
            )
            connection.commit()

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": "platform-admin@example.com", "password": "admin-secret"},
        )
        assert admin_login.status_code == 200
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

        listed = client.get(
            "/api/v1/tenants",
            headers=admin_headers,
            params={
                "search": "default",
                "type": "personal",
                "subscriptionType": "monthly",
                "subscriptionStatus": "expiring_soon",
                "sort": "monthlyUsage",
                "page": 1,
                "pageSize": 10,
            },
        )
        assert listed.status_code == 200, listed.text
        body = listed.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["id"] == "tenant_default"
        assert item["type"] == "personal"
        assert item["ownerUserEmail"] == "tenant@example.com"
        assert item["currentSubscription"]["subscriptionId"] == "sub_tenant_default_pro"
        assert item["currentSubscription"]["status"] == "expiring_soon"
        assert item["currentPlan"]["code"] == "pro"
        assert item["monthlyUsage"]["questionUsed"] == 2
        assert item["monthlyUsage"]["questionLimit"] == 100
        assert item["monthlyUsage"]["tokenUsed"] == 0
        assert item["monthlyUsage"]["tokenLimit"] == 50000
        assert item["orderSummary"] == {
            "totalAmountCents": 0,
            "orderCount": 0,
            "recentOrders": [],
        }

        detail = client.get("/api/v1/tenants/tenant_default", headers=admin_headers)
        assert detail.status_code == 200
        detail_body = detail.json()
        assert detail_body["members"] == []

        blocked = client.post(
            "/api/v1/tenants/tenant_default/members",
            headers=admin_headers,
            json={"userId": "platform_admin", "role": "member"},
        )
        assert blocked.status_code == 409

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
                "groupId": "expert_group_basic",
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
        assert expert["groupId"] == "expert_group_basic"
        assert expert["groupName"] == "基础专家组"
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
                "groupId": "expert_group_professional",
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
        assert patched_body["groupId"] == "expert_group_professional"
        assert patched_body["groupName"] == "专业专家组"
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
        assert after_soft_delete.json()["groupId"] == "expert_group_professional"

        with open_database_connection(settings) as connection:
            group_links = connection.execute(
                """
                select group_id from expert_group_members
                where expert_id = ?
                order by group_id
                """,
                (expert_id,),
            ).fetchall()
        assert [row["group_id"] for row in group_links] == ["expert_group_professional"]

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

        missing_group = client.post(
            "/api/v1/experts",
            headers=admin_headers,
            json={
                "name": "Broken Group Expert",
                "categoryId": "expert_cat_ops",
                "groupId": "missing_group",
                "abilityIntro": "Broken.",
            },
        )
        assert missing_group.status_code == 404

        too_many_kbs = client.post(
            "/api/v1/experts",
            headers=admin_headers,
            json={
                "name": "Multi KB Expert",
                "categoryId": "expert_cat_ops",
                "abilityIntro": "Broken.",
                "knowledgeBaseIds": ["kb_ops", "kb_growth"],
            },
        )
        assert too_many_kbs.status_code == 422

        too_many_kbs_patch = client.patch(
            f"/api/v1/experts/{expert_id}",
            headers=admin_headers,
            json={"knowledgeBaseIds": ["kb_ops", "kb_growth"]},
        )
        assert too_many_kbs_patch.status_code == 422
        assert missing_group.json()["code"] == "EXPERT_GROUP_NOT_FOUND"

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


def test_plan_phase1_admin_market_and_subscription_snapshot(tmp_path: Path) -> None:
    database_path = tmp_path / "plans.sqlite3"
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
        operator_login = client.post(
            "/api/v1/auth/login",
            json={"email": "operator@example.com", "password": "operator-secret"},
        )
        operator_headers = {"Authorization": f"Bearer {operator_login.json()['accessToken']}"}

        seeded = client.get("/api/v1/plans", headers=admin_headers)
        assert seeded.status_code == 200, seeded.text
        seeded_codes = [item["code"] for item in seeded.json()["items"]]
        assert seeded_codes[:4] == ["free", "pro", "max", "business"]
        free_plan = next(item for item in seeded.json()["items"] if item["code"] == "free")
        pro_plan = next(item for item in seeded.json()["items"] if item["code"] == "pro")
        assert free_plan["name"] == "免费版"
        assert free_plan["description"] == "入门级运营助手，适合首次体验专家问答能力。"
        assert free_plan["typeLabel"] == "免费版"
        assert free_plan["subtitle"] == "入门级运营助手"
        assert free_plan["badgeLabel"] == "入门体验"
        assert "基础专家问答" in free_plan["highlightItems"]
        assert pro_plan["name"] == "专业版"
        assert pro_plan["description"] == "进阶级效率专家，解锁更多专业专家和更高月度额度。"
        assert pro_plan["typeLabel"] == "个人付费"
        assert pro_plan["subtitle"] == "进阶级效率专家"
        assert pro_plan["badgeLabel"] == "最受欢迎"
        assert "深度评论拆解" in pro_plan["highlightItems"]
        assert pro_plan["upgradeRules"]["fromPlanIds"] == ["plan_free"]
        assert pro_plan["upgradeRules"]["selfServiceEnabled"] is True
        assert pro_plan["isRecommended"] is True

        operator_create = client.post(
            "/api/v1/plans",
            headers=operator_headers,
            json={
                "code": "operator-plan",
                "name": "Operator Plan",
                "level": 99,
                "description": "Forbidden",
            },
        )
        assert operator_create.status_code == 403

        missing_type = client.post(
            "/api/v1/plans",
            headers=admin_headers,
            json={
                "name": "Missing Type",
                "level": 6,
                "description": "Missing type label",
            },
        )
        assert missing_type.status_code == 400
        assert missing_type.json()["code"] == "PLAN_TYPE_LABEL_REQUIRED"

        unsupported_type = client.post(
            "/api/v1/plans",
            headers=admin_headers,
            json={
                "name": "Unsupported Type",
                "typeLabel": "未知类型",
                "level": 7,
                "description": "Unsupported type label",
            },
        )
        assert unsupported_type.status_code == 400
        assert unsupported_type.json()["code"] == "PLAN_TYPE_LABEL_UNSUPPORTED"

        invalid_level = client.post(
            "/api/v1/plans",
            headers=admin_headers,
            json={
                "name": "Invalid Level",
                "typeLabel": "个人付费",
                "level": 100,
                "description": "Out of range",
            },
        )
        assert invalid_level.status_code == 422

        invalid_sort = client.post(
            "/api/v1/plans",
            headers=admin_headers,
            json={
                "name": "Invalid Sort",
                "typeLabel": "个人付费",
                "level": 8,
                "description": "Out of range",
                "sortOrder": 10000,
            },
        )
        assert invalid_sort.status_code == 422

        created = client.post(
            "/api/v1/plans",
            headers=admin_headers,
            json={
                "name": "Team",
                "level": 5,
                "description": "Team plan",
                "typeLabel": "团队",
                "subtitle": "团队协作",
                "badgeLabel": "团队版",
                "highlightItems": ["多人协作", "组织管理"],
                "upgradeRules": {
                    "fromPlanIds": ["plan_pro"],
                    "toPlanIds": [],
                    "rules": ["联系销售"],
                    "selfServiceEnabled": False,
                },
                "isRecommended": True,
                "sortOrder": 50,
            },
        )
        assert created.status_code == 201, created.text
        plan = created.json()
        assert plan["code"] == "business_2"
        assert plan["typeLabel"] == "团队"
        assert plan["subtitle"] == "团队协作"
        assert plan["badgeLabel"] == "团队版"
        assert plan["highlightItems"] == ["多人协作", "组织管理"]
        assert plan["upgradeRules"]["rules"] == ["联系销售"]
        assert plan["isRecommended"] is True

        changed_type = client.patch(
            f"/api/v1/plans/{plan['id']}",
            headers=admin_headers,
            json={"typeLabel": "企业定制"},
        )
        assert changed_type.status_code == 200, changed_type.text
        plan = changed_type.json()
        assert plan["code"] == "enterprise"
        assert plan["typeLabel"] == "企业定制"

        with open_database_connection(settings) as connection:
            connection.execute(
                """
                insert into tenants (id, type, name, slug, status)
                values
                  ('plan_sub_tenant_1', 'personal', 'Plan Sub Tenant 1', 'plan-sub-tenant-1', 'active'),
                  ('plan_sub_tenant_2', 'personal', 'Plan Sub Tenant 2', 'plan-sub-tenant-2', 'active'),
                  ('plan_sub_tenant_cancelled', 'personal', 'Plan Sub Cancelled', 'plan-sub-cancelled', 'active')
                """
            )
            connection.execute(
                """
                insert into tenant_subscriptions (
                  id,
                  tenant_id,
                  plan_id,
                  status,
                  billing_period,
                  current_period_start,
                  current_period_end,
                  cancel_at_period_end
                )
                values
                  (
                    'plan_sub_active_1',
                    'plan_sub_tenant_1',
                    'plan_pro',
                    'active',
                    'monthly',
                    CURRENT_TIMESTAMP,
                    datetime('now', '+30 days'),
                    false
                  ),
                  (
                    'plan_sub_trialing_2',
                    'plan_sub_tenant_2',
                    'plan_pro',
                    'trialing',
                    'monthly',
                    CURRENT_TIMESTAMP,
                    datetime('now', '+14 days'),
                    false
                  ),
                  (
                    'plan_sub_cancelled_ignored',
                    'plan_sub_tenant_cancelled',
                    'plan_pro',
                    'cancelled',
                    'monthly',
                    CURRENT_TIMESTAMP,
                    datetime('now', '+30 days'),
                    false
                  )
                """
            )
            connection.commit()

        after_recommend = client.get("/api/v1/plans", headers=admin_headers)
        by_code = {item["code"]: item for item in after_recommend.json()["items"]}
        assert by_code["pro"]["isRecommended"] is False
        assert by_code["pro"]["subscriptionCount"] == 2
        assert by_code["enterprise"]["isRecommended"] is True

        pro_detail = client.get("/api/v1/plans/plan_pro", headers=admin_headers)
        assert pro_detail.status_code == 200
        assert pro_detail.json()["subscriptionCount"] == 2

        priced = client.put(
            f"/api/v1/plans/{plan['id']}/prices",
            headers=admin_headers,
            json={
                "items": [
                    {
                        "billingPeriod": "monthly",
                        "currency": "CNY",
                        "amountCents": 49900,
                        "isEnabled": True,
                    }
                ]
            },
        )
        assert priced.status_code == 200, priced.text
        assert priced.json()["prices"][0]["amountCents"] == 49900

        entitled = client.put(
            f"/api/v1/plans/{plan['id']}/entitlements",
            headers=admin_headers,
            json={
                "monthlyQuestionLimit": 2000,
                "monthlyTokenLimit": 3000000,
                "seatLimit": 3,
                "modelTiers": ["core", "enhanced"],
                "features": {"teamManagement": True},
            },
        )
        assert entitled.status_code == 200, entitled.text
        assert entitled.json()["entitlements"]["seatLimit"] == 3

        group = client.post(
            "/api/v1/expert-groups",
            headers=admin_headers,
            json={
                "code": "team_group",
                "name": "Team Group",
                "description": "Team experts",
                "sortOrder": 55,
            },
        )
        assert group.status_code == 201, group.text
        group_body = group.json()

        with open_database_connection(settings) as connection:
            connection.execute(
                """
                insert into expert_categories (id, name, description)
                values ('expert_cat_plan', 'Plan Category', null)
                """
            )
            connection.execute(
                """
                insert into experts (id, category_id, name, ability_intro, status)
                values ('expert_plan', 'expert_cat_plan', 'Plan Expert', 'Plan helper.', 'draft')
                """
            )
            connection.commit()

        members = client.put(
            f"/api/v1/expert-groups/{group_body['id']}/experts",
            headers=admin_headers,
            json={"expertIds": ["expert_plan"]},
        )
        assert members.status_code == 200, members.text
        assert members.json()["expertIds"] == ["expert_plan"]

        assigned = client.put(
            f"/api/v1/plans/{plan['id']}/expert-groups",
            headers=admin_headers,
            json={"groupIds": [group_body["id"]]},
        )
        assert assigned.status_code == 200, assigned.text
        assert assigned.json()["expertGroups"][0]["code"] == "team_group"

        delete_used_group = client.delete(
            f"/api/v1/expert-groups/{group_body['id']}", headers=admin_headers
        )
        assert delete_used_group.status_code == 409

        hidden = client.patch(
            f"/api/v1/plans/{plan['id']}",
            headers=admin_headers,
            json={"status": "disabled"},
        )
        assert hidden.status_code == 200
        market = client.get("/api/v1/plan-market/plans", headers=operator_headers)
        assert market.status_code == 200
        assert "team" not in [item["code"] for item in market.json()["items"]]

        tenant_register = client.post(
            "/api/v1/users/register",
            json={"email": "tenant@example.com", "password": "secret123", "name": "Tenant User"},
        )
        assert tenant_register.status_code == 201
        tenant_headers = {"Authorization": f"Bearer {tenant_register.json()['accessToken']}"}

        current = client.get("/api/v1/plan-market/current-subscription", headers=tenant_headers)
        assert current.status_code == 200, current.text
        body = current.json()
        assert body["subscription"]["planId"] == free_plan["id"]
        assert body["snapshot"]["planCode"] == "free"
        assert body["snapshot"]["planName"] == "免费版"
        assert body["snapshot"]["entitlementsSnapshot"]["monthlyQuestionLimit"] == 100
        assert body["snapshot"]["entitlementsSnapshot"]["expertGroups"][0]["code"] == "basic"

        client.put(
            f"/api/v1/plans/{free_plan['id']}/entitlements",
            headers=admin_headers,
            json={
                "monthlyQuestionLimit": 999,
                "monthlyTokenLimit": 999,
                "seatLimit": 1,
                "modelTiers": ["core"],
                "features": {},
            },
        )
        unchanged = client.get(
            "/api/v1/plan-market/current-subscription", headers=tenant_headers
        )
        assert unchanged.status_code == 200
        assert unchanged.json()["snapshot"]["entitlementsSnapshot"]["monthlyQuestionLimit"] == 100

        delete_free = client.delete(f"/api/v1/plans/{free_plan['id']}", headers=admin_headers)
        assert delete_free.status_code == 409


def test_expert_market_requires_sign_in_and_only_lists_published_experts(tmp_path: Path) -> None:
    database_path = tmp_path / "expert_market.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )
    test_app = create_app(settings)

    with TestClient(test_app) as client:
        _seed_platform_user(
            settings, "market_user", "market@example.com", "Market User", "market-secret", "operator"
        )

        # Anonymous callers are rejected -- the marketplace is sign-in gated, not public.
        assert client.get("/api/v1/expert-market/categories").status_code == 401
        assert client.get("/api/v1/expert-market/experts").status_code == 401
        assert client.get("/api/v1/expert-market/experts/expert_listing").status_code == 401

        login = client.post(
            "/api/v1/auth/login",
            json={"email": "market@example.com", "password": "market-secret"},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

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

        categories = client.get("/api/v1/expert-market/categories", headers=headers)
        assert categories.status_code == 200
        assert categories.json()["items"] == [
            {
                "id": "expert_cat_ops",
                "name": "Operations",
                "description": "Operations experts",
            }
        ]

        experts = client.get("/api/v1/expert-market/experts", headers=headers)
        assert experts.status_code == 200
        assert [item["id"] for item in experts.json()["items"]] == ["expert_listing"]

        by_category = client.get(
            "/api/v1/expert-market/experts",
            params={"categoryId": "expert_cat_ads"},
            headers=headers,
        )
        assert by_category.status_code == 200
        assert by_category.json()["items"] == []

        detail = client.get("/api/v1/expert-market/experts/expert_listing", headers=headers)
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

        hidden = client.get("/api/v1/expert-market/experts/expert_store", headers=headers)
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


def test_chat_acp_backend_creates_locally_and_translates_turn(tmp_path: Path) -> None:
    database_path = tmp_path / "chat_acp.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
        acp_gateway_base_url="http://gateway.test",
        acp_route_prefix="/acp",
        acp_default_cwd=str(tmp_path / "acp-workspace"),
    )
    fake_acp = FakeAcpGatewayClient()
    test_app = create_app(settings)
    test_app.dependency_overrides[get_acp_gateway_client] = lambda: fake_acp

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
            json={"title": "ACP Test"},
        )
        assert created.status_code == 201
        session_id = created.json()["id"]
        # The ACP backend mints the thread id locally; no upstream create call is made.
        assert session_id.startswith("thread_")

        turn = client.post(
            f"/api/v1/chat/sessions/{session_id}/turns",
            headers=headers,
            json={"question": "hello"},
        )
        assert turn.status_code == 200
        # ACP session/delta/done events are translated to the public public contract.
        assert "event: turn_started" in turn.text
        assert "event: message_delta" in turn.text
        assert "event: turn_completed" in turn.text
        assert "event: session" not in turn.text

        first_call = fake_acp.turn_calls[0]
        assert first_call["thread_id"] == session_id
        assert first_call["session_id"] is None  # first turn has no id to resume
        assert first_call["cwd"] == fake_acp.default_cwd
        assert first_call["input"] == "hello"
        assert first_call.get("config_overrides") is None

        messages = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=headers)
        assert messages.status_code == 200
        assert messages.json()["items"][0]["responseText"] == "ok"

        # A follow-up turn echoes back the agent-assigned ACP session id to resume the instance.
        client.post(
            f"/api/v1/chat/sessions/{session_id}/turns",
            headers=headers,
            json={"question": "again"},
        )
        assert fake_acp.turn_calls[1]["session_id"] == "acp_sess_1"


def test_chat_acp_backend_translates_reasoning_and_tool_call(tmp_path: Path) -> None:
    database_path = tmp_path / "chat_acp_reasoning.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
        acp_gateway_base_url="http://gateway.test",
        acp_route_prefix="/acp",
        acp_default_cwd=str(tmp_path / "acp-workspace"),
    )
    fake_acp = FakeAcpReasoningGatewayClient()
    test_app = create_app(settings)
    test_app.dependency_overrides[get_acp_gateway_client] = lambda: fake_acp

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

        session_id = client.post(
            "/api/v1/chat/sessions",
            headers=headers,
            json={"title": "ACP Reasoning"},
        ).json()["id"]

        turn = client.post(
            f"/api/v1/chat/sessions/{session_id}/turns",
            headers=headers,
            json={"question": "hello"},
        )

        assert turn.status_code == 200
        assert "event: reasoning_delta" in turn.text
        assert "thinking" in turn.text
        assert "[tool] search" in turn.text
        assert turn.text.index("event: reasoning_delta") < turn.text.index("event: message_delta")

        messages = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=headers)
        assert messages.status_code == 200
        item = messages.json()["items"][0]
        assert "thinking" in item["reasoningText"]
        assert "[tool] search" in item["reasoningText"]
        assert item["responseText"] == "final answer"


def test_chat_acp_transcript_replays_from_route_api(tmp_path: Path) -> None:
    database_path = tmp_path / "chat_acp_transcript.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
        acp_gateway_base_url="http://gateway.test",
        acp_default_cwd=str(tmp_path / "acp-workspace"),
    )
    fake_acp = FakeAcpGatewayClient()
    test_app = create_app(settings)
    test_app.dependency_overrides[get_acp_gateway_client] = lambda: fake_acp

    with TestClient(test_app) as client:
        _seed_tenant(settings)
        _seed_tenant_user(
            settings, "tenant_user", "tenant@example.com", "Tenant User", "tenant-secret", "member"
        )
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "tenant@example.com", "password": "tenant-secret", "tenantId": "tenant_default"},
        )
        headers = {
            "Authorization": f"Bearer {login.json()['accessToken']}",
            "x-tenant-id": "tenant_default",
        }

        session_id = client.post(
            "/api/v1/chat/sessions", headers=headers, json={"title": "Replay"}
        ).json()["id"]

        # Before any turn there is no ACP session, so replay falls back to the local record.
        empty = client.get(f"/api/v1/chat/sessions/{session_id}/transcript", headers=headers)
        assert empty.status_code == 200
        assert empty.json() == {"sessionId": session_id, "messages": [], "source": "local"}

        # Run a turn so the agent-assigned session id is captured and persisted.
        client.post(
            f"/api/v1/chat/sessions/{session_id}/turns", headers=headers, json={"question": "hello"}
        )

        transcript = client.get(f"/api/v1/chat/sessions/{session_id}/transcript", headers=headers)
        assert transcript.status_code == 200
        body = transcript.json()
        assert body["source"] == "agent"
        assert body["sessionId"] == session_id
        assert body["messages"] == [
            {"role": "user", "text": "hello"},
            {"role": "assistant", "text": "ok"},
        ]
        # The route API is addressed by the agent session id + the tenant cwd, not the thread id.
        assert fake_acp.transcript_calls[-1]["session_id"] == "acp_sess_1"
        assert fake_acp.transcript_calls[-1]["cwd"] == fake_acp.default_cwd


def _login_tenant_member(client: TestClient, settings: Settings) -> dict[str, str]:
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
    return {
        "Authorization": f"Bearer {login.json()['accessToken']}",
        "x-tenant-id": "tenant_default",
    }


def test_chat_acp_auto_title_via_session_info_event(tmp_path: Path) -> None:
    # The live `session_info` SSE path, for agents like opencode that DO emit session_info_update.
    # The session list returns no title for this fake, so the title can only come from the stream event.
    database_path = tmp_path / "chat_acp_title.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
        acp_gateway_base_url="http://gateway.test",
        acp_route_prefix="/acp",
        acp_default_cwd=str(tmp_path / "acp-workspace"),
    )
    fake_acp = FakeAcpTitleGatewayClient()
    test_app = create_app(settings)
    test_app.dependency_overrides[get_acp_gateway_client] = lambda: fake_acp

    with TestClient(test_app) as client:
        headers = _login_tenant_member(client, settings)

        # Create with a preset title: the agent's nested session_info title must not clobber it.
        preset = client.post(
            "/api/v1/chat/sessions", headers=headers, json={"title": "Preset"}
        )
        assert preset.status_code == 201
        preset_id = preset.json()["id"]
        turn_preset = client.post(
            f"/api/v1/chat/sessions/{preset_id}/turns",
            headers=headers,
            json={"question": "hello"},
        )
        assert "event: session_title_updated" not in turn_preset.text
        assert (
            client.get(f"/api/v1/chat/sessions/{preset_id}", headers=headers).json()["title"]
            == "Preset"
        )

        # Create without a title: the nested ACP session_info title fills it and emits a frame.
        created = client.post("/api/v1/chat/sessions", headers=headers, json={})
        session_id = created.json()["id"]
        turn = client.post(
            f"/api/v1/chat/sessions/{session_id}/turns",
            headers=headers,
            json={"question": "hello"},
        )
        assert "event: session_title_updated" in turn.text
        assert "Auto 2" in turn.text  # second stream_turn call on this fake
        assert (
            client.get(f"/api/v1/chat/sessions/{session_id}", headers=headers).json()["title"]
            == "Auto 2"
        )


def test_chat_acp_auto_title_from_route_session_list(tmp_path: Path) -> None:
    # The codex-acp path: the gateway emits no session_info, so the title is reconciled from the
    # route-scoped session list after the turn, keyed by the bound acp_session_id.
    database_path = tmp_path / "chat_acp_title_list.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
        acp_gateway_base_url="http://gateway.test",
        acp_route_prefix="/acp",
        acp_default_cwd=str(tmp_path / "acp-workspace"),
    )
    fake_acp = FakeAcpTitleListGatewayClient()  # streams session/delta/done, title via session/list
    test_app = create_app(settings)
    test_app.dependency_overrides[get_acp_gateway_client] = lambda: fake_acp

    with TestClient(test_app) as client:
        headers = _login_tenant_member(client, settings)

        # Empty title: reconciled from session/list after the turn binds the acp_session_id.
        session_id = client.post("/api/v1/chat/sessions", headers=headers, json={}).json()["id"]
        turn = client.post(
            f"/api/v1/chat/sessions/{session_id}/turns", headers=headers, json={"question": "hi"}
        )
        assert "event: session_title_updated" in turn.text
        assert "Codex Title" in turn.text
        assert (
            client.get(f"/api/v1/chat/sessions/{session_id}", headers=headers).json()["title"]
            == "Codex Title"
        )
        assert fake_acp.list_calls  # the route session list was consulted
        # Lookup is keyed by the agent session id + tenant cwd, not the local thread id.
        assert fake_acp.list_calls[-1]["cwd"] == fake_acp.default_cwd

        # Preset title: reconciliation is short-circuited -- no session list lookup, no clobber.
        calls_before = len(fake_acp.list_calls)
        preset_id = client.post(
            "/api/v1/chat/sessions", headers=headers, json={"title": "Preset"}
        ).json()["id"]
        preset_turn = client.post(
            f"/api/v1/chat/sessions/{preset_id}/turns", headers=headers, json={"question": "hi"}
        )
        assert "event: session_title_updated" not in preset_turn.text
        assert (
            client.get(f"/api/v1/chat/sessions/{preset_id}", headers=headers).json()["title"]
            == "Preset"
        )
        assert len(fake_acp.list_calls) == calls_before  # skipped while the title is non-empty


def test_chat_sessions_can_be_listed_by_archive_status(tmp_path: Path) -> None:
    database_path = tmp_path / "chat_archive.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
        acp_gateway_base_url="http://gateway.test",
        acp_route_prefix="/acp",
        acp_default_cwd=str(tmp_path / "acp-workspace"),
    )
    fake_acp = FakeAcpGatewayClient()
    test_app = create_app(settings)
    test_app.dependency_overrides[get_acp_gateway_client] = lambda: fake_acp

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
            json={"title": "Archive Test"},
        )
        assert created.status_code == 201
        session_id = created.json()["id"]
        assert created.json()["status"] == "active"

        archived = client.patch(
            f"/api/v1/chat/sessions/{session_id}/archive",
            headers=headers,
            json={"archived": True},
        )
        assert archived.status_code == 200
        assert archived.json()["status"] == "archived"

        active_list = client.get("/api/v1/chat/sessions", headers=headers)
        assert active_list.status_code == 200
        assert active_list.json()["items"] == []

        archived_list = client.get(
            "/api/v1/chat/sessions",
            headers=headers,
            params={"status": "archived"},
        )
        assert archived_list.status_code == 200
        assert [item["id"] for item in archived_list.json()["items"]] == [session_id]

        restored = client.patch(
            f"/api/v1/chat/sessions/{session_id}/archive",
            headers=headers,
            json={"archived": False},
        )
        assert restored.status_code == 200
        assert restored.json()["status"] == "active"

        active_list = client.get("/api/v1/chat/sessions", headers=headers)
        assert active_list.status_code == 200
        assert [item["id"] for item in active_list.json()["items"]] == [session_id]


def test_chat_session_delete_is_soft_delete(tmp_path: Path) -> None:
    database_path = tmp_path / "chat_soft_delete.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
        acp_gateway_base_url="http://gateway.test",
        acp_route_prefix="/acp",
        acp_default_cwd=str(tmp_path / "acp-workspace"),
    )
    fake_acp = FakeAcpGatewayClient()
    test_app = create_app(settings)
    test_app.dependency_overrides[get_acp_gateway_client] = lambda: fake_acp

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
            json={"title": "Soft Delete Test"},
        )
        assert created.status_code == 201
        session_id = created.json()["id"]

        turn = client.post(
            f"/api/v1/chat/sessions/{session_id}/turns",
            headers=headers,
            json={"question": "hello"},
        )
        assert turn.status_code == 200

        deleted = client.delete(f"/api/v1/chat/sessions/{session_id}", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json() == {"id": session_id, "status": "deleted"}

        listed = client.get("/api/v1/chat/sessions", headers=headers)
        assert listed.status_code == 200
        assert listed.json()["items"] == []
        assert client.get(f"/api/v1/chat/sessions/{session_id}", headers=headers).status_code == 404
        assert (
            client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=headers).status_code
            == 404
        )

    with open_database_connection(settings) as connection:
        session = connection.execute(
            "select deleted_at from chat_sessions where id = ?",
            (session_id,),
        ).fetchone()
        turns = connection.execute(
            "select count(*) as count from chat_turns where session_id = ?",
            (session_id,),
        ).fetchone()

    assert session is not None
    assert session["deleted_at"] is not None
    assert turns["count"] == 1


def test_chat_acp_backend_retries_when_resume_session_is_stale(tmp_path: Path) -> None:
    database_path = tmp_path / "chat_acp_stale_session.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
        acp_gateway_base_url="http://gateway.test",
        acp_route_prefix="/acp",
        acp_default_cwd=str(tmp_path / "acp-workspace"),
    )
    fake_acp = FakeAcpGatewayClient()
    test_app = create_app(settings)
    test_app.dependency_overrides[get_acp_gateway_client] = lambda: fake_acp

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
        headers = {
            "Authorization": f"Bearer {login.json()['accessToken']}",
            "x-tenant-id": "tenant_default",
        }
        created = client.post(
            "/api/v1/chat/sessions",
            headers=headers,
            json={"title": "ACP stale session"},
        )
        session_id = created.json()["id"]
        first_turn = client.post(
            f"/api/v1/chat/sessions/{session_id}/turns",
            headers=headers,
            json={"question": "hello"},
        )
        assert first_turn.status_code == 200

        fake_acp.fail_next_resume = True
        resumed_turn = client.post(
            f"/api/v1/chat/sessions/{session_id}/turns",
            headers=headers,
            json={"question": "after restart"},
        )

        assert resumed_turn.status_code == 200
        assert "network error" not in resumed_turn.text
        assert "event: message_delta" in resumed_turn.text
        assert "event: turn_completed" in resumed_turn.text
        assert fake_acp.turn_calls[1]["session_id"] == "acp_sess_1"
        assert fake_acp.turn_calls[2]["session_id"] is None
        assert fake_acp.turn_calls[2]["fresh_session"] is True

        messages = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=headers)
        assert messages.status_code == 200
        items = messages.json()["items"]
        assert items[-1]["status"] == "completed"
        assert items[-1]["responseText"] == "ok"
        assert items[-1]["errorMessage"] is None


def test_acp_gateway_preserves_remote_posix_cwd() -> None:
    client = AcpGatewayClient(Settings(acp_default_cwd="/usr/local/acp-workspace"))

    assert client.prepare_cwd("tenant_default") == "/usr/local/acp-workspace"

    tenant_client = AcpGatewayClient(
        Settings(
            acp_default_cwd="/unused",
            acp_cwd_base="/usr/local/acp-workspace/tenants",
        )
    )
    assert (
        tenant_client.prepare_cwd("tenant_default")
        == "/usr/local/acp-workspace/tenants/tenant_default"
    )


def test_acp_gateway_prepare_cwd_creates_per_tenant_dir(tmp_path: Path) -> None:
    # The agent chdirs into cwd, so the per-tenant subdir under an absolute base must be created
    # (regression: an absolute cwd_base used to return early without mkdir, breaking codex chdir).
    base = tmp_path / "acp-roots"
    client = AcpGatewayClient(Settings(acp_default_cwd="/unused", acp_cwd_base=str(base)))

    cwd = client.prepare_cwd("tenant_default")

    assert cwd == str(base / "tenant_default")
    assert (base / "tenant_default").is_dir()


def test_acp_stream_turn_builds_turn_request_payload() -> None:
    client = AcpGatewayClient(
        Settings(
            acp_gateway_base_url="http://gateway.test",
            acp_route_prefix="/acp",
            acp_default_model="claude-opus",
        )
    )
    captured: dict = {}

    def fake_stream(method, path, *, tenant_id=None, **kwargs):
        captured.update(method=method, path=path, tenant_id=tenant_id, json=kwargs.get("json"))

        async def empty():
            return
            yield  # pragma: no cover - marks this an async generator

        return empty()

    client.stream = fake_stream  # type: ignore[assignment]

    async def drive() -> None:
        agen = client.stream_turn(
            thread_id="thread_1",
            input="hello",
            tenant_id="tenant_default",
            session_id="",  # falsy -> omitted, lets the agent assign one on the first turn
            config_overrides={"thought_level": "medium"},
        )
        async for _ in agen:
            pass

    asyncio.run(drive())

    assert captured["method"] == "POST"
    assert captured["path"] == "/acp/turn"
    assert captured["tenant_id"] == "tenant_default"
    # Required fields plus the default model; empty optionals (session_id, cwd,
    # fresh_session) are omitted so the gateway falls back to service defaults.
    assert captured["json"] == {
        "thread_id": "thread_1",
        "input": "hello",
        "model": "claude-opus",
        "config_overrides": {"thought_level": "medium"},
    }


def test_acp_resolve_permission_sends_request_id_in_body() -> None:
    client = AcpGatewayClient(
        Settings(acp_gateway_base_url="http://gateway.test", acp_route_prefix="/acp")
    )
    captured: dict = {}

    async def fake_request(method, path, *, tenant_id=None, **kwargs):
        captured.update(method=method, path=path, tenant_id=tenant_id, json=kwargs.get("json"))
        return {"status": "resolved"}

    client.request = fake_request  # type: ignore[assignment]

    result = asyncio.run(
        client.resolve_permission(
            request_id="req_1",
            outcome="selected",
            option_id="allow",
            tenant_id="tenant_default",
        )
    )

    assert result == {"status": "resolved"}
    assert captured["method"] == "POST"
    assert captured["path"] == "/acp/permission"
    assert captured["json"] == {
        "request_id": "req_1",
        "outcome": "selected",
        "option_id": "allow",
    }


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


class FakeAcpGatewayClient:
    def __init__(self) -> None:
        self.default_model = "claude-opus"
        self.default_cwd = "/tmp/acp"
        self.turn_calls: list[dict] = []
        self.transcript_calls: list[dict] = []
        self.list_calls: list[dict] = []
        self.fail_next_resume = False

    def prepare_cwd(self, tenant_id: str | None = None) -> str:
        return self.default_cwd

    async def get_transcript(
        self, *, session_id: str, tenant_id: str | None = None, cwd: str | None = None
    ) -> dict:
        self.transcript_calls.append(
            {"session_id": session_id, "tenant_id": tenant_id, "cwd": cwd}
        )
        return {
            "session_id": session_id,
            "messages": [
                {"role": "user", "text": "hello"},
                {"role": "assistant", "text": "ok"},
            ],
        }

    async def list_sessions(
        self, *, tenant_id: str | None = None, cwd: str | None = None, cursor: str | None = None
    ) -> dict:
        self.list_calls.append({"tenant_id": tenant_id, "cwd": cwd, "cursor": cursor})
        return {"sessions": [], "next_cursor": ""}

    def stream_turn(
        self,
        *,
        thread_id: str,
        input: str,
        tenant_id: str | None = None,
        session_id: str | None = None,
        cwd: str | None = None,
        model: str | None = None,
        fresh_session: bool = False,
        config_overrides: dict | None = None,
    ):
        self.turn_calls.append(
            {
                "thread_id": thread_id,
                "input": input,
                "tenant_id": tenant_id,
                "session_id": session_id,
                "cwd": cwd,
                "fresh_session": fresh_session,
                "config_overrides": config_overrides,
            }
        )

        async def gen():
            if self.fail_next_resume and session_id:
                self.fail_next_resume = False
                yield "event: error"
                yield 'data: {"message": "network error"}'
                yield ""
                return
            yield "event: session"
            yield 'data: {"session_id": "acp_sess_1"}'
            yield ""
            yield "event: delta"
            yield 'data: {"text": "ok"}'
            yield ""
            yield "event: done"
            yield 'data: {"stop_reason": "end_turn"}'
            yield ""

        return gen()


class FakeAcpReasoningGatewayClient(FakeAcpGatewayClient):
    def stream_turn(
        self,
        *,
        thread_id: str,
        input: str,
        tenant_id: str | None = None,
        session_id: str | None = None,
        cwd: str | None = None,
        model: str | None = None,
        fresh_session: bool = False,
        config_overrides: dict | None = None,
    ):
        self.turn_calls.append(
            {
                "thread_id": thread_id,
                "input": input,
                "tenant_id": tenant_id,
                "session_id": session_id,
                "cwd": cwd,
                "fresh_session": fresh_session,
                "config_overrides": config_overrides,
            }
        )

        async def gen():
            yield "event: session"
            yield 'data: {"session_id": "acp_sess_1"}'
            yield ""
            yield "event: reasoning"
            yield 'data: {"text": "thinking"}'
            yield ""
            yield "event: tool_call"
            yield 'data: {"data": {"name": "search", "input": {"q": "hello"}}}'
            yield ""
            yield "event: delta"
            yield 'data: {"text": "final answer"}'
            yield ""
            yield "event: done"
            yield 'data: {"stop_reason": "end_turn"}'
            yield ""

        return gen()


class FakeAcpTitleGatewayClient(FakeAcpGatewayClient):
    """ACP gateway fake whose turn stream carries a per-turn auto-generated session title.

    The gateway wraps the raw ACP update under `data`, so the title is nested at
    `data.data.title` -- the shape the handler must dig through.
    """

    def __init__(self) -> None:
        super().__init__()
        self._turn = 0

    def stream_turn(self, **kwargs):
        self.turn_calls.append(
            {
                "thread_id": kwargs.get("thread_id"),
                "input": kwargs.get("input"),
                "tenant_id": kwargs.get("tenant_id"),
                "session_id": kwargs.get("session_id"),
                "cwd": kwargs.get("cwd"),
                "config_overrides": kwargs.get("config_overrides"),
            }
        )
        self._turn += 1
        title = f"Auto {self._turn}"

        async def gen():
            yield "event: session"
            yield 'data: {"session_id": "acp_sess_1"}'
            yield ""
            yield "event: session_info"
            yield (
                'data: {"data": {"sessionUpdate": "session_info_update", '
                f'"title": "{title}"}}}}'
            )
            yield ""
            yield "event: delta"
            yield 'data: {"text": "ok"}'
            yield ""
            yield "event: done"
            yield 'data: {"stop_reason": "end_turn"}'
            yield ""

        return gen()


class FakeAcpTitleListGatewayClient(FakeAcpGatewayClient):
    """ACP gateway fake whose route-scoped session/list carries the codex-derived title.

    codex-acp never emits `session_info_update`, so its title is only reachable through the
    route-scoped session list, keyed by the agent-assigned ACP session id. The turn stream from
    the base fake emits session/delta/done with no session_info.
    """

    async def list_sessions(
        self, *, tenant_id: str | None = None, cwd: str | None = None, cursor: str | None = None
    ) -> dict:
        self.list_calls.append({"tenant_id": tenant_id, "cwd": cwd, "cursor": cursor})
        return {
            "sessions": [{"session_id": "acp_sess_1", "title": "Codex Title", "cwd": cwd}],
            "next_cursor": "",
        }


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
        self.contents: dict[str, bytes] = {}
        self.removed: list[str] = []
        self.fail_remove: set[str] = set()

    @property
    def bucket(self) -> str:
        return self._bucket

    def presigned_put_url(self, object_key, *, expires, content_type=None) -> str:
        return f"https://minio.test/{self._bucket}/{object_key}?put"

    def presigned_get_url(self, object_key, *, expires, response_headers=None) -> str:
        suffix = "?get"
        if response_headers:
            suffix += "&" + "&".join(f"{key}={value}" for key, value in response_headers.items())
        return f"https://minio.test/{self._bucket}/{object_key}{suffix}"

    def stat(self, object_key: str) -> ObjectStat:
        if object_key not in self.objects:
            from app.core.errors import ApiError

            raise ApiError(404, "DOC_OBJECT_NOT_FOUND", "Uploaded object not found")
        return ObjectStat(size=self.objects[object_key], etag="fake-md5")

    def put(self, object_key: str, data: bytes | int, *, content_type=None) -> None:
        if isinstance(data, bytes):
            self.objects[object_key] = len(data)
            self.contents[object_key] = data
            return
        self.objects[object_key] = data
        self.contents[object_key] = b"\x00" * data

    def read(self, object_key: str, *, max_bytes=None) -> bytes:
        if object_key not in self.contents:
            from app.core.errors import ApiError

            raise ApiError(404, "DOC_OBJECT_NOT_FOUND", "Object not found")
        data = self.contents[object_key]
        if max_bytes is not None and len(data) > max_bytes:
            from app.core.errors import ApiError

            raise ApiError(413, "OBJECT_TOO_LARGE", "Object is too large to read inline")
        return data

    def remove(self, object_key: str) -> None:
        if object_key in self.fail_remove:
            raise RuntimeError("remove failed")
        self.removed.append(object_key)
        self.objects.pop(object_key, None)
        self.contents.pop(object_key, None)


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
        results = url_resp.json()["items"]
        assert len(results) == 2
        assert [r["status"] for r in results] == ["created", "created"]
        assert all(r["method"] == "PUT" for r in results)
        assert all(r["uploadUrl"] for r in results)
        assert all(r["uploadSessionId"] for r in results)
        uploads = [r["upload"] for r in results]
        assert results[0]["uploadUrl"] == uploads[0]["uploadUrl"]
        assert results[0]["uploadSessionId"] == uploads[0]["uploadSessionId"]

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
        assert completed.status_code == 200, completed.text
        items = completed.json()["items"]
        assert [item["status"] for item in items] == ["completed", "completed"]
        assert {item["document"]["fileName"] for item in items} == {"guide.pdf", "notes.txt"}

        listed = client.get(f"/api/v1/knowledge-bases/{kb_id}/docs", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 2


def test_complete_uploads_is_non_atomic_and_reports_per_item_failures(tmp_path: Path) -> None:
    settings = _kb_test_settings(tmp_path)
    store = FakeObjectStore()
    with TestClient(_kb_app(settings, store)) as client:
        headers = _login(client, settings, "expert_user", "expert@example.com", "expert")
        kb_id = client.post(
            "/api/v1/knowledge-bases", headers=headers, json={"name": "Partial KB"}
        ).json()["id"]

        url_resp = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/upload-urls",
            headers=headers,
            json={"files": [{"fileName": "ok.pdf", "mimeType": "application/pdf", "fileSizeBytes": 8}]},
        )
        upload = url_resp.json()["items"][0]["upload"]
        store.put(upload["objectKey"], 8)

        # First item completes; second references an unknown session and must fail on its own
        # without aborting the first (the batch is non-atomic).
        completed = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/complete-uploads",
            headers=headers,
            json={
                "items": [
                    {"uploadSessionId": upload["uploadSessionId"], "fileSizeBytes": 8},
                    {"uploadSessionId": "upl_does_not_exist", "fileSizeBytes": 8},
                ]
            },
        )
        assert completed.status_code == 200, completed.text
        items = completed.json()["items"]
        assert items[0]["status"] == "completed"
        assert items[0]["document"]["fileName"] == "ok.pdf"
        assert items[1]["status"] == "failed"
        assert items[1]["error"]["code"] == "UPLOAD_SESSION_NOT_FOUND"

        # The successful item was committed even though a sibling failed.
        listed = client.get(f"/api/v1/knowledge-bases/{kb_id}/docs", headers=headers)
        assert [doc["fileName"] for doc in listed.json()["items"]] == ["ok.pdf"]


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


def test_upload_url_returns_503_when_object_store_unavailable(tmp_path: Path) -> None:
    settings = _kb_test_settings(tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        headers = _login(client, settings, "expert_user", "expert@example.com", "expert")
        kb_id = client.post(
            "/api/v1/knowledge-bases", headers=headers, json={"name": "KB"}
        ).json()["id"]

        response = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/docs/upload-url",
            headers=headers,
            json={"fileName": "a.txt", "fileSizeBytes": 32},
        )
        assert response.status_code == 503, response.text
        body = response.json()
        assert body["code"] == "OBJECT_STORE_UNAVAILABLE"
        assert "Object storage is unavailable" in body["message"]


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


def _library_test_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'library.sqlite3'}",
        default_tenant_id="tenant_default",
        jwt_secret="test-secret-with-at-least-32-bytes",
    )


def _library_headers(
    client: TestClient,
    settings: Settings,
    *,
    user_id: str,
    email: str,
) -> dict[str, str]:
    _seed_tenant_user(settings, user_id, email, f"{user_id} name", "secret-pass", "member")
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret-pass", "tenantId": "tenant_default"},
    )
    assert login.status_code == 200, login.text
    return {
        "Authorization": f"Bearer {login.json()['accessToken']}",
        "x-tenant-id": "tenant_default",
    }


def test_library_upload_list_preview_download_and_delete(tmp_path: Path) -> None:
    settings = _library_test_settings(tmp_path)
    store = FakeObjectStore()
    app = create_app(settings)
    app.dependency_overrides[get_object_store] = lambda: store

    with TestClient(app) as client:
        _seed_tenant(settings)
        headers = _library_headers(
            client,
            settings,
            user_id="tenant_user",
            email="tenant@example.com",
        )

        uploaded = client.post(
            "/api/v1/library/files",
            headers=headers,
            files={"file": ("notes.md", b"# Hello\nbody", "text/markdown")},
        )
        assert uploaded.status_code == 201, uploaded.text
        item = uploaded.json()
        assert item["name"] == "notes.md"
        assert item["type"] == "file"
        assert item["sizeBytes"] == 12
        assert item["previewSupported"] is True
        file_id = item["id"]

        object_key = next(iter(store.objects))
        assert object_key.startswith(f"library/tenant_default/users/tenant_user/{file_id}/")

        listed = client.get("/api/v1/library/files", headers=headers)
        assert listed.status_code == 200
        assert listed.json()["total"] == 1
        assert listed.json()["items"][0]["id"] == file_id

        preview = client.get(f"/api/v1/library/files/{file_id}/preview", headers=headers)
        assert preview.status_code == 200
        assert preview.json()["previewType"] == "text"
        assert preview.json()["content"] == "# Hello\nbody"

        download = client.get(f"/api/v1/library/files/{file_id}/download", headers=headers)
        assert download.status_code == 200
        assert download.json()["downloadUrl"].endswith("?get")

        deleted = client.delete(f"/api/v1/library/files/{file_id}", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json() == {"id": file_id, "status": "deleted"}
        assert client.get("/api/v1/library/files", headers=headers).json()["items"] == []
        assert client.get(f"/api/v1/library/files/{file_id}/download", headers=headers).status_code == 404

        with open_database_connection(settings) as connection:
            row = connection.execute(
                "select deleted_at from library_files where id = ?",
                (file_id,),
            ).fetchone()
        assert row is not None
        assert row["deleted_at"] is not None
        assert object_key not in store.removed


def test_library_files_are_isolated_by_current_user(tmp_path: Path) -> None:
    settings = _library_test_settings(tmp_path)
    store = FakeObjectStore()
    app = create_app(settings)
    app.dependency_overrides[get_object_store] = lambda: store

    with TestClient(app) as client:
        _seed_tenant(settings)
        alice = _library_headers(
            client,
            settings,
            user_id="alice",
            email="alice@example.com",
        )
        bob = _library_headers(
            client,
            settings,
            user_id="bob",
            email="bob@example.com",
        )

        uploaded = client.post(
            "/api/v1/library/files",
            headers=alice,
            files={"file": ("private.txt", b"secret", "text/plain")},
        )
        assert uploaded.status_code == 201, uploaded.text
        file_id = uploaded.json()["id"]

        assert client.get("/api/v1/library/files", headers=alice).json()["total"] == 1
        assert client.get("/api/v1/library/files", headers=bob).json()["total"] == 0
        assert client.get(f"/api/v1/library/files/{file_id}/download", headers=bob).status_code == 404
        assert client.delete(f"/api/v1/library/files/{file_id}", headers=bob).status_code == 404


def test_library_search_type_filter_and_image_preview_url(tmp_path: Path) -> None:
    settings = _library_test_settings(tmp_path)
    store = FakeObjectStore()
    app = create_app(settings)
    app.dependency_overrides[get_object_store] = lambda: store

    with TestClient(app) as client:
        _seed_tenant(settings)
        headers = _library_headers(
            client,
            settings,
            user_id="tenant_user",
            email="tenant@example.com",
        )

        image = client.post(
            "/api/v1/library/files",
            headers=headers,
            files={"file": ("chart.png", b"\x89PNG", "image/png")},
        )
        assert image.status_code == 201, image.text
        client.post(
            "/api/v1/library/files",
            headers=headers,
            files={"file": ("report.pdf", b"%PDF", "application/pdf")},
        )

        images = client.get("/api/v1/library/files", headers=headers, params={"type": "image"})
        assert images.status_code == 200
        assert [item["name"] for item in images.json()["items"]] == ["chart.png"]

        search = client.get("/api/v1/library/files", headers=headers, params={"keyword": "report"})
        assert search.status_code == 200
        assert [item["name"] for item in search.json()["items"]] == ["report.pdf"]

        preview = client.get(
            f"/api/v1/library/files/{image.json()['id']}/preview",
            headers=headers,
        )
        assert preview.status_code == 200
        assert preview.json()["previewType"] == "url"
        assert "?get" in preview.json()["url"]


def test_library_pdf_preview_returns_inline_pdf_url(tmp_path: Path) -> None:
    settings = _library_test_settings(tmp_path)
    store = FakeObjectStore()
    app = create_app(settings)
    app.dependency_overrides[get_object_store] = lambda: store

    with TestClient(app) as client:
        _seed_tenant(settings)
        headers = _library_headers(
            client,
            settings,
            user_id="tenant_user",
            email="tenant@example.com",
        )

        uploaded = client.post(
            "/api/v1/library/files",
            headers=headers,
            files={"file": ("report.pdf", b"%PDF-1.7", "application/pdf")},
        )
        assert uploaded.status_code == 201, uploaded.text
        item = uploaded.json()
        assert item["mimeType"] == "application/pdf"
        assert item["previewSupported"] is True

        listed = client.get("/api/v1/library/files", headers=headers)
        assert listed.status_code == 200
        assert listed.json()["items"][0]["previewSupported"] is True

        preview = client.get(f"/api/v1/library/files/{item['id']}/preview", headers=headers)
        assert preview.status_code == 200
        body = preview.json()
        assert body["previewType"] == "url"
        assert body["mimeType"] == "application/pdf"
        assert "response-content-type=application/pdf" in body["url"]
        assert "response-content-disposition=inline" in body["url"]
        assert "attachment" not in body["url"].lower()


def test_library_preview_supported_is_derived_from_file_type_not_db_flag(tmp_path: Path) -> None:
    settings = _library_test_settings(tmp_path)
    store = FakeObjectStore()
    app = create_app(settings)
    app.dependency_overrides[get_object_store] = lambda: store

    with TestClient(app) as client:
        _seed_tenant(settings)
        headers = _library_headers(
            client,
            settings,
            user_id="tenant_user",
            email="tenant@example.com",
        )

        uploaded = client.post(
            "/api/v1/library/files",
            headers=headers,
            files={"file": ("legacy.pdf", b"%PDF", "application/pdf")},
        )
        assert uploaded.status_code == 201, uploaded.text
        file_id = uploaded.json()["id"]

        with open_database_connection(settings) as connection:
            connection.execute(
                "update library_files set preview_supported = 0 where id = ?",
                (file_id,),
            )
            connection.commit()

        listed = client.get("/api/v1/library/files", headers=headers)
        assert listed.status_code == 200
        assert listed.json()["items"][0]["previewSupported"] is True

        preview = client.get(f"/api/v1/library/files/{file_id}/preview", headers=headers)
        assert preview.status_code == 200
        assert preview.json()["previewType"] == "url"


def test_library_docx_preview_extracts_text(tmp_path: Path) -> None:
    settings = _library_test_settings(tmp_path)
    store = FakeObjectStore()
    app = create_app(settings)
    app.dependency_overrides[get_object_store] = lambda: store

    docx = BytesIO()
    with ZipFile(docx, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body>
                <w:p><w:r><w:t>Hello DOCX</w:t></w:r></w:p>
                <w:p><w:r><w:t>Second line</w:t></w:r></w:p>
              </w:body>
            </w:document>
            """,
        )
    docx.seek(0)

    with TestClient(app) as client:
        _seed_tenant(settings)
        headers = _library_headers(
            client,
            settings,
            user_id="tenant_user",
            email="tenant@example.com",
        )

        uploaded = client.post(
            "/api/v1/library/files",
            headers=headers,
            files={
                "file": (
                    "proposal.docx",
                    docx.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert uploaded.status_code == 201, uploaded.text
        item = uploaded.json()
        assert item["previewSupported"] is True

        listed = client.get("/api/v1/library/files", headers=headers)
        assert listed.status_code == 200
        assert listed.json()["items"][0]["previewSupported"] is True

        preview = client.get(f"/api/v1/library/files/{item['id']}/preview", headers=headers)
        assert preview.status_code == 200
        body = preview.json()
        assert body["previewType"] == "text"
        assert body["content"] == "Hello DOCX\nSecond line"


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


# Streaming Markdown normalization ----------------------------------------------------

from app.services.chat_service import (  # noqa: E402
    _normalize_answer_markdown_delta,
    _SmoothTextBuffer,
)


def test_markdown_delta_skips_line_start_markers_on_midline_fragments() -> None:
    # A chunk that does not begin at a line start must not be reinterpreted as a heading
    # or list marker (e.g. "#5" must stay "#5", not become "# 5").
    assert _normalize_answer_markdown_delta("#5 wins", at_line_start=False) == "#5 wins"
    assert _normalize_answer_markdown_delta("#5 wins", at_line_start=True) == "# 5 wins"
    # Lines after an embedded newline are always genuine line starts.
    assert _normalize_answer_markdown_delta("tail #hi", at_line_start=False) == "tail #hi"
    assert _normalize_answer_markdown_delta("a\n#hi", at_line_start=False) == "a\n# hi"


def test_smooth_text_buffer_tracks_line_start() -> None:
    buf = _SmoothTextBuffer(max_chars=8, punctuation=False)
    # First chunk begins at a line start.
    assert buf.push("abcdefgh") == "abcdefgh"
    assert buf.chunk_at_line_start is True
    # The previous chunk had no trailing newline, so the next one is mid-line.
    assert buf.push("ijklmnop") == "ijklmnop"
    assert buf.chunk_at_line_start is False
    # A chunk that ends on a newline makes the following chunk a line start again.
    assert buf.push("qr\nstuvwx") == "qr\n"
    assert buf.flush() == "stuvwx"
    assert buf.chunk_at_line_start is True
