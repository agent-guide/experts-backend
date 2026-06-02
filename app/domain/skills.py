from pydantic import BaseModel


class InstallSkillRequest(BaseModel):
    source: str | None = None


class SkillSummary(BaseModel):
    slug: str
    name: str
    description: str | None = None
    installed: bool = True
