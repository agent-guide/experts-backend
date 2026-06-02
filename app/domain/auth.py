from enum import StrEnum

from pydantic import BaseModel, EmailStr


class Role(StrEnum):
    USER = "User"
    ADMIN = "Admin"
    EXPERT = "Expert"
    OPS = "Ops"


Permission = str


def role_permissions(role: Role) -> set[Permission]:
    base = {"chat:ask", "kb:read"}
    if role == Role.USER:
        return base | {"kb:create", "kb:update", "doc:upload", "doc:delete", "doc:reindex"}
    if role == Role.EXPERT:
        return base | {
            "kb:create",
            "kb:update",
            "kb:delete",
            "doc:upload",
            "doc:delete",
            "doc:reindex",
            "skill:publish",
        }
    if role == Role.OPS:
        return base | {"system:ops"}
    if role == Role.ADMIN:
        return base | {
            "kb:create",
            "kb:update",
            "kb:delete",
            "kb:publish_official",
            "doc:upload",
            "doc:delete",
            "doc:reindex",
            "role:grant",
            "system:ops",
            "skill:publish",
        }
    return base


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


class GrantRoleRequest(BaseModel):
    role: Role
