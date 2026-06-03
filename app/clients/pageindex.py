from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import ApiError


class PageIndexClient:
    """Adapter for PageIndex SDK/API.

    PageIndex can be integrated as a Python package, a cloud API, or MCP. This
    scaffold uses an HTTP adapter first because it keeps the API shell stable.
    Replace these methods with direct SDK calls once the exact deployment mode
    is selected.
    """

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.pageindex_base_url
        self.api_key = settings.pageindex_api_key

    def _headers(self, tenant_id: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id
        return headers

    async def request(
        self, method: str, path: str, *, tenant_id: str | None = None, **kwargs: Any
    ) -> Any:
        if not self.base_url:
            raise ApiError(503, "PAGEINDEX_UNCONFIGURED", "PageIndex base URL is not configured")
        async with httpx.AsyncClient(base_url=self.base_url, timeout=60) as client:
            response = await client.request(method, path, headers=self._headers(tenant_id), **kwargs)
        if response.status_code >= 400:
            raise ApiError(
                response.status_code,
                "PAGEINDEX_UPSTREAM_ERROR",
                "PageIndex upstream request failed",
                {"statusCode": response.status_code, "body": response.text[:1000]},
            )
        if not response.content:
            return None
        return response.json()
