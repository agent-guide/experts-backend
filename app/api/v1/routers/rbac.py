from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service, require_platform_permission, require_tenant_permission
from app.domain.auth import (
    GrantPlatformRoleRequest,
    GrantTenantRoleRequest,
    ListUsersResponse,
    PlatformRole,
    Principal,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.get("/tenant/users", response_model=ListUsersResponse)
async def list_tenant_users(
    principal: Principal = Depends(require_tenant_permission("tenant:user_manage")),
    auth: AuthService = Depends(get_auth_service),
) -> ListUsersResponse:
    return ListUsersResponse(items=auth.list_tenant_users(str(principal.active_tenant_id)))


@router.post("/tenant/users/{user_id}/roles", status_code=204)
async def grant_tenant_role(
    user_id: str,
    body: GrantTenantRoleRequest,
    principal: Principal = Depends(require_tenant_permission("tenant:role_grant")),
    auth: AuthService = Depends(get_auth_service),
) -> None:
    auth.grant_tenant_role(str(principal.active_tenant_id), principal.user_id, user_id, body.role)
    return None


@router.delete("/tenant/users/{user_id}", status_code=204)
async def revoke_tenant_member(
    user_id: str,
    principal: Principal = Depends(require_tenant_permission("tenant:user_manage")),
    auth: AuthService = Depends(get_auth_service),
) -> None:
    auth.revoke_tenant_member(str(principal.active_tenant_id), principal.user_id, user_id)
    return None


@router.post("/platform/users/{user_id}/roles", status_code=204)
async def grant_platform_role(
    user_id: str,
    body: GrantPlatformRoleRequest,
    principal: Principal = Depends(require_platform_permission("platform:role_grant")),
    auth: AuthService = Depends(get_auth_service),
) -> None:
    auth.grant_platform_role(principal.user_id, user_id, body.role)
    return None


@router.delete("/platform/users/{user_id}/roles/{role}", status_code=204)
async def revoke_platform_role(
    user_id: str,
    role: PlatformRole,
    principal: Principal = Depends(require_platform_permission("platform:role_grant")),
    auth: AuthService = Depends(get_auth_service),
) -> None:
    auth.revoke_platform_role(principal.user_id, user_id, role)
    return None
