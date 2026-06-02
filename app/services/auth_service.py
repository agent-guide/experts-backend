from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
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
from app.domain.auth import Principal, Role, role_permissions


@dataclass
class UserRecord:
    id: str
    tenant_id: str
    email: str
    name: str
    password_hash: str
    status: str


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def register(self, email: str, password: str, name: str) -> dict[str, object]:
        tenant_id = self.settings.default_tenant_id
        normalized = email.strip().lower()

        with open_database_connection(self.settings) as connection:
            tenant = _fetch_one(
                connection,
                "select id, status from tenants where id = ? limit 1",
                (tenant_id,),
            )
            if not tenant or tenant["status"] != "active":
                raise ApiError(401, "AUTH_INVALID_TENANT", "Tenant not found or disabled")

            existing = _fetch_one(
                connection,
                "select id from users where tenant_id = ? and email = ? limit 1",
                (tenant_id, normalized),
            )
            if existing:
                raise ApiError(409, "AUTH_EMAIL_EXISTS", "Email is already registered")

            user = UserRecord(
                id=f"user_{uuid4().hex}",
                tenant_id=tenant_id,
                email=normalized,
                name=name,
                password_hash=hash_password(password),
                status="active",
            )
            _execute(
                connection,
                """
                insert into users (id, tenant_id, email, password_hash, name, status)
                values (?, ?, ?, ?, ?, 'active')
                """,
                (user.id, tenant_id, normalized, user.password_hash, name),
            )
            _execute(
                connection,
                """
                insert into user_roles (id, tenant_id, user_id, role, assigned_by)
                values (?, ?, ?, ?, ?)
                on conflict (tenant_id, user_id, role) do nothing
                """,
                (f"role_{uuid4().hex}", tenant_id, user.id, Role.USER.value, user.id),
            )
            token_pair = self._issue_token_pair(connection, user)
            _commit(connection)
            return token_pair

    def login(self, email: str, password: str) -> dict[str, object]:
        tenant_id = self.settings.default_tenant_id
        normalized = email.strip().lower()

        with open_database_connection(self.settings) as connection:
            tenant = _fetch_one(
                connection,
                "select id, status from tenants where id = ? limit 1",
                (tenant_id,),
            )
            if not tenant or tenant["status"] != "active":
                raise ApiError(401, "AUTH_INVALID_TENANT", "Tenant not found or disabled")

            user = self._find_user_by_email(connection, tenant_id, normalized)
            if not user or user.status != "active" or not verify_password(password, user.password_hash):
                raise ApiError(401, "AUTH_INVALID_CREDENTIALS", "Invalid email or password")

            token_pair = self._issue_token_pair(connection, user)
            _commit(connection)
            return token_pair

    def refresh(self, refresh_token: str) -> dict[str, object]:
        claims = decode_refresh_token(self.settings, refresh_token)
        tenant_id = str(claims["tenantId"])
        user_id = str(claims["sub"])
        token_hash = hash_opaque_token(refresh_token)

        with open_database_connection(self.settings) as connection:
            row = _fetch_one(
                connection,
                """
                select id from refresh_tokens
                where tenant_id = ?
                  and user_id = ?
                  and token_hash = ?
                  and revoked_at is null
                  and expires_at > ?
                limit 1
                """,
                (tenant_id, user_id, token_hash, _now_iso()),
            )
            if not row:
                raise ApiError(401, "AUTH_REFRESH_REVOKED", "Refresh token has been revoked")

            user = self._find_user_by_id(connection, tenant_id, user_id)
            if not user or user.status != "active":
                raise ApiError(401, "AUTH_USER_DISABLED", "User not found or disabled")

            _execute(
                connection,
                """
                update refresh_tokens
                set revoked_at = ?
                where tenant_id = ? and user_id = ? and token_hash = ? and revoked_at is null
                """,
                (_now_iso(), tenant_id, user_id, token_hash),
            )
            token_pair = self._issue_token_pair(connection, user)
            _commit(connection)
            return token_pair

    def logout(self, refresh_token: str) -> None:
        claims = decode_refresh_token(self.settings, refresh_token)
        _tenant_id = str(claims["tenantId"])
        _user_id = str(claims["sub"])
        token_hash = hash_opaque_token(refresh_token)

        with open_database_connection(self.settings) as connection:
            _execute(
                connection,
                """
                update refresh_tokens
                set revoked_at = ?
                where tenant_id = ? and user_id = ? and token_hash = ? and revoked_at is null
                """,
                (_now_iso(), _tenant_id, _user_id, token_hash),
            )
            _commit(connection)

    def activate_admin(self, activation_token: str, new_password: str, name: str | None = None) -> dict:
        token_hash = hash_opaque_token(activation_token)

        with open_database_connection(self.settings) as connection:
            row = _fetch_one(
                connection,
                """
                select
                  t.id as token_id,
                  t.tenant_id,
                  t.user_id,
                  t.expires_at,
                  t.used_at,
                  u.email
                from admin_activation_tokens t
                inner join users u
                  on u.id = t.user_id
                 and u.tenant_id = t.tenant_id
                where t.token_hash = ?
                limit 1
                """,
                (token_hash,),
            )
            if not row:
                raise ApiError(400, "AUTH_INVALID_ACTIVATION_TOKEN", "Invalid activation token")
            if row["used_at"]:
                raise ApiError(
                    400,
                    "AUTH_ACTIVATION_TOKEN_USED",
                    "Activation token has already been used",
                )
            if _parse_datetime(str(row["expires_at"])) <= datetime.now(timezone.utc):
                raise ApiError(
                    400,
                    "AUTH_ACTIVATION_TOKEN_EXPIRED",
                    "Activation token has expired",
                )

            tenant_id = str(row["tenant_id"])
            user_id = str(row["user_id"])
            _execute(
                connection,
                """
                update users
                set password_hash = ?, name = coalesce(?, name), updated_at = ?
                where tenant_id = ? and id = ?
                """,
                (hash_password(new_password), name, _now_iso(), tenant_id, user_id),
            )
            _execute(
                connection,
                "update admin_activation_tokens set used_at = ? where id = ?",
                (_now_iso(), str(row["token_id"])),
            )
            _commit(connection)

            return {
                "message": "Admin account activated",
                "userId": user_id,
                "tenantId": tenant_id,
                "email": str(row["email"]),
            }

    def grant_role(self, tenant_id: str, actor_user_id: str, target_user_id: str, role: Role) -> None:
        with open_database_connection(self.settings) as connection:
            actor_roles = self._list_roles(connection, tenant_id, actor_user_id)
            if not _can_grant_role(actor_roles, role):
                raise ApiError(403, "AUTH_FORBIDDEN", "Actor cannot grant this role")

            target_user = self._find_user_by_id(connection, tenant_id, target_user_id)
            if not target_user:
                raise ApiError(404, "USER_NOT_FOUND", "Target user does not exist")

            _execute(
                connection,
                """
                insert into user_roles (id, tenant_id, user_id, role, assigned_by)
                values (?, ?, ?, ?, ?)
                on conflict (tenant_id, user_id, role) do nothing
                """,
                (f"role_{uuid4().hex}", tenant_id, target_user_id, role.value, actor_user_id),
            )
            _commit(connection)

    def _issue_token_pair(
        self, connection: DatabaseConnection, user: UserRecord
    ) -> dict[str, object]:
        principal = self._principal(connection, user)
        token_pair = issue_token_pair(self.settings, principal)
        claims = decode_refresh_token(self.settings, str(token_pair["refreshToken"]))
        expires_at = datetime.fromtimestamp(int(claims["exp"]), timezone.utc).isoformat()
        _execute(
            connection,
            """
            insert into refresh_tokens (id, tenant_id, user_id, token_hash, expires_at)
            values (?, ?, ?, ?, ?)
            """,
            (
                f"refresh_{uuid4().hex}",
                user.tenant_id,
                user.id,
                hash_opaque_token(str(token_pair["refreshToken"])),
                expires_at,
            ),
        )
        return token_pair

    def _principal(self, connection: DatabaseConnection, user: UserRecord) -> Principal:
        roles = self._list_roles(connection, user.tenant_id, user.id)
        permissions = sorted({perm for role in roles for perm in role_permissions(role)})
        return Principal(
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            roles=roles,
            permissions=permissions,
        )

    def _list_roles(
        self, connection: DatabaseConnection, tenant_id: str, user_id: str
    ) -> list[Role]:
        rows = _fetch_all(
            connection,
            """
            select role from user_roles
            where tenant_id = ? and user_id = ?
            order by created_at asc
            """,
            (tenant_id, user_id),
        )
        return [Role(str(row["role"])) for row in rows]

    def _find_user_by_email(
        self, connection: DatabaseConnection, tenant_id: str, email: str
    ) -> UserRecord | None:
        row = _fetch_one(
            connection,
            """
            select id, tenant_id, email, password_hash, name, status
            from users
            where tenant_id = ? and email = ?
            limit 1
            """,
            (tenant_id, email),
        )
        return _map_user(row)

    def _find_user_by_id(
        self, connection: DatabaseConnection, tenant_id: str, user_id: str
    ) -> UserRecord | None:
        row = _fetch_one(
            connection,
            """
            select id, tenant_id, email, password_hash, name, status
            from users
            where tenant_id = ? and id = ?
            limit 1
            """,
            (tenant_id, user_id),
        )
        return _map_user(row)


def _map_user(row: dict[str, Any] | None) -> UserRecord | None:
    if not row:
        return None
    return UserRecord(
        id=str(row["id"]),
        tenant_id=str(row["tenant_id"]),
        email=str(row["email"]),
        password_hash=str(row["password_hash"]),
        name=str(row["name"]),
        status=str(row["status"]),
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


def _can_grant_role(actor_roles: list[Role], target_role: Role) -> bool:
    if Role.OPS in actor_roles:
        return target_role != Role.ADMIN
    if Role.ADMIN in actor_roles:
        return target_role in {Role.USER, Role.EXPERT, Role.OPS}
    return False
