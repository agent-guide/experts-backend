from __future__ import annotations

import re
import secrets
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import (
    decode_refresh_token,
    hash_opaque_token,
    hash_password,
    issue_token_pair,
    verify_password,
)
from app.db import DatabaseConnection, open_database_connection
from app.domain.auth import (
    CreatePlatformUserResponse,
    PlatformRole,
    Principal,
    TenantRole,
    UserAccessSummary,
    platform_role_permissions,
    tenant_role_permissions,
)


@dataclass
class UserRecord:
    id: str
    email: str
    name: str
    password_hash: str
    status: str
    created_at: str
    updated_at: str


@dataclass
class TenantMembership:
    tenant_id: str
    role: TenantRole


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def current_principal(self, token_principal: Principal) -> Principal:
        with open_database_connection(self.settings) as connection:
            user = self._find_user_by_id(connection, token_principal.user_id)
            if not user or user.status != "active":
                raise ApiError(401, "AUTH_USER_DISABLED", "User not found or disabled")

            active_tenant_id = token_principal.active_tenant_id
            if active_tenant_id:
                roles = self._list_tenant_roles(connection, active_tenant_id, token_principal.user_id)
                if not roles:
                    # The token's tenant context is no longer valid (membership was
                    # revoked). Drop it instead of failing every request: tenant and
                    # platform contexts are independent, so platform/identity calls must
                    # still work. Tenant-scoped endpoints reject the request anyway
                    # because the now-empty active tenant cannot match `x-tenant-id`.
                    active_tenant_id = None

            return self._principal(connection, user, active_tenant_id)

    def register(self, email: str, password: str, name: str) -> dict[str, object]:
        normalized = email.strip().lower()

        with open_database_connection(self.settings) as connection:
            existing = _fetch_one(
                connection,
                "select id from users where email = ? limit 1",
                (normalized,),
            )
            if existing:
                raise ApiError(409, "AUTH_EMAIL_EXISTS", "Email is already registered")

            now = _now_iso()
            user = UserRecord(
                id=f"user_{uuid4().hex}",
                email=normalized,
                name=name,
                password_hash=hash_password(password),
                status="active",
                created_at=now,
                updated_at=now,
            )
            tenant_id = f"tenant_{uuid4().hex}"
            _execute(
                connection,
                """
                insert into users (id, email, password_hash, name, status)
                values (?, ?, ?, ?, 'active')
                """,
                (user.id, normalized, user.password_hash, name),
            )
            _execute(
                connection,
                """
                insert into tenants (id, type, name, slug, owner_user_id, status)
                values (?, 'personal', ?, ?, ?, 'active')
                """,
                (tenant_id, f"{name}'s Workspace", _tenant_slug(normalized), user.id),
            )
            _execute(
                connection,
                """
                insert into tenant_members (id, tenant_id, user_id, role)
                values (?, ?, ?, ?)
                """,
                (f"member_{uuid4().hex}", tenant_id, user.id, TenantRole.ADMIN.value),
            )
            token_pair = self._issue_token_pair(connection, user, tenant_id)
            _commit(connection)
            return token_pair

    def login(self, email: str, password: str, tenant_id: str | None = None) -> dict[str, object]:
        normalized = email.strip().lower()

        with open_database_connection(self.settings) as connection:
            user = self._find_user_by_email(connection, normalized)
            if not user or user.status != "active" or not verify_password(password, user.password_hash):
                raise ApiError(401, "AUTH_INVALID_CREDENTIALS", "Invalid email or password")

            active_tenant_id = self._resolve_active_tenant(connection, user.id, tenant_id)
            token_pair = self._issue_token_pair(connection, user, active_tenant_id)
            _commit(connection)
            return token_pair

    def refresh(self, refresh_token: str, tenant_id: str | None = None) -> dict[str, object]:
        claims = decode_refresh_token(self.settings, refresh_token)
        user_id = str(claims["sub"])
        token_hash = hash_opaque_token(refresh_token)

        with open_database_connection(self.settings) as connection:
            row = _fetch_one(
                connection,
                """
                select id from refresh_tokens
                where user_id = ?
                  and token_hash = ?
                  and revoked_at is null
                  and expires_at > ?
                limit 1
                """,
                (user_id, token_hash, _now_iso()),
            )
            if not row:
                raise ApiError(401, "AUTH_REFRESH_REVOKED", "Refresh token has been revoked")

            user = self._find_user_by_id(connection, user_id)
            if not user or user.status != "active":
                raise ApiError(401, "AUTH_USER_DISABLED", "User not found or disabled")

            _execute(
                connection,
                """
                update refresh_tokens
                set revoked_at = ?
                where user_id = ? and token_hash = ? and revoked_at is null
                """,
                (_now_iso(), user_id, token_hash),
            )
            active_tenant_id = self._resolve_active_tenant(connection, user.id, tenant_id)
            token_pair = self._issue_token_pair(connection, user, active_tenant_id)
            _commit(connection)
            return token_pair

    def logout(self, refresh_token: str) -> None:
        claims = decode_refresh_token(self.settings, refresh_token)
        user_id = str(claims["sub"])
        token_hash = hash_opaque_token(refresh_token)

        with open_database_connection(self.settings) as connection:
            _execute(
                connection,
                """
                update refresh_tokens
                set revoked_at = ?
                where user_id = ? and token_hash = ? and revoked_at is null
                """,
                (_now_iso(), user_id, token_hash),
            )
            _commit(connection)

    def activate_platform_user(
        self, activation_token: str, new_password: str, name: str | None = None
    ) -> dict:
        token_hash = hash_opaque_token(activation_token)

        with open_database_connection(self.settings) as connection:
            row = _fetch_one(
                connection,
                """
                select
                  t.id as token_id,
                  t.user_id,
                  t.expires_at,
                  t.used_at,
                  u.email
                from platform_activation_tokens t
                inner join users u on u.id = t.user_id
                where t.token_hash = ?
                limit 1
                """,
                (token_hash,),
            )
            if not row:
                raise ApiError(400, "AUTH_INVALID_ACTIVATION_TOKEN", "Invalid activation token")
            if row["used_at"]:
                raise ApiError(400, "AUTH_ACTIVATION_TOKEN_USED", "Activation token has already been used")
            if _parse_datetime(str(row["expires_at"])) <= datetime.now(timezone.utc):
                raise ApiError(400, "AUTH_ACTIVATION_TOKEN_EXPIRED", "Activation token has expired")

            user_id = str(row["user_id"])
            _execute(
                connection,
                """
                update users
                set password_hash = ?, name = coalesce(?, name), status = 'active', updated_at = ?
                where id = ?
                """,
                (hash_password(new_password), name, _now_iso(), user_id),
            )
            _execute(
                connection,
                "update platform_activation_tokens set used_at = ? where id = ?",
                (_now_iso(), str(row["token_id"])),
            )
            _commit(connection)

            return {
                "message": "Platform user activated",
                "userId": user_id,
                "email": str(row["email"]),
            }

    def create_platform_user(
        self,
        actor_user_id: str,
        email: str,
        name: str,
        roles: Sequence[PlatformRole],
    ) -> CreatePlatformUserResponse:
        normalized = email.strip().lower()
        unique_roles = list(dict.fromkeys(roles or [PlatformRole.EXPERT]))

        with open_database_connection(self.settings) as connection:
            actor_roles = self._list_platform_roles(connection, actor_user_id)
            for role in unique_roles:
                if not _can_grant_platform_role(actor_roles, role):
                    raise ApiError(403, "AUTH_FORBIDDEN", "Actor cannot grant platform roles")

            existing = _fetch_one(
                connection,
                "select id from users where email = ? limit 1",
                (normalized,),
            )
            if existing:
                raise ApiError(409, "AUTH_EMAIL_EXISTS", "Email is already registered")

            user_id = f"user_{uuid4().hex}"
            activation_token = secrets.token_urlsafe(32)
            expires_at = (
                datetime.now(timezone.utc)
                + timedelta(seconds=self.settings.platform_activation_token_ttl_seconds)
            ).isoformat()

            _execute(
                connection,
                """
                insert into users (id, email, password_hash, name, status)
                values (?, ?, ?, ?, 'pending_activation')
                """,
                (user_id, normalized, hash_password(secrets.token_urlsafe(32)), name),
            )
            for role in unique_roles:
                _execute(
                    connection,
                    """
                    insert into platform_user_roles (id, user_id, role, assigned_by)
                    values (?, ?, ?, ?)
                    """,
                    (f"platform_role_{uuid4().hex}", user_id, role.value, actor_user_id),
                )
            _execute(
                connection,
                """
                insert into platform_activation_tokens
                  (id, user_id, token_hash, expires_at)
                values (?, ?, ?, ?)
                """,
                (
                    f"platform_activation_{uuid4().hex}",
                    user_id,
                    hash_opaque_token(activation_token),
                    expires_at,
                ),
            )
            _commit(connection)

            return CreatePlatformUserResponse(
                id=user_id,
                email=normalized,
                name=name,
                status="pending_activation",
                platformRoles=unique_roles,
                activationToken=activation_token,
                activationExpiresAt=expires_at,
            )

    def grant_tenant_role(
        self,
        tenant_id: str,
        actor_user_id: str,
        target_user_id: str,
        role: TenantRole,
    ) -> None:
        with open_database_connection(self.settings) as connection:
            _begin_write_transaction(connection)
            self._lock_tenant_members(connection, tenant_id)
            actor_roles = self._list_tenant_roles(connection, tenant_id, actor_user_id)
            if TenantRole.ADMIN not in actor_roles:
                raise ApiError(403, "AUTH_FORBIDDEN", "Actor cannot grant tenant roles")

            target_user = self._find_user_by_id(connection, target_user_id)
            if not target_user:
                raise ApiError(404, "USER_NOT_FOUND", "Target user does not exist")

            if role != TenantRole.ADMIN:
                target_roles = self._list_tenant_roles(connection, tenant_id, target_user_id)
                if (
                    TenantRole.ADMIN in target_roles
                    and self._count_tenant_admins(connection, tenant_id) <= 1
                ):
                    raise ApiError(409, "TENANT_LAST_ADMIN", "Cannot demote the last tenant admin")

            _execute(
                connection,
                """
                insert into tenant_members (id, tenant_id, user_id, role)
                values (?, ?, ?, ?)
                on conflict (tenant_id, user_id) do update
                set role = excluded.role,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (f"member_{uuid4().hex}", tenant_id, target_user_id, role.value),
            )
            _commit(connection)

    def grant_platform_role(
        self,
        actor_user_id: str,
        target_user_id: str,
        role: PlatformRole,
    ) -> None:
        with open_database_connection(self.settings) as connection:
            actor_roles = self._list_platform_roles(connection, actor_user_id)
            if not _can_grant_platform_role(actor_roles, role):
                raise ApiError(403, "AUTH_FORBIDDEN", "Actor cannot grant platform roles")

            target_user = self._find_user_by_id(connection, target_user_id)
            if not target_user:
                raise ApiError(404, "USER_NOT_FOUND", "Target user does not exist")

            _execute(
                connection,
                """
                insert into platform_user_roles (id, user_id, role, assigned_by)
                values (?, ?, ?, ?)
                on conflict (user_id, role) do nothing
                """,
                (f"platform_role_{uuid4().hex}", target_user_id, role.value, actor_user_id),
            )
            _commit(connection)

    def revoke_tenant_member(
        self,
        tenant_id: str,
        actor_user_id: str,
        target_user_id: str,
    ) -> None:
        with open_database_connection(self.settings) as connection:
            _begin_write_transaction(connection)
            self._lock_tenant_members(connection, tenant_id)
            actor_roles = self._list_tenant_roles(connection, tenant_id, actor_user_id)
            if TenantRole.ADMIN not in actor_roles:
                raise ApiError(403, "AUTH_FORBIDDEN", "Actor cannot manage tenant members")

            target_roles = self._list_tenant_roles(connection, tenant_id, target_user_id)
            if not target_roles:
                raise ApiError(404, "MEMBER_NOT_FOUND", "User is not a member of this tenant")

            if TenantRole.ADMIN in target_roles and self._count_tenant_admins(connection, tenant_id) <= 1:
                raise ApiError(409, "TENANT_LAST_ADMIN", "Cannot remove the last tenant admin")

            _execute(
                connection,
                "delete from tenant_members where tenant_id = ? and user_id = ?",
                (tenant_id, target_user_id),
            )
            _commit(connection)

    def revoke_platform_role(
        self,
        actor_user_id: str,
        target_user_id: str,
        role: PlatformRole,
    ) -> None:
        with open_database_connection(self.settings) as connection:
            _begin_write_transaction(connection)
            self._lock_platform_roles(connection)
            actor_roles = self._list_platform_roles(connection, actor_user_id)
            if not _can_grant_platform_role(actor_roles, role):
                raise ApiError(403, "AUTH_FORBIDDEN", "Actor cannot revoke platform roles")

            target_user = self._find_user_by_id(connection, target_user_id)
            if not target_user:
                raise ApiError(404, "USER_NOT_FOUND", "Target user does not exist")

            target_roles = self._list_platform_roles(connection, target_user_id)
            if (
                role == PlatformRole.ADMIN
                and PlatformRole.ADMIN in target_roles
                and self._count_platform_admins(connection) <= 1
            ):
                raise ApiError(409, "PLATFORM_LAST_ADMIN", "Cannot revoke the last platform admin")

            _execute(
                connection,
                "delete from platform_user_roles where user_id = ? and role = ?",
                (target_user_id, role.value),
            )
            _commit(connection)

    def list_tenant_users(self, tenant_id: str) -> list[UserAccessSummary]:
        with open_database_connection(self.settings) as connection:
            rows = _fetch_all(
                connection,
                """
                select u.id, u.email, u.name, u.status, u.created_at, u.updated_at
                from users u
                inner join tenant_members tm on tm.user_id = u.id
                where tm.tenant_id = ?
                order by u.created_at desc, u.id asc
                """,
                (tenant_id,),
            )

            return [
                self._user_access_summary(connection, user, tenant_id)
                for row in rows
                if (user := _map_user_summary(row)) is not None
            ]

    def list_platform_users(self) -> list[UserAccessSummary]:
        with open_database_connection(self.settings) as connection:
            rows = _fetch_all(
                connection,
                """
                select distinct u.id, u.email, u.name, u.status, u.created_at, u.updated_at
                from users u
                inner join platform_user_roles pur on pur.user_id = u.id
                order by u.created_at desc, u.id asc
                """,
            )

            return [
                self._user_access_summary(connection, user, None)
                for row in rows
                if (user := _map_user_summary(row)) is not None
            ]

    def _issue_token_pair(
        self, connection: DatabaseConnection, user: UserRecord, active_tenant_id: str | None
    ) -> dict[str, object]:
        principal = self._principal(connection, user, active_tenant_id)
        token_pair = issue_token_pair(self.settings, principal)
        claims = decode_refresh_token(self.settings, str(token_pair["refreshToken"]))
        expires_at = datetime.fromtimestamp(int(claims["exp"]), timezone.utc).isoformat()
        _execute(
            connection,
            """
            insert into refresh_tokens (id, user_id, token_hash, expires_at)
            values (?, ?, ?, ?)
            """,
            (
                f"refresh_{uuid4().hex}",
                user.id,
                hash_opaque_token(str(token_pair["refreshToken"])),
                expires_at,
            ),
        )
        return token_pair

    def _principal(
        self, connection: DatabaseConnection, user: UserRecord, active_tenant_id: str | None
    ) -> Principal:
        tenant_roles = (
            self._list_tenant_roles(connection, active_tenant_id, user.id)
            if active_tenant_id
            else []
        )
        platform_roles = self._list_platform_roles(connection, user.id)
        return Principal(
            user_id=user.id,
            email=user.email,
            active_tenant_id=active_tenant_id,
            tenant_roles=tenant_roles,
            tenant_permissions=sorted(
                {perm for role in tenant_roles for perm in tenant_role_permissions(role)}
            ),
            platform_roles=platform_roles,
            platform_permissions=sorted(
                {perm for role in platform_roles for perm in platform_role_permissions(role)}
            ),
        )

    def _resolve_active_tenant(
        self, connection: DatabaseConnection, user_id: str, requested_tenant_id: str | None
    ) -> str | None:
        if requested_tenant_id:
            roles = self._list_tenant_roles(connection, requested_tenant_id, user_id)
            if not roles:
                raise ApiError(403, "AUTH_FORBIDDEN", "User is not a member of this tenant")
            return requested_tenant_id

        row = _fetch_one(
            connection,
            """
            select tenant_id from tenant_members
            where user_id = ?
            order by created_at asc
            limit 1
            """,
            (user_id,),
        )
        return str(row["tenant_id"]) if row else None

    def _list_tenant_roles(
        self, connection: DatabaseConnection, tenant_id: str, user_id: str
    ) -> list[TenantRole]:
        rows = _fetch_all(
            connection,
            """
            select role from tenant_members
            where tenant_id = ? and user_id = ?
            order by created_at asc
            """,
            (tenant_id, user_id),
        )
        return [TenantRole(str(row["role"])) for row in rows]

    def _count_tenant_admins(self, connection: DatabaseConnection, tenant_id: str) -> int:
        row = _fetch_one(
            connection,
            "select count(*) as count from tenant_members where tenant_id = ? and role = ?",
            (tenant_id, TenantRole.ADMIN.value),
        )
        return int(row["count"]) if row else 0

    def _lock_tenant_members(self, connection: DatabaseConnection, tenant_id: str) -> None:
        if isinstance(connection, sqlite3.Connection):
            return
        _execute(
            connection,
            "select id from tenant_members where tenant_id = ? order by id for update",
            (tenant_id,),
        )

    def _list_platform_roles(self, connection: DatabaseConnection, user_id: str) -> list[PlatformRole]:
        rows = _fetch_all(
            connection,
            """
            select role from platform_user_roles
            where user_id = ?
            order by created_at asc
            """,
            (user_id,),
        )
        return [PlatformRole(str(row["role"])) for row in rows]

    def _count_platform_admins(self, connection: DatabaseConnection) -> int:
        row = _fetch_one(
            connection,
            "select count(*) as count from platform_user_roles where role = ?",
            (PlatformRole.ADMIN.value,),
        )
        return int(row["count"]) if row else 0

    def _lock_platform_roles(self, connection: DatabaseConnection) -> None:
        if isinstance(connection, sqlite3.Connection):
            return
        _execute(
            connection,
            "select id from platform_user_roles order by id for update",
        )

    def _find_user_by_email(self, connection: DatabaseConnection, email: str) -> UserRecord | None:
        row = _fetch_one(
            connection,
            """
            select id, email, password_hash, name, status, created_at, updated_at
            from users
            where email = ?
            limit 1
            """,
            (email,),
        )
        return _map_user(row)

    def _find_user_by_id(self, connection: DatabaseConnection, user_id: str) -> UserRecord | None:
        row = _fetch_one(
            connection,
            """
            select id, email, password_hash, name, status, created_at, updated_at
            from users
            where id = ?
            limit 1
            """,
            (user_id,),
        )
        return _map_user(row)

    def _user_access_summary(
        self, connection: DatabaseConnection, user: UserRecord, active_tenant_id: str | None
    ) -> UserAccessSummary:
        tenant_roles = (
            self._list_tenant_roles(connection, active_tenant_id, user.id)
            if active_tenant_id
            else []
        )
        platform_roles = self._list_platform_roles(connection, user.id)
        return UserAccessSummary(
            id=user.id,
            email=user.email,
            name=user.name,
            status=user.status,
            activeTenantId=active_tenant_id,
            tenantRoles=tenant_roles,
            tenantPermissions=sorted(
                {perm for role in tenant_roles for perm in tenant_role_permissions(role)}
            ),
            platformRoles=platform_roles,
            platformPermissions=sorted(
                {perm for role in platform_roles for perm in platform_role_permissions(role)}
            ),
            createdAt=user.created_at,
            updatedAt=user.updated_at,
        )


def _map_user(row: dict[str, Any] | None) -> UserRecord | None:
    if not row:
        return None
    return UserRecord(
        id=str(row["id"]),
        email=str(row["email"]),
        password_hash=str(row["password_hash"]),
        name=str(row["name"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _map_user_summary(row: dict[str, Any] | None) -> UserRecord | None:
    """Map a user row that does not include the password hash (listing context)."""
    if not row:
        return None
    return UserRecord(
        id=str(row["id"]),
        email=str(row["email"]),
        password_hash="",
        name=str(row["name"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _execute(connection: DatabaseConnection, sql: str, params: Sequence[Any] = ()) -> Any:
    return connection.execute(_prepare_sql(connection, sql), params)


def _begin_write_transaction(connection: DatabaseConnection) -> None:
    if isinstance(connection, sqlite3.Connection):
        connection.execute("begin immediate")


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


def _commit(connection: DatabaseConnection) -> None:
    connection.commit()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _tenant_slug(email: str) -> str:
    local_part = email.split("@", 1)[0]
    slug = re.sub(r"[^a-z0-9]+", "-", local_part.lower()).strip("-")
    return f"{slug or 'user'}-{uuid4().hex[:8]}"


def _can_grant_platform_role(actor_roles: list[PlatformRole], target_role: PlatformRole) -> bool:
    if PlatformRole.ADMIN in actor_roles:
        return True
    if PlatformRole.OPERATOR in actor_roles:
        return target_role != PlatformRole.ADMIN
    return False
