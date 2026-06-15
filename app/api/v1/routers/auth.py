from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service
from app.domain.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login")
async def login(body: LoginRequest, auth: AuthService = Depends(get_auth_service)) -> dict:
    return auth.login(body.email, body.password, body.tenantId)


@router.post("/refresh")
async def refresh(body: RefreshRequest, auth: AuthService = Depends(get_auth_service)) -> dict:
    return auth.refresh(body.refreshToken, body.tenantId)


@router.post("/logout", status_code=204)
async def logout(body: LogoutRequest, auth: AuthService = Depends(get_auth_service)) -> None:
    auth.logout(body.refreshToken)
    return None
