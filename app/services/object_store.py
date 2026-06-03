from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.core.config import Settings
from app.core.errors import ApiError


@dataclass(frozen=True)
class ObjectStat:
    size: int
    etag: str | None = None


class ObjectStore:
    """Control-plane view of the document object storage.

    The API never streams document bodies; it only mints short-lived presigned URLs,
    verifies uploaded objects (HEAD) and removes objects. Implementations expose the
    bucket they write to so it can be persisted on `documents.object_bucket`.
    """

    @property
    def bucket(self) -> str:
        raise NotImplementedError

    def presigned_put_url(
        self, object_key: str, *, expires: timedelta, content_type: str | None = None
    ) -> str:
        raise NotImplementedError

    def presigned_get_url(self, object_key: str, *, expires: timedelta) -> str:
        raise NotImplementedError

    def stat(self, object_key: str) -> ObjectStat:
        raise NotImplementedError

    def remove(self, object_key: str) -> None:
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
        self, object_key: str, *, expires: timedelta, content_type: str | None = None
    ) -> str:
        # content_type is enforced by the client sending the matching Content-Type header;
        # the presigned PUT URL itself does not bind it. See design section 11.
        return self.client.presigned_put_object(self._bucket, object_key, expires=expires)

    def presigned_get_url(self, object_key: str, *, expires: timedelta) -> str:
        return self.client.presigned_get_object(self._bucket, object_key, expires=expires)

    def stat(self, object_key: str) -> ObjectStat:
        try:
            info = self.client.stat_object(self._bucket, object_key)
        except self._s3_error as exc:
            if getattr(exc, "code", None) in {"NoSuchKey", "NoSuchObject", "NotFound"}:
                raise ApiError(404, "DOC_OBJECT_NOT_FOUND", "Uploaded object not found") from exc
            raise
        return ObjectStat(size=int(info.size or 0), etag=info.etag)

    def remove(self, object_key: str) -> None:
        self.client.remove_object(self._bucket, object_key)


# Process-level cache. Constructing a MinioObjectStore opens a client and does a bucket
# exists/create round-trip; without this every request that injects the store would pay that
# cost. Keyed by the connection config so distinct settings (e.g. per-test) get distinct stores.
_STORE_CACHE: dict[tuple[object, ...], ObjectStore] = {}


def create_object_store(settings: Settings) -> ObjectStore:
    key = (
        settings.minio_endpoint,
        settings.minio_access_key,
        settings.minio_secret_key,
        settings.minio_bucket,
        settings.minio_secure,
    )
    store = _STORE_CACHE.get(key)
    if store is None:
        store = MinioObjectStore(settings)
        _STORE_CACHE[key] = store
    return store
