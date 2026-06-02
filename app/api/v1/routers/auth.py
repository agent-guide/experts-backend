from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service
from app.domain.auth import (
    AdminActivateRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, auth: AuthService = Depends(get_auth_service)) -> dict:
    return auth.register(body.email, body.password, body.name)


@router.post("/login")
async def login(body: LoginRequest, auth: AuthService = Depends(get_auth_service)) -> dict:
    return auth.login(body.email, body.password)


@router.post("/refresh")
async def refresh(body: RefreshRequest, auth: AuthService = Depends(get_auth_service)) -> dict:
    return auth.refresh(body.refreshToken)


@router.post("/logout", status_code=204)
async def logout(body: LogoutRequest, auth: AuthService = Depends(get_auth_service)) -> None:
    auth.logout(body.refreshToken)
    return None


@router.post("/admin/activate")
async def activate_admin(
    body: AdminActivateRequest,
    auth: AuthService = Depends(get_auth_service),
) -> dict:
    return auth.activate_admin(body.token, body.newPassword, body.name)
