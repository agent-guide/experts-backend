from collections.abc import Iterator

from fastapi import Depends, Header

from app.clients.ngent import NgentClient
from app.clients.pageindex import PageIndexClient
from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.security import decode_access_token
from app.db import DatabaseConnection, open_database_connection
from app.domain.auth import Principal
from app.services.auth_service import AuthService
from app.services.skill_storage import SkillStorage, create_skill_storage


def get_auth_service(settings: Settings = Depends(get_settings)) -> AuthService:
    return AuthService(settings)


def get_pageindex_client(settings: Settings = get_settings()) -> PageIndexClient:
    return PageIndexClient(settings)


def get_ngent_client(settings: Settings = get_settings()) -> NgentClient:
    return NgentClient(settings)


def get_skill_storage(settings: Settings = Depends(get_settings)) -> SkillStorage:
    return create_skill_storage(settings)


def get_database(settings: Settings = Depends(get_settings)) -> Iterator[DatabaseConnection]:
    with open_database_connection(settings) as connection:
        yield connection


async def require_principal(
    authorization: str | None = Header(default=None, alias="Authorization"),
    tenant_id: str | None = Header(default=None, alias="x-tenant-id"),
    settings: Settings = Depends(get_settings),
) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError(401, "AUTH_UNAUTHORIZED", "Missing bearer token")
    if not tenant_id:
        raise ApiError(401, "AUTH_UNAUTHORIZED", "Missing x-tenant-id")
    principal = decode_access_token(settings, authorization.removeprefix("Bearer ").strip())
    if principal.tenant_id != tenant_id:
        raise ApiError(403, "AUTH_FORBIDDEN", "Tenant mismatch")
    return principal


def require_permission(permission: str):
    async def dependency(principal: Principal = Depends(require_principal)) -> Principal:
        if permission not in principal.permissions:
            raise ApiError(403, "AUTH_FORBIDDEN", f"Missing permission: {permission}")
        return principal

    return dependency
