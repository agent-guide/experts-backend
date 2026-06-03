import mimetypes
import posixpath

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response

from app.api.deps import (
    get_database,
    get_skill_storage,
    require_platform_permission,
    require_principal,
)
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.skills import Skill, SkillListResponse, SkillMetadataUpdate
from app.core.errors import ApiError
from app.services.skill_service import MAX_ARCHIVE_BYTES, SkillService
from app.services.skill_storage import SkillStorage

router = APIRouter()


@router.post("", response_model=Skill, status_code=201)
async def upload_skill(
    file: UploadFile = File(...),
    slug: str | None = Form(default=None),
    _: Principal = Depends(require_platform_permission("skill:write")),
    connection: DatabaseConnection = Depends(get_database),
    storage: SkillStorage = Depends(get_skill_storage),
) -> Skill:
    content = await file.read(MAX_ARCHIVE_BYTES + 1)
    if len(content) > MAX_ARCHIVE_BYTES:
        raise ApiError(400, "SKILL_ZIP_TOO_LARGE", "Skill zip archive is too large")
    return SkillService(connection, storage).upload(content, slug)


@router.get("", response_model=SkillListResponse)
async def list_skills(
    tags: list[str] = Query(default_factory=list),
    search: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: Principal = Depends(require_principal),
    connection: DatabaseConnection = Depends(get_database),
    storage: SkillStorage = Depends(get_skill_storage),
) -> SkillListResponse:
    normalized_tags = _normalize_tags(tags)
    items, total = SkillService(connection, storage).list(
        tags=normalized_tags,
        search=search,
        limit=limit,
        offset=offset,
    )
    return SkillListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        hasMore=offset + len(items) < total,
    )


@router.get("/{slug}", response_model=Skill)
async def get_skill(
    slug: str,
    _: Principal = Depends(require_principal),
    connection: DatabaseConnection = Depends(get_database),
    storage: SkillStorage = Depends(get_skill_storage),
) -> Skill:
    return SkillService(connection, storage).get(slug)


@router.put("/{slug}", response_model=Skill)
async def update_skill(
    slug: str,
    update: SkillMetadataUpdate,
    _: Principal = Depends(require_platform_permission("skill:write")),
    connection: DatabaseConnection = Depends(get_database),
    storage: SkillStorage = Depends(get_skill_storage),
) -> Skill:
    return SkillService(connection, storage).update(slug, update)


@router.delete("/{slug}", status_code=204)
async def delete_skill(
    slug: str,
    delete_files: bool = False,
    _: Principal = Depends(require_platform_permission("skill:write")),
    connection: DatabaseConnection = Depends(get_database),
    storage: SkillStorage = Depends(get_skill_storage),
) -> None:
    SkillService(connection, storage).delete(slug, delete_files)
    return None


@router.get("/{slug}/file")
async def get_skill_file(
    slug: str,
    path: str = "SKILL.md",
    _: Principal = Depends(require_principal),
    connection: DatabaseConnection = Depends(get_database),
    storage: SkillStorage = Depends(get_skill_storage),
) -> Response:
    content = SkillService(connection, storage).get_file(slug, path)
    return Response(content=content, media_type=_media_type_for(path))


def _media_type_for(path: str) -> str:
    if posixpath.basename(path).lower().endswith(".md"):
        return "text/markdown; charset=utf-8"
    guessed, _ = mimetypes.guess_type(path)
    if guessed is None:
        return "application/octet-stream"
    if guessed.startswith("text/"):
        return f"{guessed}; charset=utf-8"
    return guessed


def _normalize_tags(values: list[str]) -> list[str]:
    tags: list[str] = []
    for value in values:
        tags.extend(part.strip() for part in value.split(","))
    return [tag for tag in tags if tag]
