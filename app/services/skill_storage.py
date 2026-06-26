from __future__ import annotations

from pathlib import PurePosixPath

from app.core.config import Settings
from app.core.errors import ApiError
from app.services.object_store import ObjectStore, create_object_store


_SKILL_OBJECT_PREFIX = "skills"


class SkillStorage:
    def uri_for(self, slug: str) -> str:
        raise NotImplementedError

    def put_files(self, slug: str, files: dict[str, bytes]) -> str:
        raise NotImplementedError

    def get_file(self, slug: str, path: str) -> bytes:
        raise NotImplementedError

    def delete_skill(self, slug: str) -> None:
        raise NotImplementedError


class ObjectStoreSkillStorage(SkillStorage):
    def __init__(self, store: ObjectStore, prefix: str) -> None:
        self.store = store
        self.prefix = _clean_prefix(prefix)

    def put_files(self, slug: str, files: dict[str, bytes]) -> str:
        for relative_path, content in files.items():
            self.store.put(self._object_name(slug, relative_path), content)
        return self.uri_for(slug)

    def uri_for(self, slug: str) -> str:
        if self.store.bucket == "local":
            return f"/{self.prefix}/{slug}"
        return f"minio://{self.store.bucket}/{self.prefix}/{slug}"

    def get_file(self, slug: str, path: str) -> bytes:
        try:
            return self.store.read(self._object_name(slug, path))
        except ApiError as exc:
            if exc.status_code == 404:
                raise ApiError(404, "SKILL_FILE_NOT_FOUND", "Skill file not found") from exc
            raise

    def delete_skill(self, slug: str) -> None:
        self.store.remove_prefix(f"{self.prefix}/{slug}")

    def _object_name(self, slug: str, path: str) -> str:
        return f"{self.prefix}/{slug}/{_safe_relative_path(path)}"


def create_skill_storage(settings: Settings) -> SkillStorage:
    return ObjectStoreSkillStorage(create_object_store(settings), _SKILL_OBJECT_PREFIX)


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
