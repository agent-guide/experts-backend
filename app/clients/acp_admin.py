from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.core.errors import ApiError

# Process-level session-token cache keyed by (base_url, username). The gateway admin plane issues
# in-memory session tokens (lost on gateway restart), so the token is reused across requests and
# re-minted only on a 401. A concurrent re-login at worst wastes one extra login, so no lock.
_token_cache: dict[tuple[str, str], str] = {}


class AcpAdminClient:
    """Client for the agent-gateway ACP admin plane (history replay).

    The admin plane lives at its own address (separate from the data plane) and authenticates via
    a username/password login that returns an in-memory Bearer session token. It exposes the ACP
    session list and per-session transcript, keyed by the gateway's ACP service id.
    """

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.acp_admin_base_url
        self.username = settings.acp_admin_username
        self.password = settings.acp_admin_password
        self.service_id = settings.acp_service_id

    def _ensure_configured(self) -> None:
        if not (self.base_url and self.username and self.password and self.service_id):
            raise ApiError(
                503,
                "ACP_ADMIN_UNCONFIGURED",
                "acp gateway admin plane is not configured",
            )

    @property
    def _cache_key(self) -> tuple[str, str]:
        return (self.base_url or "", self.username or "")

    async def _login(self, client: httpx.AsyncClient) -> str:
        response = await client.post(
            "/admin/auth/login",
            json={"username": self.username, "password": self.password},
        )
        if response.status_code >= 400:
            raise ApiError(
                response.status_code,
                "ACP_ADMIN_LOGIN_FAILED",
                "acp gateway admin login failed",
                {"statusCode": response.status_code, "body": response.text[:1000]},
            )
        token = (response.json() or {}).get("token")
        if not token:
            raise ApiError(502, "ACP_ADMIN_LOGIN_FAILED", "acp gateway admin login returned no token")
        _token_cache[self._cache_key] = token
        return token

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        self._ensure_configured()
        async with httpx.AsyncClient(base_url=self.base_url, timeout=120) as client:
            token = _token_cache.get(self._cache_key) or await self._login(client)
            response = await client.get(
                path, params=params, headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 401:
                # Cached session expired (e.g. gateway restart); re-login once and retry.
                token = await self._login(client)
                response = await client.get(
                    path, params=params, headers={"Authorization": f"Bearer {token}"}
                )
            if response.status_code >= 400:
                raise ApiError(
                    response.status_code,
                    "ACP_ADMIN_ERROR",
                    "acp gateway admin request failed",
                    {"statusCode": response.status_code, "body": response.text[:1000]},
                )
            return response.json() if response.content else None

    async def list_sessions(self, *, cwd: str | None = None, cursor: str | None = None) -> Any:
        params: dict[str, str] = {}
        if cwd:
            params["cwd"] = cwd
        if cursor:
            params["cursor"] = cursor
        path = f"/admin/acp/services/{quote(self.service_id or '', safe='')}/sessions"
        return await self._get(path, params=params or None)

    async def get_transcript(self, *, session_id: str, cwd: str | None = None) -> Any:
        params: dict[str, str] = {}
        if cwd:
            params["cwd"] = cwd
        path = (
            f"/admin/acp/services/{quote(self.service_id or '', safe='')}"
            f"/sessions/{quote(session_id, safe='')}/transcript"
        )
        return await self._get(path, params=params or None)
