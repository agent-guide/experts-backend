from __future__ import annotations

from uuid import uuid4

from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.experts import CreateExpertRequest, Expert, ExpertStatsResponse, UpdateExpertRequest
from app.services.expert_repository import ExpertRepository


class ExpertService:
    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection
        self.repo = ExpertRepository(connection)

    def list(
        self,
        *,
        name: str | None = None,
        category_id: str | None = None,
        status: str | None = None,
    ) -> list[Expert]:
        return self.repo.list(name=name, category_id=category_id, status=status)

    def stats(self) -> ExpertStatsResponse:
        counts = self.repo.status_counts()
        return ExpertStatsResponse(
            total=sum(counts.values()),
            published=counts.get("published", 0),
            draft=counts.get("draft", 0),
            unlisted=counts.get("unlisted", 0),
        )

    def get(self, expert_id: str) -> Expert:
        expert = self.repo.get(expert_id)
        if not expert:
            raise ApiError(404, "EXPERT_NOT_FOUND", "Expert not found")
        return expert

    def create(self, request: CreateExpertRequest) -> Expert:
        skill_ids = _unique_strings(request.skillIds)
        knowledge_base_ids = _unique_strings(request.knowledgeBaseIds)
        self._require_category(request.categoryId)
        self._require_skills(skill_ids)
        self._require_knowledge_bases(knowledge_base_ids)
        expert_id = f"expert_{uuid4().hex}"
        self.repo.insert(
            expert_id=expert_id,
            category_id=request.categoryId,
            name=request.name,
            ability_intro=request.abilityIntro,
            tags=_unique_strings(request.tags),
            status=request.status,
            guide_questions=_unique_strings(request.guideQuestions),
            summon_button_text=request.summonButtonText,
        )
        self.repo.replace_skills(expert_id, skill_ids)
        self.repo.replace_knowledge_bases(expert_id, knowledge_base_ids)
        self.connection.commit()
        return self.get(expert_id)

    def update(self, expert_id: str, request: UpdateExpertRequest) -> Expert:
        current = self.get(expert_id)
        next_category_id = (
            request.categoryId if request.categoryId is not None else current.categoryId
        )
        self._require_category(next_category_id)

        skill_ids = _unique_strings(request.skillIds) if request.skillIds is not None else None
        knowledge_base_ids = (
            _unique_strings(request.knowledgeBaseIds)
            if request.knowledgeBaseIds is not None
            else None
        )
        if skill_ids is not None:
            self._require_skills(skill_ids)
        if knowledge_base_ids is not None:
            self._require_knowledge_bases(knowledge_base_ids)

        self.repo.update(
            expert_id,
            category_id=next_category_id,
            name=request.name if request.name is not None else current.name,
            ability_intro=(
                request.abilityIntro if request.abilityIntro is not None else current.abilityIntro
            ),
            tags=_unique_strings(request.tags) if request.tags is not None else current.tags,
            guide_questions=(
                _unique_strings(request.guideQuestions)
                if request.guideQuestions is not None
                else current.guideQuestions
            ),
            summon_button_text=(
                request.summonButtonText
                if request.summonButtonText is not None
                else current.summonButtonText
            ),
        )
        if skill_ids is not None:
            self.repo.replace_skills(expert_id, skill_ids)
        if knowledge_base_ids is not None:
            self.repo.replace_knowledge_bases(expert_id, knowledge_base_ids)
        self.connection.commit()
        return self.get(expert_id)

    def update_status(self, expert_id: str, status: str) -> Expert:
        self.get(expert_id)
        self.repo.update_status(expert_id, status)
        self.connection.commit()
        return self.get(expert_id)

    def delete(self, expert_id: str) -> None:
        self.get(expert_id)
        if self.repo.delete(expert_id) <= 0:
            raise ApiError(404, "EXPERT_NOT_FOUND", "Expert not found")
        self.connection.commit()

    def _require_category(self, category_id: str) -> None:
        if not self.repo.category_exists(category_id):
            raise ApiError(404, "EXPERT_CATEGORY_NOT_FOUND", "Expert category not found")

    def _require_skills(self, skill_ids: list[str]) -> None:
        existing = self.repo.existing_skill_ids(skill_ids)
        missing = [skill_id for skill_id in skill_ids if skill_id not in existing]
        if missing:
            raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found", {"skillIds": missing})

    def _require_knowledge_bases(self, knowledge_base_ids: list[str]) -> None:
        existing = self.repo.existing_knowledge_base_ids(knowledge_base_ids)
        missing = [kb_id for kb_id in knowledge_base_ids if kb_id not in existing]
        if missing:
            raise ApiError(
                404,
                "KB_NOT_FOUND",
                "Knowledge base not found",
                {"knowledgeBaseIds": missing},
            )


def _unique_strings(values: list[str]) -> list[str]:
    return [value for value in dict.fromkeys(values) if value]
