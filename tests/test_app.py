from pathlib import Path
from io import BytesIO
from zipfile import ZipFile

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
    assert "/api/v1/users/register" in paths
    assert "/api/v1/users/platform/activate" in paths
    assert "/api/v1/users/platform" in paths
    assert "/api/v1/rbac/tenant/users" in paths
    assert "/api/v1/rbac/tenant/users/{user_id}/roles" in paths
    assert "/api/v1/rbac/tenant/users/{user_id}" in paths
    assert "/api/v1/rbac/platform/users/{user_id}/roles" in paths
    assert "/api/v1/rbac/platform/users/{user_id}/roles/{role}" in paths
    assert "/api/v1/admin/users" not in paths
    assert "/api/v1/knowledge-bases" in paths
    assert "/api/v1/knowledge-bases/official" in paths
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
        assert "kb:delete" in items["target_user"]["tenantPermissions"]
        assert "doc:reindex" not in items["target_user"]["tenantPermissions"]

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
        assert "doc:reindex" in updated_items["target_user"]["tenantPermissions"]

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
            "/api/v1/knowledge-bases/official",
            headers=stale_headers,
            json={"name": "Official KB", "description": "test"},
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
        assert [item["slug"] for item in list_response.json()["items"]] == [
            "amazon-review-analyzer"
        ]

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
