from collections.abc import Iterator

from fastapi import Depends, Header

from app.clients.acp_gateway import AcpGatewayClient
from app.clients.pageindex import PageIndexClient
from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.security import decode_access_token
from app.db import DatabaseConnection, open_database_connection
from app.domain.auth import Principal
from app.services.auth_service import AuthService
from app.services.object_store import ObjectStore, create_object_store
from app.services.skill_storage import SkillStorage, create_skill_storage


def get_auth_service(settings: Settings = Depends(get_settings)) -> AuthService:
    return AuthService(settings)


def get_pageindex_client(settings: Settings = Depends(get_settings)) -> PageIndexClient:
    return PageIndexClient(settings)


def get_acp_gateway_client(settings: Settings = Depends(get_settings)) -> AcpGatewayClient:
    return AcpGatewayClient(settings)


def get_skill_storage(settings: Settings = Depends(get_settings)) -> SkillStorage:
    return create_skill_storage(settings)


def get_object_store(settings: Settings = Depends(get_settings)) -> ObjectStore:
    return create_object_store(settings)


def get_database(settings: Settings = Depends(get_settings)) -> Iterator[DatabaseConnection]:
    with open_database_connection(settings) as connection:
        yield connection


async def require_principal(
    authorization: str | None = Header(default=None, alias="Authorization"),
    settings: Settings = Depends(get_settings),
) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError(401, "AUTH_UNAUTHORIZED", "Missing bearer token")
    token_principal = decode_access_token(settings, authorization.removeprefix("Bearer ").strip())
    return AuthService(settings).current_principal(token_principal)


async def require_tenant_principal(
    principal: Principal = Depends(require_principal),
    tenant_id: str | None = Header(default=None, alias="x-tenant-id"),
) -> Principal:
    if not tenant_id:
        raise ApiError(401, "AUTH_UNAUTHORIZED", "Missing x-tenant-id")
    if principal.active_tenant_id != tenant_id:
        raise ApiError(403, "AUTH_FORBIDDEN", "Tenant mismatch")
    return principal


async def require_platform_principal(principal: Principal = Depends(require_principal)) -> Principal:
    if not principal.platform_roles:
        raise ApiError(403, "AUTH_FORBIDDEN", "Missing platform role")
    return principal


def require_tenant_permission(permission: str):
    async def dependency(principal: Principal = Depends(require_tenant_principal)) -> Principal:
        if permission not in principal.tenant_permissions:
            raise ApiError(403, "AUTH_FORBIDDEN", f"Missing permission: {permission}")
        return principal

    return dependency


def require_platform_permission(permission: str):
    async def dependency(principal: Principal = Depends(require_platform_principal)) -> Principal:
        if permission not in principal.platform_permissions:
            raise ApiError(403, "AUTH_FORBIDDEN", f"Missing permission: {permission}")
        return principal

    return dependency
