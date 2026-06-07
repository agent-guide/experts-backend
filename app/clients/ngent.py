from pathlib import Path
from typing import Any, AsyncIterator

import httpx

from app.core.config import Settings
from app.core.errors import ApiError


class NgentClient:
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.ngent_base_url
        self.auth_token = settings.ngent_auth_token
        self.client_id = settings.ngent_client_id
        self.default_agent = settings.ngent_default_agent
        self.default_cwd = settings.ngent_default_cwd
        self.cwd_base = settings.ngent_cwd_base

    def prepare_cwd(self, tenant_id: str | None = None) -> str:
        """Resolve and create the working directory for a tenant's ngent thread.

        With cwd_base set, each tenant gets an isolated subdirectory
        (<cwd_base>/<tenant_id>); otherwise the shared default_cwd is used. ngent
        requires cwd to exist and be absolute, so the directory is created here
        (backend and ngent share the host).
        """
        if self.cwd_base and tenant_id:
            path = Path(self.cwd_base).expanduser() / tenant_id
        else:
            path = Path(self.default_cwd).expanduser()
        path = path.resolve()
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

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
            raise ApiError(503, "NGENT_UNCONFIGURED", "ngent base URL is not configured")
        async with httpx.AsyncClient(base_url=self.base_url, timeout=120) as client:
            response = await client.request(method, path, headers=self._headers(tenant_id), **kwargs)
        if response.status_code >= 400:
            raise ApiError(
                response.status_code,
                "NGENT_UPSTREAM_ERROR",
                "ngent upstream request failed",
                {"statusCode": response.status_code, "body": response.text[:1000]},
            )
        if not response.content:
            return None
        return response.json()

    async def stream(
        self, method: str, path: str, *, tenant_id: str | None = None, **kwargs: Any
    ) -> AsyncIterator[str]:
        if not self.base_url:
            raise ApiError(503, "NGENT_UNCONFIGURED", "ngent base URL is not configured")
        async with httpx.AsyncClient(base_url=self.base_url, timeout=None) as client:
            async with client.stream(
                method, path, headers=self._headers(tenant_id), **kwargs
            ) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise ApiError(
                        response.status_code,
                        "NGENT_UPSTREAM_ERROR",
                        "ngent upstream stream failed",
                        {"statusCode": response.status_code, "body": body.decode()[:1000]},
                    )
                async for line in response.aiter_lines():
                    yield line
