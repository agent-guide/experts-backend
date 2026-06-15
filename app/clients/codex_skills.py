from pathlib import Path
from zipfile import ZipFile

from app.core.config import Settings
from app.core.errors import ApiError
from app.domain.skills import SkillSummary


class CodexSkillsClient:
    def __init__(self, settings: Settings) -> None:
        base = Path(settings.codex_skills_dir or Path(settings.codex_home) / "skills")
        self.skills_dir = base.expanduser()

    def list_installed(self) -> list[SkillSummary]:
        if not self.skills_dir.exists():
            return []
        items: list[SkillSummary] = []
        for child in sorted(self.skills_dir.iterdir()):
            if not child.is_dir():
                continue
            skill_md = child / "SKILL.md"
            items.append(
                SkillSummary(
                    slug=child.name,
                    name=child.name,
                    description=self._read_description(skill_md),
                    installed=True,
                )
            )
        return items

    def get_file(self, slug: str, file_path: str = "SKILL.md") -> bytes:
        path = self._skill_path(slug) / file_path
        if not path.exists() or not path.is_file():
            raise ApiError(404, "SKILL_FILE_NOT_FOUND", "Skill file not found")
        return path.read_bytes()

    def install_zip(self, slug: str, zip_bytes: bytes) -> SkillSummary:
        target = self._skill_path(slug)
        if target.exists():
            raise ApiError(409, "SKILL_EXISTS", "Skill already exists")
        target.mkdir(parents=True, exist_ok=False)
        archive_path = target / "_upload.zip"
        archive_path.write_bytes(zip_bytes)
        try:
            with ZipFile(archive_path) as archive:
                archive.extractall(target)
        finally:
            archive_path.unlink(missing_ok=True)
        if not (target / "SKILL.md").exists():
            raise ApiError(400, "SKILL_INVALID", "Uploaded skill must include SKILL.md")
        return SkillSummary(slug=slug, name=slug, description=self._read_description(target / "SKILL.md"))

    def uninstall(self, slug: str) -> None:
        target = self._skill_path(slug)
        if not target.exists():
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found")
        for path in sorted(target.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        target.rmdir()

    def _skill_path(self, slug: str) -> Path:
        if "/" in slug or ".." in slug:
            raise ApiError(400, "SKILL_INVALID_SLUG", "Invalid skill slug")
        return self.skills_dir / slug

    @staticmethod
    def _read_description(skill_md: Path) -> str | None:
        if not skill_md.exists():
            return None
        for line in skill_md.read_text("utf-8", errors="ignore").splitlines():
            if line.strip().startswith("description:"):
                return line.split(":", 1)[1].strip().strip("\"'")
        return None
