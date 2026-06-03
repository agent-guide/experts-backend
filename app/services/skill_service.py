from __future__ import annotations

import re
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import PurePosixPath
from uuid import uuid4

from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.skills import Skill, SkillMetadataUpdate
from app.services.skill_repository import SkillRepository
from app.services.skill_storage import SkillStorage


class SkillService:
    def __init__(self, connection: DatabaseConnection, storage: SkillStorage) -> None:
        self.connection = connection
        self.repo = SkillRepository(connection)
        self.storage = storage

    def upload(self, zip_bytes: bytes, slug_override: str | None = None) -> Skill:
        files = _read_zip_files(zip_bytes)
        skill_md_path = _find_skill_md(files)
        meta = _parse_frontmatter(files[skill_md_path].decode("utf-8"))
        name = _required_meta(meta, "name")
        description = _required_meta(meta, "description")
        slug = _normalize_slug(slug_override or name)
        if self.repo.get(slug):
            raise ApiError(409, "SKILL_EXISTS", "Skill already exists")

        storage_uri = self.storage.put_files(slug, files)
        now = _now_iso()
        skill = Skill(
            id=f"skill_{uuid4().hex}",
            slug=slug,
            name=name,
            description=description,
            version=_optional_string(meta.get("version")),
            allowedTools=_string_list(meta.get("allowed-tools")),
            filePaths=sorted(files),
            tags=_string_list(meta.get("tags")),
            storageUri=storage_uri,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.create(skill)
        self.connection.commit()
        return skill

    def update(self, slug: str, update: SkillMetadataUpdate) -> Skill:
        existing = self.repo.get(slug)
        if not existing:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found")
        updated = self.repo.update(
            slug,
            name=update.name or existing.name,
            description=update.description or existing.description,
            version=update.version if update.version is not None else existing.version,
            allowed_tools=(
                _clean_string_list(update.allowedTools)
                if update.allowedTools is not None
                else existing.allowedTools
            ),
            tags=_clean_string_list(update.tags) if update.tags is not None else existing.tags,
            updated_at=_now_iso(),
        )
        if not updated:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found")
        self.connection.commit()
        return updated

    def delete(self, slug: str, delete_files: bool) -> None:
        existing = self.repo.delete(slug)
        if not existing:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found")
        if delete_files:
            self.storage.delete_skill(slug)
        self.connection.commit()

    def list(self, tags: list[str], search: str | None, limit: int, offset: int) -> list[Skill]:
        return self.repo.list(tags=tags, search=search, limit=limit, offset=offset)

    def get(self, slug: str) -> Skill:
        skill = self.repo.get(slug)
        if not skill:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found")
        return skill

    def get_file(self, slug: str, path: str) -> str:
        skill = self.get(slug)
        if path not in skill.filePaths:
            raise ApiError(404, "SKILL_FILE_NOT_FOUND", "Skill file not found")
        return self.storage.get_file(slug, path)


def _read_zip_files(zip_bytes: bytes) -> dict[str, bytes]:
    try:
        archive = zipfile.ZipFile(BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise ApiError(400, "SKILL_INVALID_ZIP", "Uploaded file must be a zip archive") from exc

    files: dict[str, bytes] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        path = _safe_zip_path(info.filename)
        files[path] = archive.read(info)
    files = _strip_common_root(files)
    if not files:
        raise ApiError(400, "SKILL_EMPTY_ZIP", "Skill zip does not contain files")
    return files


def _safe_zip_path(filename: str) -> str:
    cleaned = filename.replace("\\", "/").lstrip("/")
    path = PurePosixPath(cleaned)
    if not cleaned or any(part in {"", ".", ".."} for part in path.parts):
        raise ApiError(400, "SKILL_INVALID_ZIP_PATH", "Skill zip contains an invalid path")
    return str(path)


def _strip_common_root(files: dict[str, bytes]) -> dict[str, bytes]:
    roots = {PurePosixPath(path).parts[0] for path in files}
    if len(roots) != 1:
        return files
    if "SKILL.md" in files:
        return files
    stripped: dict[str, bytes] = {}
    for path, content in files.items():
        parts = PurePosixPath(path).parts
        if len(parts) > 1:
            stripped["/".join(parts[1:])] = content
    return stripped or files


def _find_skill_md(files: dict[str, bytes]) -> str:
    if "SKILL.md" not in files:
        raise ApiError(400, "SKILL_MD_REQUIRED", "Skill zip must contain SKILL.md")
    return "SKILL.md"


def _parse_frontmatter(content: str) -> dict[str, object]:
    if not content.startswith("---\n"):
        return {}
    end = content.find("\n---", 4)
    if end == -1:
        return {}
    lines = content[4:end].splitlines()
    result: dict[str, object] = {}
    current_key: str | None = None
    for line in lines:
        if not line.strip():
            continue
        if line.startswith("  - ") or line.startswith("- "):
            if current_key:
                existing = result.setdefault(current_key, [])
                if isinstance(existing, list):
                    existing.append(line.split("-", 1)[1].strip())
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            current_key = key.strip()
            value = value.strip()
            result[current_key] = value if value else []
    return result


def _required_meta(meta: dict[str, object], key: str) -> str:
    value = _optional_string(meta.get(key))
    if not value:
        raise ApiError(400, "SKILL_METADATA_REQUIRED", f"SKILL.md frontmatter requires {key}")
    return value


def _optional_string(value: object) -> str | None:
    if value is None or isinstance(value, list):
        return None
    cleaned = str(value).strip().strip('"').strip("'")
    return cleaned or None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return _clean_string_list([str(item) for item in value])


def _clean_string_list(value: list[str]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for item in value:
        cleaned = item.strip().strip('"').strip("'")
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            items.append(cleaned)
    return items


def _normalize_slug(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"\s+", "-", slug)
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,126}[a-z0-9])?", slug):
        raise ApiError(400, "SKILL_INVALID_SLUG", "Skill slug must use lowercase letters, numbers and hyphens")
    return slug


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
