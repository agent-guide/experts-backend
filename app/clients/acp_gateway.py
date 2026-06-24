from pathlib import Path
import posixpath
from typing import Any, AsyncIterator
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.core.errors import ApiError


class AcpGatewayClient:
    """Client for the agent-gateway ACP data plane.

    The ACP data plane exposes routed endpoints under a configured path prefix:
      - POST {prefix}/turn       -> SSE stream (events: session, delta, permission, done, error)
      - POST {prefix}/permission -> answers one in-flight interactive permission request
      - GET  {prefix}/sessions   -> list materialized ACP sessions (history replay)
      - GET  {prefix}/sessions/{id}/transcript -> coalesced session transcript
    All are route-scoped and authenticated by the route's VirtualKey, so history
    replay no longer needs the gateway admin plane. There is no server-side
    thread/turn lifecycle: `thread_id` is caller-owned and `session_id` is assigned
    by the agent and surfaced via the first `session` event. The local DB stays the
    system of record; this client only drives compute.
    """

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.acp_gateway_base_url
        self.route_prefix = settings.acp_route_prefix.rstrip("/")
        self.search_route_prefix = (
            settings.acp_search_route_prefix.rstrip("/")
            if settings.acp_search_route_prefix
            else None
        )
        self.auth_token = settings.acp_auth_token
        self.client_id = settings.acp_client_id
        self.default_model = settings.acp_default_model
        self.default_cwd = settings.acp_default_cwd
        self.cwd_base = settings.acp_cwd_base

    def prepare_cwd(self, tenant_id: str | None = None) -> str:
        """Resolve and create the working directory for a tenant's ACP session.

        With cwd_base set, each tenant gets an isolated subdirectory
        (<cwd_base>/<tenant_id>); otherwise the shared default_cwd is used. The
        gateway validates cwd against the service's allowedRoots and the agent
        chdirs into it, so the directory must exist. On a shared host it is
        created here; an absolute path is returned verbatim (no resolve()) so it
        still matches allowedRoots, and a failed mkdir is tolerated for the case
        where the gateway runs on a different host that owns the path.
        """
        if self.cwd_base and tenant_id:
            if _is_posix_absolute(self.cwd_base):
                cwd = posixpath.join(self.cwd_base, tenant_id)
                _ensure_dir(cwd)
                return cwd
            path = Path(self.cwd_base).expanduser() / tenant_id
        else:
            if _is_posix_absolute(self.default_cwd):
                _ensure_dir(self.default_cwd)
                return self.default_cwd
            path = Path(self.default_cwd).expanduser()
        path = path.resolve()
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def _path(self, suffix: str, route_prefix: str | None = None) -> str:
        prefix = self.route_prefix if route_prefix is None else route_prefix.rstrip("/")
        return f"{prefix}{suffix}"

    def _headers(self, tenant_id: str | None = None) -> dict[str, str]:
        headers = {"X-Client-ID": self.client_id}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id
        return headers

    async def request(
        self, method: str, path: str, *, tenant_id: str | None = None, **kwargs: Any
    ) -> Any:
        if not self.base_url:
            raise ApiError(503, "ACP_UNCONFIGURED", "acp gateway base URL is not configured")
        async with httpx.AsyncClient(base_url=self.base_url, timeout=120) as client:
            response = await client.request(method, path, headers=self._headers(tenant_id), **kwargs)
        if response.status_code >= 400:
            raise ApiError(
                response.status_code,
                "ACP_UPSTREAM_ERROR",
                "acp gateway request failed",
                {"statusCode": response.status_code, "body": response.text[:1000]},
            )
        if not response.content:
            return None
        return response.json()

    async def stream(
        self, method: str, path: str, *, tenant_id: str | None = None, **kwargs: Any
    ) -> AsyncIterator[str]:
        if not self.base_url:
            raise ApiError(503, "ACP_UNCONFIGURED", "acp gateway base URL is not configured")
        async with httpx.AsyncClient(base_url=self.base_url, timeout=None) as client:
            async with client.stream(
                method, path, headers=self._headers(tenant_id), **kwargs
            ) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise ApiError(
                        response.status_code,
                        "ACP_UPSTREAM_ERROR",
                        "acp gateway stream failed",
                        {"statusCode": response.status_code, "body": body.decode()[:1000]},
                    )
                async for line in response.aiter_lines():
                    yield line

    # --- ACP data-plane endpoints --------------------------------------------

    def stream_turn(
        self,
        *,
        thread_id: str,
        input: str,
        tenant_id: str | None = None,
        session_id: str | None = None,
        cwd: str | None = None,
        model: str | None = None,
        fresh_session: bool = False,
        config_overrides: dict[str, str] | None = None,
        search_mode: str | None = None,
        route_prefix: str | None = None,
    ) -> AsyncIterator[str]:
        """Drive one turn. Yields raw SSE lines from POST {prefix}/turn.

        Mirrors acpruntime.TurnRequest: only thread_id and input are required;
        empty optional fields are omitted so the gateway falls back to the
        service config defaults (cwd, model).
        """
        payload: dict[str, Any] = {"thread_id": thread_id, "input": input}
        if session_id:
            payload["session_id"] = session_id
        if cwd:
            payload["cwd"] = cwd
        if model or self.default_model:
            payload["model"] = model or self.default_model
        if fresh_session:
            payload["fresh_session"] = True
        if config_overrides:
            payload["config_overrides"] = config_overrides
        if search_mode:
            payload["search_mode"] = search_mode
        return self.stream(
            "POST", self._path("/turn", route_prefix), tenant_id=tenant_id, json=payload
        )

    async def resolve_permission(
        self,
        *,
        request_id: str,
        outcome: str,
        option_id: str | None = None,
        tenant_id: str | None = None,
        route_prefix: str | None = None,
    ) -> Any:
        """Answer one pending interactive permission request via POST {prefix}/permission.

        Mirrors acpruntime.PermissionDecision: outcome is the ACP discriminator
        ("selected" with option_id, or "cancelled"). The id travels in the body,
        not the path, and must reach the gateway instance holding the request.
        """
        payload: dict[str, Any] = {"request_id": request_id, "outcome": outcome}
        if option_id:
            payload["option_id"] = option_id
        return await self.request(
            "POST", self._path("/permission", route_prefix), tenant_id=tenant_id, json=payload
        )

    async def list_sessions(
        self,
        *,
        tenant_id: str | None = None,
        cwd: str | None = None,
        cursor: str | None = None,
        route_prefix: str | None = None,
    ) -> Any:
        """List materialized ACP sessions via GET {prefix}/sessions.

        Returns the gateway's ListSessionsResponse: {sessions: [{session_id, cwd,
        title, updated_at}], next_cursor}. The route's VirtualKey is the only auth;
        scope is the route's service, so no service id is passed.
        """
        params: dict[str, str] = {}
        if cwd:
            params["cwd"] = cwd
        if cursor:
            params["cursor"] = cursor
        return await self.request(
            "GET", self._path("/sessions", route_prefix), tenant_id=tenant_id, params=params or None
        )

    async def get_transcript(
        self,
        *,
        session_id: str,
        tenant_id: str | None = None,
        cwd: str | None = None,
        route_prefix: str | None = None,
    ) -> Any:
        """Load a session's coalesced transcript via GET {prefix}/sessions/{id}/transcript.

        Returns the gateway's TranscriptResponse: {session_id, messages: [{role,
        text}]} with role in user/assistant/reasoning.
        """
        params: dict[str, str] = {}
        if cwd:
            params["cwd"] = cwd
        path = self._path(f"/sessions/{quote(session_id, safe='')}/transcript", route_prefix)
        return await self.request("GET", path, tenant_id=tenant_id, params=params or None)


def _is_posix_absolute(path: str) -> bool:
    return path.startswith("/") and not path.startswith("//")


def _ensure_dir(path: str) -> None:
    # Best-effort: the agent chdirs into cwd, so it must exist on a shared host. When the gateway
    # runs on a different host it owns the path, so tolerate a local mkdir failure.
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
