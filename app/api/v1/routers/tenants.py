from fastapi import APIRouter, Depends

from app.api.deps import get_database, require_platform_permission
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.tenants import (
    AddTenantMemberRequest,
    CreateTenantRequest,
    Tenant,
    TenantListResponse,
    TenantMember,
    TenantMemberListResponse,
    UpdateTenantMemberRequest,
    UpdateTenantRequest,
    UpdateTenantStatusRequest,
)
from app.services.tenant_service import TenantService

router = APIRouter()


@router.get("", response_model=TenantListResponse)
async def list_tenants(
    principal: Principal = Depends(require_platform_permission("platform:tenant_manage")),
    connection: DatabaseConnection = Depends(get_database),
) -> TenantListResponse:
    return TenantListResponse(items=TenantService(connection).list())


@router.post("", response_model=Tenant, status_code=201)
async def create_tenant(
    body: CreateTenantRequest,
    principal: Principal = Depends(require_platform_permission("platform:tenant_manage")),
    connection: DatabaseConnection = Depends(get_database),
) -> Tenant:
    return TenantService(connection).create(body)


@router.get("/{tenant_id}", response_model=Tenant)
async def get_tenant(
    tenant_id: str,
    principal: Principal = Depends(require_platform_permission("platform:tenant_manage")),
    connection: DatabaseConnection = Depends(get_database),
) -> Tenant:
    return TenantService(connection).get(tenant_id)


@router.patch("/{tenant_id}", response_model=Tenant)
async def update_tenant(
    tenant_id: str,
    body: UpdateTenantRequest,
    principal: Principal = Depends(require_platform_permission("platform:tenant_manage")),
    connection: DatabaseConnection = Depends(get_database),
) -> Tenant:
    return TenantService(connection).update(tenant_id, body)


@router.patch("/{tenant_id}/status", response_model=Tenant)
async def update_tenant_status(
    tenant_id: str,
    body: UpdateTenantStatusRequest,
    principal: Principal = Depends(require_platform_permission("platform:tenant_manage")),
    connection: DatabaseConnection = Depends(get_database),
) -> Tenant:
    return TenantService(connection).update_status(tenant_id, body.status)


@router.get("/{tenant_id}/members", response_model=TenantMemberListResponse)
async def list_tenant_members(
    tenant_id: str,
    principal: Principal = Depends(require_platform_permission("platform:tenant_manage")),
    connection: DatabaseConnection = Depends(get_database),
) -> TenantMemberListResponse:
    return TenantMemberListResponse(items=TenantService(connection).list_members(tenant_id))


@router.post("/{tenant_id}/members", response_model=TenantMember, status_code=201)
async def add_tenant_member(
    tenant_id: str,
    body: AddTenantMemberRequest,
    principal: Principal = Depends(require_platform_permission("platform:tenant_manage")),
    connection: DatabaseConnection = Depends(get_database),
) -> TenantMember:
    return TenantService(connection).add_member(tenant_id, body)


@router.patch("/{tenant_id}/members/{user_id}", response_model=TenantMember)
async def update_tenant_member(
    tenant_id: str,
    user_id: str,
    body: UpdateTenantMemberRequest,
    principal: Principal = Depends(require_platform_permission("platform:tenant_manage")),
    connection: DatabaseConnection = Depends(get_database),
) -> TenantMember:
    return TenantService(connection).update_member(tenant_id, user_id, body)


@router.delete("/{tenant_id}/members/{user_id}", status_code=204)
async def remove_tenant_member(
    tenant_id: str,
    user_id: str,
    principal: Principal = Depends(require_platform_permission("platform:tenant_manage")),
    connection: DatabaseConnection = Depends(get_database),
) -> None:
    TenantService(connection).remove_member(tenant_id, user_id)
    return None
