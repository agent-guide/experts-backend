from __future__ import annotations

import re
import secrets
import sqlite3
import json
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
    UserDetail,
    UserLifetimeUsageSummary,
    UserMonthlyUsageSummary,
    UserOrderSummary,
    UserAccessSummary,
    UserSummary,
    UserSubscriptionSummary,
    UserTenantSummary,
    platform_role_permissions,
    tenant_role_permissions,
)
from app.services.plan_pricing import select_price_snapshot


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

    def list_managed_users(
        self,
        *,
        search: str | None = None,
        subscription_status: str | None = None,
        subscription_type: str | None = None,
        sort: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[UserSummary], int]:
        """List non-platform users for ordinary user management."""
        with open_database_connection(self.settings) as connection:
            rows = _fetch_all(
                connection,
                """
                select
                  u.id,
                  u.email,
                  u.name,
                  u.status,
                  u.created_at,
                  u.updated_at,
                  count(tm.id) as tenant_count
                from users u
                left join tenant_members tm on tm.user_id = u.id
                where not exists (
                  select 1 from platform_user_roles pur where pur.user_id = u.id
                )
                group by u.id, u.email, u.name, u.status, u.created_at, u.updated_at
                order by u.created_at desc, u.id asc
                """,
            )

            items = [
                self._managed_user_summary(connection, row)
                for row in rows
            ]
            items = _filter_user_summaries(
                items,
                search=search,
                subscription_status=subscription_status,
                subscription_type=subscription_type,
            )
            items = _sort_user_summaries(items, sort)
            total = len(items)
            start = max(page - 1, 0) * page_size
            return items[start : start + page_size], total

    def get_managed_user(self, user_id: str) -> UserDetail:
        with open_database_connection(self.settings) as connection:
            user = self._find_user_by_id(connection, user_id)
            if not user:
                raise ApiError(404, "USER_NOT_FOUND", "User not found")
            return self._user_detail(connection, user)

    def update_user(self, user_id: str, *, name: str | None) -> UserDetail:
        with open_database_connection(self.settings) as connection:
            user = self._find_user_by_id(connection, user_id)
            if not user:
                raise ApiError(404, "USER_NOT_FOUND", "User not found")
            next_name = name if name is not None else user.name
            _execute(
                connection,
                """
                update users
                set name = ?, updated_at = CURRENT_TIMESTAMP
                where id = ?
                """,
                (next_name, user_id),
            )
            _commit(connection)
            updated = self._find_user_by_id(connection, user_id)
            if not updated:
                raise ApiError(404, "USER_NOT_FOUND", "User not found")
            return self._user_detail(connection, updated)

    def update_user_status(self, user_id: str, *, status: str) -> UserDetail:
        with open_database_connection(self.settings) as connection:
            _begin_write_transaction(connection)
            user = self._find_user_by_id(connection, user_id)
            if not user:
                raise ApiError(404, "USER_NOT_FOUND", "User not found")

            roles = self._list_platform_roles(connection, user_id)
            if (
                status == "disabled"
                and PlatformRole.ADMIN in roles
                and self._count_platform_admins(connection) <= 1
            ):
                raise ApiError(409, "PLATFORM_LAST_ADMIN", "Cannot disable the last platform admin")

            _execute(
                connection,
                """
                update users
                set status = ?, updated_at = CURRENT_TIMESTAMP
                where id = ?
                """,
                (status, user_id),
            )
            _commit(connection)
            updated = self._find_user_by_id(connection, user_id)
            if not updated:
                raise ApiError(404, "USER_NOT_FOUND", "User not found")
            return self._user_detail(connection, updated)

    def list_user_tenants(self, user_id: str) -> list[UserTenantSummary]:
        with open_database_connection(self.settings) as connection:
            user = self._find_user_by_id(connection, user_id)
            if not user:
                raise ApiError(404, "USER_NOT_FOUND", "User not found")
            return self._list_user_tenants(connection, user_id)

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

    def _user_detail(self, connection: DatabaseConnection, user: UserRecord) -> UserDetail:
        platform_roles = self._list_platform_roles(connection, user.id)
        subscription = self._current_subscription_summary(connection, user.id)
        return UserDetail(
            id=user.id,
            email=user.email,
            name=user.name,
            status=user.status,
            platformRoles=platform_roles,
            platformPermissions=sorted(
                {perm for role in platform_roles for perm in platform_role_permissions(role)}
            ),
            tenants=self._list_user_tenants(connection, user.id),
            currentSubscription=subscription,
            monthlyUsage=self._monthly_usage_summary(connection, user.id, subscription),
            orderSummary=UserOrderSummary(),
            usageLifetime=_lifetime_usage(user.created_at, subscription),
            createdAt=user.created_at,
            updatedAt=user.updated_at,
        )

    def _managed_user_summary(self, connection: DatabaseConnection, row: dict[str, Any]) -> UserSummary:
        user_id = str(row["id"])
        created_at = str(row["created_at"])
        subscription = self._current_subscription_summary(connection, user_id)
        return UserSummary(
            id=user_id,
            email=str(row["email"]),
            name=str(row["name"]),
            status=str(row["status"]),
            platformRoles=[],
            tenantCount=int(row["tenant_count"]),
            currentSubscription=subscription,
            monthlyUsage=self._monthly_usage_summary(connection, user_id, subscription),
            orderSummary=UserOrderSummary(),
            usageLifetime=_lifetime_usage(created_at, subscription),
            createdAt=created_at,
            updatedAt=str(row["updated_at"]),
        )

    def _current_subscription_summary(
        self, connection: DatabaseConnection, user_id: str
    ) -> UserSubscriptionSummary | None:
        row = _fetch_one(
            connection,
            """
            select
              s.id,
              s.tenant_id,
              s.plan_id,
              s.status,
              s.billing_period,
              s.current_period_start,
              s.current_period_end,
              s.cancel_at_period_end,
              p.code as plan_code,
              p.name as plan_name,
              p.prices,
              t.name as tenant_name,
              p.entitlements,
              p.expert_ids
            from tenant_members tm
            inner join tenants t on t.id = tm.tenant_id
            inner join subscriptions s on s.tenant_id = t.id
            inner join plans p on p.id = s.plan_id
            where tm.user_id = ?
            order by
              case
                when s.status in ('active', 'trialing', 'past_due')
                 and (s.current_period_end is null or s.current_period_end > CURRENT_TIMESTAMP)
                then 0 else 1
              end,
              s.current_period_start desc,
              s.created_at desc
            limit 1
            """,
            (user_id,),
        )
        if not row:
            return None
        ends_at = str(row["current_period_end"]) if row["current_period_end"] is not None else None
        days_until_expiry = _days_until(ends_at)
        status = _subscription_status(str(row["status"]), ends_at)
        price_snapshot = select_price_snapshot(
            _json_list_dicts(row["prices"]), str(row["billing_period"])
        )
        return UserSubscriptionSummary(
            subscriptionId=str(row["id"]),
            planId=str(row["plan_id"]),
            planCode=str(row["plan_code"]),
            planName=str(row["plan_name"]),
            billingPeriod=str(row["billing_period"]),
            status=status,
            statusLabel=_subscription_status_label(status),
            currentPeriodStart=str(row["current_period_start"]),
            currentPeriodEnd=ends_at,
            daysUntilExpiry=days_until_expiry,
            cancelAtPeriodEnd=bool(row["cancel_at_period_end"]),
            autoRenew=not bool(row["cancel_at_period_end"]) and str(row["billing_period"]) != "free",
            priceLabel=_price_label(price_snapshot),
            currentOrderNo=None,
            paymentMethod="免费开通" if str(row["billing_period"]) == "free" else None,
            tenantId=str(row["tenant_id"]),
            tenantName=str(row["tenant_name"]),
        )

    def _monthly_usage_summary(
        self,
        connection: DatabaseConnection,
        user_id: str,
        subscription: UserSubscriptionSummary | None,
    ) -> UserMonthlyUsageSummary:
        tenant_id = subscription.tenantId if subscription else None
        if not tenant_id:
            return UserMonthlyUsageSummary(status=_usage_status(subscription, 0, 0, 0, 0))
        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        row = _fetch_one(
            connection,
            """
            select count(*) as count
            from chat_turns
            where tenant_id = ?
              and user_id = ?
              and created_at >= ?
              and is_internal = false
            """,
            (tenant_id, user_id, month_start),
        )
        question_used = int(row["count"]) if row else 0
        entitlements = self._subscription_entitlements(connection, subscription)
        question_limit = int(entitlements.get("monthlyQuestionLimit", 0) or 0)
        token_limit = int(entitlements.get("monthlyTokenLimit", 0) or 0)
        token_used = 0
        status = _usage_status(subscription, question_used, question_limit, token_used, token_limit)
        return UserMonthlyUsageSummary(
            questionUsed=question_used,
            questionLimit=question_limit,
            tokenUsed=token_used,
            tokenLimit=token_limit,
            questionUsagePercent=_percent(question_used, question_limit),
            tokenUsagePercent=_percent(token_used, token_limit),
            status=status,
            isServicePaused=status in {"question_exhausted", "token_exhausted", "expired"},
        )

    def _subscription_entitlements(
        self, connection: DatabaseConnection, subscription: UserSubscriptionSummary
    ) -> dict[str, Any]:
        row = _fetch_one(
            connection,
            """
            select p.entitlements, p.expert_ids
            from subscriptions s
            inner join plans p on p.id = s.plan_id
            where s.id = ?
            limit 1
            """,
            (subscription.subscriptionId,),
        )
        if not row:
            return {}
        entitlements = _json_dict(row["entitlements"])
        entitlements["expertIds"] = _json_list(row["expert_ids"])
        return entitlements

    def _list_user_tenants(
        self, connection: DatabaseConnection, user_id: str
    ) -> list[UserTenantSummary]:
        rows = _fetch_all(
            connection,
            """
            select
              t.id,
              t.name,
              t.type,
              t.slug,
              t.status,
              tm.role,
              tm.created_at as joined_at
            from tenant_members tm
            inner join tenants t on t.id = tm.tenant_id
            where tm.user_id = ?
            order by tm.created_at desc, t.id asc
            """,
            (user_id,),
        )
        return [
            UserTenantSummary(
                id=str(row["id"]),
                name=str(row["name"]),
                type=str(row["type"]),
                slug=str(row["slug"]),
                status=str(row["status"]),
                role=TenantRole(str(row["role"])),
                joinedAt=str(row["joined_at"]),
            )
            for row in rows
        ]

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


def _filter_user_summaries(
    items: list[UserSummary],
    *,
    search: str | None,
    subscription_status: str | None,
    subscription_type: str | None,
) -> list[UserSummary]:
    if search:
        needle = search.casefold()
        items = [
            item
            for item in items
            if needle in item.name.casefold()
            or needle in item.email.casefold()
            or (
                item.currentSubscription is not None
                and needle in (item.currentSubscription.planName or "").casefold()
            )
            or needle in str(item.tenantCount)
        ]
    if subscription_status:
        expected = _normalize_subscription_filter(subscription_status)
        items = [
            item
            for item in items
            if item.currentSubscription is not None
            and item.currentSubscription.status == expected
        ]
    if subscription_type:
        expected = subscription_type.casefold()
        items = [
            item
            for item in items
            if item.currentSubscription is not None
            and (
                (
                    f"{item.currentSubscription.planName or ''} "
                    f"{item.currentSubscription.billingPeriod or ''} "
                    f"{_billing_period_label(item.currentSubscription.billingPeriod)}"
                    f" {item.currentSubscription.planName or ''} · "
                    f"{_billing_period_label(item.currentSubscription.billingPeriod)}"
                )
            ).casefold().find(expected)
            >= 0
        ]
    return items


def _sort_user_summaries(items: list[UserSummary], sort: str | None) -> list[UserSummary]:
    if sort == "expiresAt":
        return sorted(
            items,
            key=lambda item: (
                item.currentSubscription is None
                or item.currentSubscription.currentPeriodEnd is None,
                item.currentSubscription.currentPeriodEnd if item.currentSubscription else "",
            ),
        )
    if sort == "monthlyUsage":
        return sorted(items, key=lambda item: item.monthlyUsage.questionUsed, reverse=True)
    if sort == "subscriptionStart":
        return sorted(
            items,
            key=lambda item: (
                item.currentSubscription.currentPeriodStart
                if item.currentSubscription
                and item.currentSubscription.currentPeriodStart is not None
                else ""
            ),
            reverse=True,
        )
    return items


def _normalize_subscription_filter(value: str) -> str:
    mapping = {
        "订阅中": "active",
        "active": "active",
        "即将到期": "expiring_soon",
        "expiring_soon": "expiring_soon",
        "expiringsoon": "expiring_soon",
        "已过期": "expired",
        "expired": "expired",
    }
    return mapping.get(value.casefold(), value)


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _json_list(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    return []


def _json_list_dicts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _days_until(value: str | None) -> int | None:
    if value is None:
        return None
    delta = _parse_datetime(value) - datetime.now(timezone.utc)
    return max(delta.days, 0)


def _subscription_status(status: str, ends_at: str | None) -> str:
    if status in {"cancelled", "expired"}:
        return "expired"
    if ends_at is not None:
        days = _days_until(ends_at)
        if _parse_datetime(ends_at) <= datetime.now(timezone.utc):
            return "expired"
        if days is not None and days <= 14:
            return "expiring_soon"
    return "active"


def _subscription_status_label(status: str) -> str:
    return {
        "active": "订阅中",
        "expiring_soon": "即将到期",
        "expired": "已过期",
    }.get(status, status)


def _price_label(price_snapshot: dict[str, Any]) -> str | None:
    period = str(price_snapshot.get("billingPeriod") or "")
    amount = int(price_snapshot.get("amountCents") or 0)
    if period == "free":
        return "免费"
    if period == "sales":
        return "联系销售"
    suffix = {"monthly": " / 月", "yearly": " / 年"}.get(period, "")
    return f"¥{amount / 100:g}{suffix}"


def _billing_period_label(period: str | None) -> str:
    return {
        "free": "免费",
        "monthly": "月付",
        "yearly": "年付",
        "sales": "商务报价",
    }.get(str(period or ""), "")


def _percent(used: int, limit: int) -> float:
    if limit <= 0:
        return 0
    return round(min((used / limit) * 100, 100), 2)


def _usage_status(
    subscription: UserSubscriptionSummary | None,
    question_used: int,
    question_limit: int,
    token_used: int,
    token_limit: int,
) -> str:
    if subscription is not None and subscription.status == "expired":
        return "expired"
    if question_limit > 0 and question_used >= question_limit:
        return "question_exhausted"
    if token_limit > 0 and token_used >= token_limit:
        return "token_exhausted"
    if subscription is not None and subscription.status == "expiring_soon":
        return "expiring_soon"
    return "normal"


def _lifetime_usage(
    created_at: str, subscription: UserSubscriptionSummary | None
) -> UserLifetimeUsageSummary:
    start = _parse_datetime(created_at)
    usage_days = max((datetime.now(timezone.utc) - start).days + 1, 1)
    stopped = subscription is not None and subscription.status == "expired"
    return UserLifetimeUsageSummary(
        startDate=created_at,
        usageDays=usage_days,
        stopped=stopped,
    )


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
