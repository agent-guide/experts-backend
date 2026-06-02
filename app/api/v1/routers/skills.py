from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

from app.api.deps import get_codex_skills_client, require_permission, require_principal
from app.clients.codex_skills import CodexSkillsClient
from app.domain.auth import Principal

router = APIRouter()


@router.post("", status_code=201)
async def upload_skill(
    slug: str,
    file: UploadFile = File(...),
    _: Principal = Depends(require_permission("skill:publish")),
    skills: CodexSkillsClient = Depends(get_codex_skills_client),
) -> dict:
    summary = skills.install_zip(slug, await file.read())
    return summary.model_dump()


@router.get("/installed")
async def list_installed_skills(
    _: Principal = Depends(require_principal),
    skills: CodexSkillsClient = Depends(get_codex_skills_client),
) -> dict:
    return {"items": [item.model_dump() for item in skills.list_installed()]}


@router.get("")
async def list_public_skills(
    _: Principal = Depends(require_principal),
    skills: CodexSkillsClient = Depends(get_codex_skills_client),
) -> dict:
    return {"items": [item.model_dump() for item in skills.list_installed()]}


@router.get("/{slug}")
async def get_skill(
    slug: str,
    _: Principal = Depends(require_principal),
    skills: CodexSkillsClient = Depends(get_codex_skills_client),
) -> dict:
    for item in skills.list_installed():
        if item.slug == slug:
            return item.model_dump()
    from app.core.errors import ApiError

    raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found")


@router.get("/{slug}/file")
async def get_skill_file(
    slug: str,
    filePath: str = "SKILL.md",
    _: Principal = Depends(require_principal),
    skills: CodexSkillsClient = Depends(get_codex_skills_client),
) -> Response:
    return Response(content=skills.get_file(slug, filePath), media_type="text/plain; charset=utf-8")


@router.post("/{slug}/install", status_code=204)
async def install_skill(slug: str, _: Principal = Depends(require_principal)) -> None:
    _ = slug
    return None


@router.delete("/{slug}/install", status_code=204)
async def uninstall_skill(
    slug: str,
    _: Principal = Depends(require_principal),
    skills: CodexSkillsClient = Depends(get_codex_skills_client),
) -> None:
    skills.uninstall(slug)
    return None
