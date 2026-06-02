import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import Settings
from app.core.errors import ApiError
from app.domain.auth import Principal, Role, role_permissions


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = password_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 120_000
    )
    return hmac.compare_digest(actual, expected)


def _encode(settings: Settings, payload: dict[str, Any], ttl_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        **payload,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def issue_token_pair(settings: Settings, principal: Principal) -> dict[str, object]:
    access = _encode(
        settings,
        {
            "sub": principal.user_id,
            "tenantId": principal.tenant_id,
            "email": principal.email,
            "roles": principal.roles,
            "permissions": principal.permissions,
            "type": "access",
        },
        settings.access_token_ttl_seconds,
    )
    refresh = _encode(
        settings,
        {
            "sub": principal.user_id,
            "tenantId": principal.tenant_id,
            "type": "refresh",
        },
        settings.refresh_token_ttl_seconds,
    )
    return {
        "accessToken": access,
        "refreshToken": refresh,
        "expiresInSeconds": settings.access_token_ttl_seconds,
    }


def decode_access_token(settings: Settings, token: str) -> Principal:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    except jwt.PyJWTError as exc:
        raise ApiError(401, "AUTH_UNAUTHORIZED", "Invalid access token") from exc

    if claims.get("type") != "access":
        raise ApiError(401, "AUTH_UNAUTHORIZED", "Invalid access token type")

    roles = [Role(role) for role in claims.get("roles", [])]
    permissions = sorted({perm for role in roles for perm in role_permissions(role)})
    return Principal(
        user_id=str(claims["sub"]),
        tenant_id=str(claims["tenantId"]),
        email=str(claims.get("email", "")),
        roles=roles,
        permissions=permissions,
    )
