from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service
from app.core.errors import ApiError
from app.domain.auth import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, auth: AuthService = Depends(get_auth_service)) -> dict:
    return auth.register(body.email, body.password, body.name)


@router.post("/login")
async def login(body: LoginRequest, auth: AuthService = Depends(get_auth_service)) -> dict:
    return auth.login(body.email, body.password)


@router.post("/refresh")
async def refresh(_: RefreshRequest) -> dict:
    raise ApiError(501, "NOT_IMPLEMENTED", "Refresh token rotation will be backed by persistent auth storage")


@router.post("/logout", status_code=204)
async def logout(_: LogoutRequest) -> None:
    return None


@router.post("/admin/activate")
async def activate_admin() -> dict:
    raise ApiError(501, "NOT_IMPLEMENTED", "Admin activation token flow is not implemented yet")
