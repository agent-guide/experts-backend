from __future__ import annotations

from pathlib import Path, PurePosixPath

from app.core.config import Settings
from app.core.errors import ApiError


class SkillStorage:
    def uri_for(self, slug: str) -> str:
        raise NotImplementedError

    def put_files(self, slug: str, files: dict[str, bytes]) -> str:
        raise NotImplementedError

    def get_file(self, slug: str, path: str) -> bytes:
        raise NotImplementedError

    def delete_skill(self, slug: str) -> None:
        raise NotImplementedError


class LocalSkillStorage(SkillStorage):
    def __init__(self, root: str, prefix: str) -> None:
        self.root = Path(root).expanduser()
        self.prefix = _clean_prefix(prefix)

    def put_files(self, slug: str, files: dict[str, bytes]) -> str:
        base = self._base(slug)
        base.mkdir(parents=True, exist_ok=True)
        for relative_path, content in files.items():
            target = base / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        return self.uri_for(slug)

    def uri_for(self, slug: str) -> str:
        return f"/{self.prefix}/{slug}"

    def get_file(self, slug: str, path: str) -> bytes:
        relative = _safe_relative_path(path)
        target = self._base(slug) / relative
        if not target.is_file():
            raise ApiError(404, "SKILL_FILE_NOT_FOUND", "Skill file not found")
        return target.read_bytes()

    def delete_skill(self, slug: str) -> None:
        base = self._base(slug)
        if not base.exists():
            return
        for child in sorted(base.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        base.rmdir()

    def _base(self, slug: str) -> Path:
        return self.root / self.prefix / slug


class MinioSkillStorage(SkillStorage):
    def __init__(self, settings: Settings) -> None:
        try:
            from minio import Minio
            from minio.error import S3Error
        except ImportError as exc:  # pragma: no cover - depends on optional runtime config
            raise RuntimeError("MinIO storage requires the minio dependency.") from exc

        if not (
            settings.minio_endpoint
            and settings.minio_access_key
            and settings.minio_secret_key
            and settings.minio_bucket
        ):
            raise RuntimeError("MinIO storage requires endpoint, access key, secret key and bucket.")

        self._s3_error = S3Error
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket
        self.prefix = _clean_prefix(settings.skill_storage_prefix)
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put_files(self, slug: str, files: dict[str, bytes]) -> str:
        from io import BytesIO

        for relative_path, content in files.items():
            object_name = self._object_name(slug, relative_path)
            self.client.put_object(
                self.bucket,
                object_name,
                BytesIO(content),
                length=len(content),
            )
        return self.uri_for(slug)

    def uri_for(self, slug: str) -> str:
        return f"minio://{self.bucket}/{self.prefix}/{slug}"

    def get_file(self, slug: str, path: str) -> bytes:
        object_name = self._object_name(slug, path)
        try:
            response = self.client.get_object(self.bucket, object_name)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except self._s3_error as exc:
            if getattr(exc, "code", None) == "NoSuchKey":
                raise ApiError(404, "SKILL_FILE_NOT_FOUND", "Skill file not found") from exc
            raise

    def delete_skill(self, slug: str) -> None:
        prefix = f"{self.prefix}/{slug}/"
        for item in self.client.list_objects(self.bucket, prefix=prefix, recursive=True):
            self.client.remove_object(self.bucket, item.object_name)

    def _object_name(self, slug: str, path: str) -> str:
        return f"{self.prefix}/{slug}/{_safe_relative_path(path)}"


def create_skill_storage(settings: Settings) -> SkillStorage:
    if settings.skill_storage_backend == "local":
        return LocalSkillStorage(settings.skill_storage_local_dir, settings.skill_storage_prefix)
    if settings.skill_storage_backend == "minio":
        return MinioSkillStorage(settings)
    raise RuntimeError(f"Unsupported skill storage backend: {settings.skill_storage_backend}")


def _clean_prefix(prefix: str) -> str:
    cleaned = prefix.strip().strip("/")
    if not cleaned:
        raise RuntimeError("Skill storage prefix cannot be empty")
    return cleaned


def _safe_relative_path(path: str) -> str:
    cleaned = path.strip().replace("\\", "/").lstrip("/")
    pure = PurePosixPath(cleaned)
    if not cleaned or any(part in {"", ".", ".."} for part in pure.parts):
        raise ApiError(400, "SKILL_INVALID_FILE_PATH", "Invalid skill file path")
    return str(pure)
