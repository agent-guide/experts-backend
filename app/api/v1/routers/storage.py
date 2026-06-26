from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import FileResponse, Response

from app.api.deps import get_object_store, get_settings
from app.core.config import Settings
from app.core.errors import ApiError
from app.services.object_store import LocalObjectStore, ObjectStore, decode_object_store_token

router = APIRouter()


@router.put("/objects/{token}", status_code=204)
async def put_object(
    token: str,
    request: Request,
    content_type: str | None = Header(default=None, alias="content-type"),
    content_length: int | None = Header(default=None, alias="content-length"),
    settings: Settings = Depends(get_settings),
    object_store: ObjectStore = Depends(get_object_store),
) -> Response:
    local_store = _require_local_store(object_store)
    claims = decode_object_store_token(settings, token, method="PUT")
    object_key = str(claims["objectKey"])
    expected_type = claims.get("contentType")
    if expected_type is not None and content_type != str(expected_type):
        raise ApiError(400, "OBJECT_CONTENT_TYPE_MISMATCH", "Content-Type does not match upload token")
    max_bytes = _upload_limit(settings, claims.get("contentLength"))
    if content_length is not None and content_length > max_bytes:
        raise ApiError(413, "OBJECT_TOO_LARGE", "Object upload is too large")
    await local_store.write_local_stream(
        object_key,
        request.stream(),
        max_bytes=max_bytes,
        content_type=content_type,
    )
    return Response(status_code=204)


@router.get("/objects/{token}")
async def get_object(
    token: str,
    settings: Settings = Depends(get_settings),
    object_store: ObjectStore = Depends(get_object_store),
) -> Response:
    local_store = _require_local_store(object_store)
    claims = decode_object_store_token(settings, token, method="GET")
    object_key = str(claims["objectKey"])
    headers = _response_headers(claims.get("responseHeaders"))
    media_type = (
        headers.pop("content-type", None)
        or local_store.content_type(object_key)
        or "application/octet-stream"
    )
    return FileResponse(
        local_store.local_path(object_key),
        media_type=media_type,
        headers=headers,
    )


def _require_local_store(object_store: ObjectStore) -> LocalObjectStore:
    if not isinstance(object_store, LocalObjectStore):
        raise ApiError(404, "OBJECT_ROUTE_NOT_FOUND", "Object route is not available")
    return object_store


def _upload_limit(settings: Settings, claim: object) -> int:
    configured = settings.object_storage_max_upload_bytes
    if claim is None:
        return configured
    try:
        expected = int(claim)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "OBJECT_INVALID_TOKEN", "Invalid upload token") from exc
    if expected <= 0:
        raise ApiError(400, "OBJECT_INVALID_TOKEN", "Invalid upload token")
    if expected > configured:
        raise ApiError(413, "OBJECT_TOO_LARGE", "Object upload is too large")
    return expected


def _response_headers(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    headers: dict[str, str] = {}
    content_type = value.get("response-content-type")
    if content_type:
        headers["content-type"] = str(content_type)
    disposition = value.get("response-content-disposition")
    if disposition:
        headers["content-disposition"] = str(disposition)
    return headers
