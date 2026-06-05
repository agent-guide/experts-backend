from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.auth import TenantRole
from app.domain.tenants import (
    AddTenantMemberRequest,
    CreateTenantRequest,
    Tenant,
    TenantMember,
    UpdateTenantMemberRequest,
    UpdateTenantRequest,
)
from app.services._sql import execute, fetch_all, fetch_one, is_unique_violation, rowcount


class TenantService:
    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection

    def list(self) -> list[Tenant]:
        rows = fetch_all(
            self.connection,
            """
            select
              t.id,
              t.type,
              t.name,
              t.slug,
              t.owner_user_id,
              owner.name as owner_user_name,
              t.status,
              t.created_at,
              t.updated_at,
              count(tm.id) as member_count
            from tenants t
            left join users owner on owner.id = t.owner_user_id
            left join tenant_members tm on tm.tenant_id = t.id
            group by
              t.id, t.type, t.name, t.slug, t.owner_user_id, owner.name,
              t.status, t.created_at, t.updated_at
            order by t.created_at desc, t.id asc
            """,
        )
        return [_map_tenant(row) for row in rows]

    def get(self, tenant_id: str) -> Tenant:
        row = self._tenant_row(tenant_id)
        if not row:
            raise ApiError(404, "TENANT_NOT_FOUND", "Tenant not found")
        return _map_tenant(row)

    def create(self, request: CreateTenantRequest) -> Tenant:
        owner = self._require_user(request.ownerUserId)
        tenant_id = f"tenant_{uuid4().hex}"
        slug = request.slug or _tenant_slug(request.name)
        try:
            execute(
                self.connection,
                """
                insert into tenants (id, type, name, slug, owner_user_id, status)
                values (?, 'team', ?, ?, ?, 'active')
                """,
                (tenant_id, request.name, slug, owner["id"]),
            )
            self._upsert_member(tenant_id, str(owner["id"]), TenantRole.ADMIN)
            self.connection.commit()
        except Exception as exc:
            if is_unique_violation(exc):
                raise ApiError(409, "TENANT_SLUG_EXISTS", "Tenant slug already exists") from exc
            raise
        return self.get(tenant_id)

    def update(self, tenant_id: str, request: UpdateTenantRequest) -> Tenant:
        current = self.get(tenant_id)
        next_name = request.name if request.name is not None else current.name
        next_slug = request.slug if request.slug is not None else current.slug
        next_owner_id = (
            request.ownerUserId if request.ownerUserId is not None else current.ownerUserId
        )

        if next_owner_id is not None:
            self._require_user(next_owner_id)

        try:
            execute(
                self.connection,
                """
                update tenants
                set name = ?, slug = ?, owner_user_id = ?, updated_at = CURRENT_TIMESTAMP
                where id = ?
                """,
                (next_name, next_slug, next_owner_id, tenant_id),
            )
            if next_owner_id is not None and next_owner_id != current.ownerUserId:
                self._upsert_member(tenant_id, next_owner_id, TenantRole.ADMIN)
            self.connection.commit()
        except Exception as exc:
            if is_unique_violation(exc):
                raise ApiError(409, "TENANT_SLUG_EXISTS", "Tenant slug already exists") from exc
            raise
        return self.get(tenant_id)

    def update_status(self, tenant_id: str, status: str) -> Tenant:
        self.get(tenant_id)
        execute(
            self.connection,
            """
            update tenants
            set status = ?, updated_at = CURRENT_TIMESTAMP
            where id = ?
            """,
            (status, tenant_id),
        )
        self.connection.commit()
        return self.get(tenant_id)

    def list_members(self, tenant_id: str) -> list[TenantMember]:
        self.get(tenant_id)
        rows = fetch_all(
            self.connection,
            """
            select
              u.id as user_id,
              u.email,
              u.name,
              u.status,
              tm.role,
              tm.created_at as joined_at
            from tenant_members tm
            inner join users u on u.id = tm.user_id
            where tm.tenant_id = ?
            order by tm.created_at desc, u.id asc
            """,
            (tenant_id,),
        )
        return [_map_member(row) for row in rows]

    def add_member(self, tenant_id: str, request: AddTenantMemberRequest) -> TenantMember:
        self.get(tenant_id)
        self._require_user(request.userId)
        self._upsert_member(tenant_id, request.userId, request.role)
        self.connection.commit()
        return self._require_member(tenant_id, request.userId)

    def update_member(
        self, tenant_id: str, user_id: str, request: UpdateTenantMemberRequest
    ) -> TenantMember:
        self.get(tenant_id)
        current = self._require_member(tenant_id, user_id)
        if (
            current.role == TenantRole.ADMIN
            and request.role != TenantRole.ADMIN
            and self._count_tenant_admins(tenant_id) <= 1
        ):
            raise ApiError(409, "TENANT_LAST_ADMIN", "Cannot demote the last tenant admin")
        self._upsert_member(tenant_id, user_id, request.role)
        self.connection.commit()
        return self._require_member(tenant_id, user_id)

    def remove_member(self, tenant_id: str, user_id: str) -> None:
        self.get(tenant_id)
        current = self._require_member(tenant_id, user_id)
        if current.role == TenantRole.ADMIN and self._count_tenant_admins(tenant_id) <= 1:
            raise ApiError(409, "TENANT_LAST_ADMIN", "Cannot remove the last tenant admin")
        cursor = execute(
            self.connection,
            "delete from tenant_members where tenant_id = ? and user_id = ?",
            (tenant_id, user_id),
        )
        if rowcount(cursor) <= 0:
            raise ApiError(404, "MEMBER_NOT_FOUND", "User is not a member of this tenant")
        self.connection.commit()

    def _tenant_row(self, tenant_id: str) -> dict[str, Any] | None:
        return fetch_one(
            self.connection,
            """
            select
              t.id,
              t.type,
              t.name,
              t.slug,
              t.owner_user_id,
              owner.name as owner_user_name,
              t.status,
              t.created_at,
              t.updated_at,
              count(tm.id) as member_count
            from tenants t
            left join users owner on owner.id = t.owner_user_id
            left join tenant_members tm on tm.tenant_id = t.id
            where t.id = ?
            group by
              t.id, t.type, t.name, t.slug, t.owner_user_id, owner.name,
              t.status, t.created_at, t.updated_at
            limit 1
            """,
            (tenant_id,),
        )

    def _require_user(self, user_id: str) -> dict[str, Any]:
        row = fetch_one(
            self.connection,
            "select id from users where id = ? limit 1",
            (user_id,),
        )
        if not row:
            raise ApiError(404, "USER_NOT_FOUND", "User not found")
        return row

    def _require_member(self, tenant_id: str, user_id: str) -> TenantMember:
        row = fetch_one(
            self.connection,
            """
            select
              u.id as user_id,
              u.email,
              u.name,
              u.status,
              tm.role,
              tm.created_at as joined_at
            from tenant_members tm
            inner join users u on u.id = tm.user_id
            where tm.tenant_id = ? and tm.user_id = ?
            limit 1
            """,
            (tenant_id, user_id),
        )
        if not row:
            raise ApiError(404, "MEMBER_NOT_FOUND", "User is not a member of this tenant")
        return _map_member(row)

    def _upsert_member(self, tenant_id: str, user_id: str, role: TenantRole) -> None:
        execute(
            self.connection,
            """
            insert into tenant_members (id, tenant_id, user_id, role)
            values (?, ?, ?, ?)
            on conflict (tenant_id, user_id) do update
            set role = excluded.role,
                updated_at = CURRENT_TIMESTAMP
            """,
            (f"member_{uuid4().hex}", tenant_id, user_id, role.value),
        )

    def _count_tenant_admins(self, tenant_id: str) -> int:
        row = fetch_one(
            self.connection,
            "select count(*) as count from tenant_members where tenant_id = ? and role = ?",
            (tenant_id, TenantRole.ADMIN.value),
        )
        return int(row["count"]) if row else 0


def _map_tenant(row: dict[str, Any]) -> Tenant:
    return Tenant(
        id=str(row["id"]),
        type=str(row["type"]),
        name=str(row["name"]),
        slug=str(row["slug"]),
        ownerUserId=str(row["owner_user_id"]) if row["owner_user_id"] is not None else None,
        ownerUserName=(
            str(row["owner_user_name"]) if row.get("owner_user_name") is not None else None
        ),
        status=str(row["status"]),
        memberCount=int(row["member_count"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _map_member(row: dict[str, Any]) -> TenantMember:
    return TenantMember(
        userId=str(row["user_id"]),
        email=str(row["email"]),
        name=str(row["name"]),
        status=str(row["status"]),
        role=TenantRole(str(row["role"])),
        joinedAt=str(row["joined_at"]),
    )


def _tenant_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{slug or 'tenant'}-{uuid4().hex[:8]}"
