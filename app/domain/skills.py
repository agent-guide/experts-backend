from pydantic import BaseModel, Field


class SkillMetadataUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)
    version: str | None = None
    allowedTools: list[str] | None = None
    tags: list[str] | None = None


class Skill(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    version: str | None = None
    allowedTools: list[str] = Field(default_factory=list)
    filePaths: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    storageUri: str
    createdAt: str
    updatedAt: str


class SkillListResponse(BaseModel):
    items: list[Skill]
    limit: int
    offset: int
