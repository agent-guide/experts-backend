from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class TenantRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class PlatformRole(StrEnum):
    ADMIN = "admin"
    EXPERT = "expert"
    OPERATOR = "operator"


Permission = str
UserStatus = Literal["pending_activation", "active", "disabled"]
MutableUserStatus = Literal["active", "disabled"]


def tenant_role_permissions(role: TenantRole) -> set[Permission]:
    # Tenant roles only consume platform-provided capabilities (via chat). Knowledge
    # bases, documents and skills are authored on the platform side, so tenant roles
    # hold no kb:* / doc:* / skill:* permissions.
    if role == TenantRole.MEMBER:
        return {
            "chat:ask",
        }
    if role == TenantRole.ADMIN:
        return {
            "chat:ask",
            "tenant:user_manage",
            "tenant:role_grant",
            "tenant:manage",
        }
    return set()


def platform_role_permissions(role: PlatformRole) -> set[Permission]:
    # Platform-provided capabilities (knowledge bases, documents, skills) are authored by
    # `expert`. `operator` governs tenant users and capability entitlement: it can read
    # capabilities and grant their use, but cannot author them.
    if role == PlatformRole.EXPERT:
        return {
            "kb:create",
            "kb:read",
            "kb:update",
            "kb:delete",
            "kb:build",
            "doc:create",
            "doc:read",
            "doc:update",
            "doc:delete",
            "skill:read",
            "skill:write",
            "expert:read",
            "expert:write",
        }
    if role == PlatformRole.OPERATOR:
        return {
            "platform:user_manage",
            "platform:role_grant",
            "platform:entitlement_grant",
            "system:ops",
            "kb:read",
            "skill:read",
            "expert:read",
        }
    if role == PlatformRole.ADMIN:
        return {
            "platform:user_manage",
            "platform:role_grant",
            "platform:entitlement_grant",
            "platform:tenant_manage",
            "kb:create",
            "kb:read",
            "kb:update",
            "kb:delete",
            "kb:build",
            "doc:create",
            "doc:read",
            "doc:update",
            "doc:delete",
            "skill:read",
            "skill:write",
            "expert:read",
            "expert:write",
            "system:ops",
        }
    return set()


class Principal(BaseModel):
    user_id: str
    email: str
    active_tenant_id: str | None = None
    tenant_roles: list[TenantRole] = []
    tenant_permissions: list[Permission] = []
    platform_roles: list[PlatformRole] = []
    platform_permissions: list[Permission] = []


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenantId: str | None = None


class RefreshRequest(BaseModel):
    refreshToken: str
    tenantId: str | None = None


class LogoutRequest(BaseModel):
    refreshToken: str


class PlatformUserActivateRequest(BaseModel):
    token: str
    newPassword: str
    name: str | None = None


class CreatePlatformUserRequest(BaseModel):
    email: EmailStr
    name: str
    roles: list[PlatformRole] = Field(default_factory=lambda: [PlatformRole.EXPERT])


class CreatePlatformUserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str
    status: str
    platformRoles: list[PlatformRole]
    activationToken: str
    activationExpiresAt: str


class UpdateUserRequest(BaseModel):
    name: str | None = None


class UpdateUserStatusRequest(BaseModel):
    status: MutableUserStatus


class GrantTenantRoleRequest(BaseModel):
    role: TenantRole


class GrantPlatformRoleRequest(BaseModel):
    role: PlatformRole


class PlatformRoleSummary(BaseModel):
    role: PlatformRole
    name: str
    permissions: list[Permission]


class ListPlatformRolesResponse(BaseModel):
    items: list[PlatformRoleSummary]


class UserTenantSummary(BaseModel):
    id: str
    name: str
    type: str
    slug: str
    status: str
    role: TenantRole
    joinedAt: str


class UserSummary(BaseModel):
    id: str
    email: str
    name: str
    status: UserStatus
    platformRoles: list[PlatformRole]
    tenantCount: int
    createdAt: str
    updatedAt: str


class UserDetail(BaseModel):
    id: str
    email: str
    name: str
    status: UserStatus
    platformRoles: list[PlatformRole]
    platformPermissions: list[Permission]
    tenants: list[UserTenantSummary]
    createdAt: str
    updatedAt: str


class ListManagedUsersResponse(BaseModel):
    items: list[UserSummary]


class ListUserTenantsResponse(BaseModel):
    items: list[UserTenantSummary]


class UserAccessSummary(BaseModel):
    id: str
    email: str
    name: str
    status: str
    activeTenantId: str | None = None
    tenantRoles: list[TenantRole]
    tenantPermissions: list[Permission]
    platformRoles: list[PlatformRole]
    platformPermissions: list[Permission]
    createdAt: str
    updatedAt: str


class ListUsersResponse(BaseModel):
    items: list[UserAccessSummary]
