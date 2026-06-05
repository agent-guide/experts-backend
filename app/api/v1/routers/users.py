from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service, require_platform_permission
from app.domain.auth import (
    CreatePlatformUserRequest,
    CreatePlatformUserResponse,
    ListUsersResponse,
    PlatformUserActivateRequest,
    Principal,
    RegisterRequest,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, auth: AuthService = Depends(get_auth_service)) -> dict:
    return auth.register(body.email, body.password, body.name)


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
