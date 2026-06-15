from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service, require_platform_permission
from app.domain.auth import (
    CreatePlatformUserRequest,
    CreatePlatformUserResponse,
    ListManagedUsersResponse,
    ListUserTenantsResponse,
    ListUsersResponse,
    PlatformUserActivateRequest,
    Principal,
    RegisterRequest,
    UpdateUserRequest,
    UpdateUserStatusRequest,
    UserDetail,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, auth: AuthService = Depends(get_auth_service)) -> dict:
    return auth.register(body.email, body.password, body.name)


@router.get("", response_model=ListManagedUsersResponse)
async def list_users(
    principal: Principal = Depends(require_platform_permission("platform:user_manage")),
    auth: AuthService = Depends(get_auth_service),
) -> ListManagedUsersResponse:
    return ListManagedUsersResponse(items=auth.list_managed_users())


@router.post("/platform/activate")
async def activate_platform_user(
    body: PlatformUserActivateRequest,
    auth: AuthService = Depends(get_auth_service),
) -> dict:
    return auth.activate_platform_user(body.token, body.newPassword, body.name)


@router.get("/platform", response_model=ListUsersResponse)
async def list_platform_users(
    principal: Principal = Depends(require_platform_permission("platform:user_manage")),
    auth: AuthService = Depends(get_auth_service),
) -> ListUsersResponse:
    return ListUsersResponse(items=auth.list_platform_users())


@router.post("/platform", response_model=CreatePlatformUserResponse, status_code=201)
async def create_platform_user(
    body: CreatePlatformUserRequest,
    principal: Principal = Depends(require_platform_permission("platform:user_manage")),
    auth: AuthService = Depends(get_auth_service),
) -> CreatePlatformUserResponse:
    return auth.create_platform_user(principal.user_id, body.email, body.name, body.roles)


@router.get("/{user_id}/tenants", response_model=ListUserTenantsResponse)
async def list_user_tenants(
    user_id: str,
    principal: Principal = Depends(require_platform_permission("platform:user_manage")),
    auth: AuthService = Depends(get_auth_service),
) -> ListUserTenantsResponse:
    return ListUserTenantsResponse(items=auth.list_user_tenants(user_id))


@router.get("/{user_id}", response_model=UserDetail)
async def get_user(
    user_id: str,
    principal: Principal = Depends(require_platform_permission("platform:user_manage")),
    auth: AuthService = Depends(get_auth_service),
) -> UserDetail:
    return auth.get_managed_user(user_id)


@router.patch("/{user_id}", response_model=UserDetail)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    principal: Principal = Depends(require_platform_permission("platform:user_manage")),
    auth: AuthService = Depends(get_auth_service),
) -> UserDetail:
    return auth.update_user(user_id, name=body.name)


@router.patch("/{user_id}/status", response_model=UserDetail)
async def update_user_status(
    user_id: str,
    body: UpdateUserStatusRequest,
    principal: Principal = Depends(require_platform_permission("platform:user_manage")),
    auth: AuthService = Depends(get_auth_service),
) -> UserDetail:
    return auth.update_user_status(user_id, status=body.status)
