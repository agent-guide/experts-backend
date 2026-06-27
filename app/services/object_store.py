from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

import jwt

from app.core.config import Settings
from app.core.errors import ApiError


@dataclass(frozen=True)
class ObjectStat:
    size: int
    etag: str | None = None
    content_type: str | None = None


class ObjectStore:
    """Control-plane view of the document object storage.

    The API mints short-lived upload/download URLs, verifies uploaded objects (HEAD) and
    removes objects. MinIO URLs send bytes directly to MinIO/S3; local URLs send bytes to
    a signed backend route that streams to disk. Implementations expose the bucket they
    write to so it can be persisted on `documents.object_bucket`.
    """

    @property
    def bucket(self) -> str:
        raise NotImplementedError

    def presigned_put_url(
        self,
        object_key: str,
        *,
        expires: timedelta,
        content_type: str | None = None,
        content_length: int | None = None,
    ) -> str:
        raise NotImplementedError

    def presigned_get_url(
        self,
        object_key: str,
        *,
        expires: timedelta,
        response_headers: dict[str, str] | None = None,
    ) -> str:
        raise NotImplementedError

    def stat(self, object_key: str) -> ObjectStat:
        raise NotImplementedError

    def put(self, object_key: str, data: bytes, *, content_type: str | None = None) -> None:
        raise NotImplementedError

    def read(self, object_key: str, *, max_bytes: int | None = None) -> bytes:
        raise NotImplementedError

    def remove(self, object_key: str) -> None:
        raise NotImplementedError

    def remove_prefix(self, object_prefix: str) -> None:
        raise NotImplementedError


class MinioObjectStore(ObjectStore):
    def __init__(self, settings: Settings) -> None:
        try:
            from minio import Minio
            from minio.error import S3Error
        except ImportError as exc:  # pragma: no cover - depends on optional runtime config
            raise RuntimeError("MinIO object store requires the minio dependency.") from exc

        if not (
            settings.minio_endpoint
            and settings.minio_access_key
            and settings.minio_secret_key
            and settings.minio_bucket
        ):
            raise RuntimeError(
                "MinIO object store requires endpoint, access key, secret key and bucket."
            )

        self._s3_error = S3Error
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._bucket = settings.minio_bucket
        if not self.client.bucket_exists(self._bucket):
            self.client.make_bucket(self._bucket)

    @property
    def bucket(self) -> str:
        return self._bucket

    def presigned_put_url(
        self,
        object_key: str,
        *,
        expires: timedelta,
        content_type: str | None = None,
        content_length: int | None = None,
    ) -> str:
        # content_type is enforced by the client sending the matching Content-Type header;
        # the presigned PUT URL itself does not bind it. content_length is validated before
        # signing by DocumentService for both backends; MinIO does not bind it into the URL.
        return self.client.presigned_put_object(self._bucket, object_key, expires=expires)

    def presigned_get_url(
        self,
        object_key: str,
        *,
        expires: timedelta,
        response_headers: dict[str, str] | None = None,
    ) -> str:
        return self.client.presigned_get_object(
            self._bucket,
            object_key,
            expires=expires,
            response_headers=response_headers,
        )

    def stat(self, object_key: str) -> ObjectStat:
        try:
            info = self.client.stat_object(self._bucket, object_key)
        except self._s3_error as exc:
            if getattr(exc, "code", None) in {"NoSuchKey", "NoSuchObject", "NotFound"}:
                raise ApiError(404, "DOC_OBJECT_NOT_FOUND", "Uploaded object not found") from exc
            raise
        return ObjectStat(size=int(info.size or 0), etag=info.etag, content_type=info.content_type)

    def put(self, object_key: str, data: bytes, *, content_type: str | None = None) -> None:
        from io import BytesIO

        self.client.put_object(
            self._bucket,
            object_key,
            BytesIO(data),
            length=len(data),
            content_type=content_type or "application/octet-stream",
        )

    def read(self, object_key: str, *, max_bytes: int | None = None) -> bytes:
        try:
            response = self.client.get_object(self._bucket, object_key)
        except self._s3_error as exc:
            if getattr(exc, "code", None) in {"NoSuchKey", "NoSuchObject", "NotFound"}:
                raise ApiError(404, "DOC_OBJECT_NOT_FOUND", "Object not found") from exc
            raise
        try:
            data = response.read(max_bytes + 1 if max_bytes is not None else None)
        finally:
            response.close()
            response.release_conn()
        if max_bytes is not None and len(data) > max_bytes:
            raise ApiError(413, "OBJECT_TOO_LARGE", "Object is too large to read inline")
        return data

    def remove(self, object_key: str) -> None:
        self.client.remove_object(self._bucket, object_key)

    def remove_prefix(self, object_prefix: str) -> None:
        prefix = _safe_object_prefix(object_prefix)
        for item in self.client.list_objects(self._bucket, prefix=prefix, recursive=True):
            self.client.remove_object(self._bucket, item.object_name)


class LocalObjectStore(ObjectStore):
    def __init__(self, settings: Settings) -> None:
        self.root = Path(settings.object_storage_local_dir).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._bucket = "local"
        self._settings = settings

    @property
    def bucket(self) -> str:
        return self._bucket

    def presigned_put_url(
        self,
        object_key: str,
        *,
        expires: timedelta,
        content_type: str | None = None,
        content_length: int | None = None,
    ) -> str:
        token = issue_object_store_token(
            self._settings,
            object_key,
            method="PUT",
            expires=expires,
            content_type=content_type,
            content_length=content_length,
        )
        return _local_object_url(self._settings, token)

    def presigned_get_url(
        self,
        object_key: str,
        *,
        expires: timedelta,
        response_headers: dict[str, str] | None = None,
    ) -> str:
        token = issue_object_store_token(
            self._settings,
            object_key,
            method="GET",
            expires=expires,
            response_headers=response_headers,
        )
        return _local_object_url(self._settings, token)

    def stat(self, object_key: str) -> ObjectStat:
        path = self._path(object_key)
        if not path.is_file():
            raise ApiError(404, "DOC_OBJECT_NOT_FOUND", "Uploaded object not found")
        return ObjectStat(
            size=path.stat().st_size,
            etag=None,
            content_type=self._metadata(object_key).get("contentType"),
        )

    def put(self, object_key: str, data: bytes, *, content_type: str | None = None) -> None:
        path = self._path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self._write_metadata(object_key, content_type=content_type)

    def read(self, object_key: str, *, max_bytes: int | None = None) -> bytes:
        path = self._path(object_key)
        if not path.is_file():
            raise ApiError(404, "DOC_OBJECT_NOT_FOUND", "Object not found")
        if max_bytes is not None and path.stat().st_size > max_bytes:
            raise ApiError(413, "OBJECT_TOO_LARGE", "Object is too large to read inline")
        return path.read_bytes()

    def remove(self, object_key: str) -> None:
        path = self._path(object_key)
        try:
            path.unlink()
        except FileNotFoundError:
            return
        self._remove_metadata(object_key)
        self._remove_empty_parents(path.parent)

    def remove_prefix(self, object_prefix: str) -> None:
        prefix = _safe_object_prefix(object_prefix)
        path = (self.root / prefix).resolve()
        if not path.is_relative_to(self.root):
            raise ApiError(400, "OBJECT_INVALID_KEY", "Invalid object key")
        if not path.exists():
            return
        if path.is_file():
            path.unlink()
            self._remove_empty_parents(path.parent)
            return
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        path.rmdir()
        self._remove_empty_parents(path.parent)

    def _path(self, object_key: str) -> Path:
        relative = _safe_object_key(object_key)
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ApiError(400, "OBJECT_INVALID_KEY", "Invalid object key")
        return path

    def local_path(self, object_key: str) -> Path:
        path = self._path(object_key)
        if not path.is_file():
            raise ApiError(404, "DOC_OBJECT_NOT_FOUND", "Object not found")
        return path

    def content_type(self, object_key: str) -> str | None:
        return self._metadata(object_key).get("contentType")

    async def write_local_stream(
        self,
        object_key: str,
        chunks: Any,
        *,
        max_bytes: int,
        content_type: str | None,
    ) -> None:
        path = self._path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
        written = 0
        try:
            with tmp_path.open("wb") as handle:
                async for chunk in chunks:
                    written += len(chunk)
                    if written > max_bytes:
                        raise ApiError(413, "OBJECT_TOO_LARGE", "Object upload is too large")
                    handle.write(chunk)
            tmp_path.replace(path)
            self._write_metadata(object_key, content_type=content_type)
        except Exception:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass
            raise

    def _metadata_path(self, object_key: str) -> Path:
        path = self._path(object_key)
        return path.with_name(f".{path.name}.metadata.json")

    def _metadata(self, object_key: str) -> dict[str, str]:
        path = self._metadata_path(object_key)
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): str(value) for key, value in data.items() if value is not None}

    def _write_metadata(self, object_key: str, *, content_type: str | None) -> None:
        path = self._metadata_path(object_key)
        if content_type:
            path.write_text(json.dumps({"contentType": content_type}), encoding="utf-8")
            return
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def _remove_metadata(self, object_key: str) -> None:
        try:
            self._metadata_path(object_key).unlink()
        except FileNotFoundError:
            pass

    def _remove_empty_parents(self, path: Path) -> None:
        while path != self.root:
            try:
                path.rmdir()
            except OSError:
                return
            path = path.parent


# Process-level cache. Constructing a MinioObjectStore opens a client and does a bucket
# exists/create round-trip; without this every request that injects the store would pay that
# cost. Keyed by the connection config so distinct settings (e.g. per-test) get distinct stores.
_STORE_CACHE: dict[tuple[object, ...], ObjectStore] = {}


def create_object_store(settings: Settings) -> ObjectStore:
    key = (
        settings.object_storage_backend,
        settings.object_storage_local_dir,
        settings.object_storage_public_base_url,
        settings.object_storage_max_upload_bytes,
        settings.minio_endpoint,
        settings.minio_access_key,
        settings.minio_secret_key,
        settings.minio_bucket,
        settings.minio_secure,
    )
    store = _STORE_CACHE.get(key)
    if store is None:
        try:
            if settings.object_storage_backend == "local":
                store = LocalObjectStore(settings)
            elif settings.object_storage_backend == "minio":
                store = MinioObjectStore(settings)
            else:
                raise RuntimeError(
                    f"Unsupported object storage backend: {settings.object_storage_backend}"
                )
        except ApiError:
            raise
        except Exception as exc:
            # Surface storage bootstrap failures (bad endpoint/credentials/unreachable host)
            # as a typed API error instead of an unhandled 500 traceback.
            raise ApiError(
                503,
                "OBJECT_STORE_UNAVAILABLE",
                "Object storage is unavailable",
                {"reason": str(exc)},
            ) from exc
        _STORE_CACHE[key] = store
    return store


def issue_object_store_token(
    settings: Settings,
    object_key: str,
    *,
    method: str,
    expires: timedelta,
    content_type: str | None = None,
    content_length: int | None = None,
    response_headers: dict[str, str] | None = None,
) -> str:
    _safe_object_key(object_key)
    now = datetime.now(timezone.utc)
    claims: dict[str, Any] = {
        "iss": settings.jwt_issuer,
        "aud": "object-store",
        "iat": int(now.timestamp()),
        "exp": int((now + expires).timestamp()),
        "type": "object-store",
        "method": method,
        "objectKey": object_key,
    }
    if content_type:
        claims["contentType"] = content_type
    if content_length is not None:
        claims["contentLength"] = content_length
    if response_headers:
        claims["responseHeaders"] = response_headers
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def decode_object_store_token(settings: Settings, token: str, *, method: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience="object-store",
        )
    except jwt.PyJWTError as exc:
        raise ApiError(401, "OBJECT_TOKEN_INVALID", "Invalid object URL token") from exc
    if claims.get("type") != "object-store" or claims.get("method") != method:
        raise ApiError(403, "OBJECT_TOKEN_FORBIDDEN", "Object URL token cannot be used here")
    object_key = str(claims.get("objectKey") or "")
    _safe_object_key(object_key)
    return claims


def _local_object_url(settings: Settings, token: str) -> str:
    path = f"/api/v1/storage/objects/{token}"
    base = (settings.object_storage_public_base_url or "").rstrip("/")
    return f"{base}{path}" if base else path


def _safe_object_key(object_key: str) -> str:
    cleaned = object_key.strip().replace("\\", "/").lstrip("/")
    pure = PurePosixPath(cleaned)
    if not cleaned or any(part in {"", ".", ".."} for part in pure.parts):
        raise ApiError(400, "OBJECT_INVALID_KEY", "Invalid object key")
    return str(pure)


def _safe_object_prefix(object_prefix: str) -> str:
    cleaned = _safe_object_key(object_prefix)
    return cleaned.rstrip("/") + "/"


def best_effort_remove(store: ObjectStore, object_key: str) -> None:
    """Remove an object, swallowing any failure (GC retries by key on the next pass)."""
    try:
        store.remove(object_key)
    except Exception:  # noqa: BLE001 - cleanup is best-effort; GC will retry by key
        pass


def remove_if_present(store: ObjectStore, object_key: str) -> bool:
    """Remove an object, reporting whether it is now gone.

    Returns True when the object was removed or was already absent (a 404), so the caller can
    safely drop the owning DB row. Returns False on any other failure (e.g. backend unavailable)
    so the row is kept and reclaimed on the next GC pass.
    """
    try:
        store.remove(object_key)
        return True
    except ApiError as exc:
        return exc.status_code == 404
    except Exception:  # noqa: BLE001 - keep DB rows so GC can retry later
        return False
