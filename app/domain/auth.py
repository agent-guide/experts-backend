from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field


class TenantRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class PlatformRole(StrEnum):
    ADMIN = "admin"
    EXPERT = "expert"
    OPERATOR = "operator"


Permission = str


def tenant_role_permissions(role: TenantRole) -> set[Permission]:
    if role == TenantRole.MEMBER:
        return {
            "kb:create",
            "kb:read",
            "kb:update",
            "kb:delete",
            "doc:upload",
            "doc:delete",
            "chat:ask",
        }
    if role == TenantRole.ADMIN:
        return {
            "kb:create",
            "kb:read",
            "kb:update",
            "kb:delete",
            "doc:upload",
            "doc:delete",
            "doc:reindex",
            "chat:ask",
            "tenant:user_manage",
            "tenant:role_grant",
            "tenant:manage",
        }
    return set()


def platform_role_permissions(role: PlatformRole) -> set[Permission]:
    if role == PlatformRole.EXPERT:
        return {
            "platform:kb_publish_official",
            "skill:write",
        }
    if role == PlatformRole.OPERATOR:
        return {
            "platform:user_manage",
            "platform:role_grant",
            "system:ops",
        }
    if role == PlatformRole.ADMIN:
        return {
            "platform:user_manage",
            "platform:role_grant",
            "platform:tenant_manage",
            "platform:kb_publish_official",
            "skill:write",
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


class GrantTenantRoleRequest(BaseModel):
    role: TenantRole


class GrantPlatformRoleRequest(BaseModel):
    role: PlatformRole


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
