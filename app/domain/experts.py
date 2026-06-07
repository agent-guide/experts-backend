from typing import Literal

from pydantic import BaseModel, Field


ExpertStatus = Literal["published", "draft", "unlisted"]


class ExpertCategory(BaseModel):
    id: str
    name: str
    description: str | None = None
    createdAt: str
    updatedAt: str


class CreateExpertCategoryRequest(BaseModel):
    name: str
    description: str | None = None


class UpdateExpertCategoryRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class ExpertCategoryListResponse(BaseModel):
    items: list[ExpertCategory]


class Expert(BaseModel):
    id: str
    name: str
    categoryId: str
    categoryName: str
    abilityIntro: str
    tags: list[str] = Field(default_factory=list)
    status: ExpertStatus
    skillIds: list[str] = Field(default_factory=list)
    knowledgeBaseIds: list[str] = Field(default_factory=list)
    guideQuestions: list[str] = Field(default_factory=list, max_length=3)
    summonButtonText: str | None = None
    createdAt: str
    updatedAt: str


class CreateExpertRequest(BaseModel):
    name: str
    categoryId: str
    abilityIntro: str
    tags: list[str] = Field(default_factory=list)
    status: ExpertStatus = "draft"
    skillIds: list[str] = Field(default_factory=list)
    knowledgeBaseIds: list[str] = Field(default_factory=list)
    guideQuestions: list[str] = Field(default_factory=list, max_length=3)
    summonButtonText: str | None = None


class UpdateExpertRequest(BaseModel):
    name: str | None = None
    categoryId: str | None = None
    abilityIntro: str | None = None
    tags: list[str] | None = None
    skillIds: list[str] | None = None
    knowledgeBaseIds: list[str] | None = None
    guideQuestions: list[str] | None = Field(default=None, max_length=3)
    summonButtonText: str | None = None


class UpdateExpertStatusRequest(BaseModel):
    status: ExpertStatus


class ExpertListResponse(BaseModel):
    items: list[Expert]


class ExpertStatsResponse(BaseModel):
    total: int
    published: int
    draft: int
    unlisted: int
