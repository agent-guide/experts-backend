from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def error_payload(code: str, message: str, details: dict[str, object] | None = None) -> dict:
    if details:
        return {"code": code, "message": message, "details": details}
    return {"code": code, "message": message}


def _sanitize_json_value(value: Any) -> Any:
    if isinstance(value, str):
        # Replace invalid surrogates so JSON encoding never crashes with
        # "UnicodeEncodeError: surrogates not allowed".
        return value.encode("utf-8", errors="replace").decode("utf-8")
    if isinstance(value, list):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(_sanitize_json_value(key)): _sanitize_json_value(item)
            for key, item in value.items()
        }
    return value


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # jsonable_encoder coerces non-serializable error context (e.g. the original
        # exception objects pydantic puts under `ctx`) into JSON-safe primitives first;
        # _sanitize_json_value then scrubs invalid surrogates from any strings.
        errors = jsonable_encoder(exc.errors())
        return JSONResponse(
            status_code=422,
            content={"detail": _sanitize_json_value(errors)},
        )
