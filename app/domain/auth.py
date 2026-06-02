from enum import StrEnum

from pydantic import BaseModel, EmailStr


class Role(StrEnum):
    USER = "User"
    ADMIN = "Admin"
    EXPERT = "Expert"
    OPS = "Ops"


Permission = str


def role_permissions(role: Role) -> set[Permission]:
    if role == Role.USER:
        return {
            "kb:create",
            "kb:read",
            "kb:update",
            "kb:delete",
            "doc:upload",
            "doc:delete",
            "chat:ask",
        }
    if role == Role.EXPERT:
        return {
            "kb:create",
            "kb:read",
            "kb:update",
            "kb:delete",
            "kb:publish_official",
            "doc:upload",
            "doc:delete",
            "doc:reindex",
            "chat:ask",
            "skill:publish",
        }
    if role == Role.OPS:
        return {
            "kb:read",
            "doc:reindex",
            "user:manage",
            "role:grant",
            "tenant:manage",
            "system:ops",
        }
    if role == Role.ADMIN:
        return {
            "kb:create",
            "kb:read",
            "kb:update",
            "kb:delete",
            "kb:publish_official",
            "doc:upload",
            "doc:delete",
            "doc:reindex",
            "chat:ask",
            "user:manage",
            "role:grant",
            "tenant:manage",
            "skill:publish",
        }
    return set()


class Principal(BaseModel):
    user_id: str
    tenant_id: str
    email: str
    roles: list[Role]
    permissions: list[Permission]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refreshToken: str


class LogoutRequest(BaseModel):
    refreshToken: str


class AdminActivateRequest(BaseModel):
    token: str
    newPassword: str
    name: str | None = None


class GrantRoleRequest(BaseModel):
    role: Role


class AdminUser(BaseModel):
    id: str
    tenantId: str
    email: str
    name: str
    status: str
    roles: list[Role]
    permissions: list[Permission]
    createdAt: str
    updatedAt: str


class ListUsersResponse(BaseModel):
    items: list[AdminUser]
