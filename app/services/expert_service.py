from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.experts import CreateExpertRequest, Expert, ExpertStatsResponse, UpdateExpertRequest
from app.services._sql import execute, fetch_all, fetch_one, json_load, json_param, rowcount


class ExpertService:
    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection

    def list(
        self,
        *,
        name: str | None = None,
        category_id: str | None = None,
        status: str | None = None,
    ) -> list[Expert]:
        where = []
        params: list[Any] = []
        if name:
            where.append("lower(e.name) like ?")
            params.append(f"%{name.casefold()}%")
        if category_id:
            where.append("e.category_id = ?")
            params.append(category_id)
        if status:
            where.append("e.status = ?")
            params.append(status)
        where_sql = f"where {' and '.join(where)}" if where else ""
        rows = fetch_all(
            self.connection,
            f"""
            select
              e.id,
              e.name,
              e.category_id,
              c.name as category_name,
              e.ability_intro,
              e.tags,
              e.status,
              e.guide_questions,
              e.summon_button_text,
              e.created_at,
              e.updated_at
            from experts e
            inner join expert_categories c on c.id = e.category_id
            {where_sql}
            order by e.created_at desc, e.id asc
            """,
            params,
        )
        return [self._map_expert(row) for row in rows]

    def stats(self) -> ExpertStatsResponse:
        rows = fetch_all(
            self.connection,
            """
            select status, count(*) as count
            from experts
            group by status
            """,
        )
        counts = {str(row["status"]): int(row["count"]) for row in rows}
        return ExpertStatsResponse(
            total=sum(counts.values()),
            published=counts.get("published", 0),
            draft=counts.get("draft", 0),
            unlisted=counts.get("unlisted", 0),
        )

    def get(self, expert_id: str) -> Expert:
        row = self._expert_row(expert_id)
        if not row:
            raise ApiError(404, "EXPERT_NOT_FOUND", "Expert not found")
        return self._map_expert(row)

    def create(self, request: CreateExpertRequest) -> Expert:
        self._require_category(request.categoryId)
        self._require_skills(request.skillIds)
        self._require_knowledge_bases(request.knowledgeBaseIds)
        expert_id = f"expert_{uuid4().hex}"
        execute(
            self.connection,
            """
            insert into experts (
              id, category_id, name, ability_intro, tags, status,
              guide_questions, summon_button_text
            )
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                expert_id,
                request.categoryId,
                request.name,
                request.abilityIntro,
                json_param(self.connection, _unique_strings(request.tags)),
                request.status,
                json_param(self.connection, _unique_strings(request.guideQuestions)),
                request.summonButtonText,
            ),
        )
        self._replace_skills(expert_id, request.skillIds)
        self._replace_knowledge_bases(expert_id, request.knowledgeBaseIds)
        self.connection.commit()
        return self.get(expert_id)

    def update(self, expert_id: str, request: UpdateExpertRequest) -> Expert:
        current = self.get(expert_id)
        next_category_id = request.categoryId if request.categoryId is not None else current.categoryId
        self._require_category(next_category_id)
        if request.skillIds is not None:
            self._require_skills(request.skillIds)
        if request.knowledgeBaseIds is not None:
            self._require_knowledge_bases(request.knowledgeBaseIds)

        execute(
            self.connection,
            """
            update experts
            set category_id = ?,
                name = ?,
                ability_intro = ?,
                tags = ?,
                guide_questions = ?,
                summon_button_text = ?,
                updated_at = CURRENT_TIMESTAMP
            where id = ?
            """,
            (
                next_category_id,
                request.name if request.name is not None else current.name,
                (
                    request.abilityIntro
                    if request.abilityIntro is not None
                    else current.abilityIntro
                ),
                json_param(
                    self.connection,
                    _unique_strings(request.tags) if request.tags is not None else current.tags,
                ),
                json_param(
                    self.connection,
                    (
                        _unique_strings(request.guideQuestions)
                        if request.guideQuestions is not None
                        else current.guideQuestions
                    ),
                ),
                (
                    request.summonButtonText
                    if request.summonButtonText is not None
                    else current.summonButtonText
                ),
                expert_id,
            ),
        )
        if request.skillIds is not None:
            self._replace_skills(expert_id, request.skillIds)
        if request.knowledgeBaseIds is not None:
            self._replace_knowledge_bases(expert_id, request.knowledgeBaseIds)
        self.connection.commit()
        return self.get(expert_id)

    def update_status(self, expert_id: str, status: str) -> Expert:
        self.get(expert_id)
        execute(
            self.connection,
            """
            update experts
            set status = ?, updated_at = CURRENT_TIMESTAMP
            where id = ?
            """,
            (status, expert_id),
        )
        self.connection.commit()
        return self.get(expert_id)

    def delete(self, expert_id: str) -> None:
        self.get(expert_id)
        execute(self.connection, "delete from expert_skills where expert_id = ?", (expert_id,))
        execute(
            self.connection,
            "delete from expert_knowledge_bases where expert_id = ?",
            (expert_id,),
        )
        cursor = execute(self.connection, "delete from experts where id = ?", (expert_id,))
        if rowcount(cursor) <= 0:
            raise ApiError(404, "EXPERT_NOT_FOUND", "Expert not found")
        self.connection.commit()

    def _expert_row(self, expert_id: str) -> dict[str, Any] | None:
        return fetch_one(
            self.connection,
            """
            select
              e.id,
              e.name,
              e.category_id,
              c.name as category_name,
              e.ability_intro,
              e.tags,
              e.status,
              e.guide_questions,
              e.summon_button_text,
              e.created_at,
              e.updated_at
            from experts e
            inner join expert_categories c on c.id = e.category_id
            where e.id = ?
            limit 1
            """,
            (expert_id,),
        )

    def _map_expert(self, row: dict[str, Any]) -> Expert:
        expert_id = str(row["id"])
        return Expert(
            id=expert_id,
            name=str(row["name"]),
            categoryId=str(row["category_id"]),
            categoryName=str(row["category_name"]),
            abilityIntro=str(row["ability_intro"]),
            tags=_json_string_list(row["tags"]),
            status=str(row["status"]),
            skillIds=self._list_skill_ids(expert_id),
            knowledgeBaseIds=self._list_knowledge_base_ids(expert_id),
            guideQuestions=_json_string_list(row["guide_questions"]),
            summonButtonText=(
                str(row["summon_button_text"])
                if row["summon_button_text"] is not None
                else None
            ),
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )

    def _replace_skills(self, expert_id: str, skill_ids: list[str]) -> None:
        execute(self.connection, "delete from expert_skills where expert_id = ?", (expert_id,))
        for skill_id in _unique_strings(skill_ids):
            execute(
                self.connection,
                """
                insert into expert_skills (id, expert_id, skill_id)
                values (?, ?, ?)
                """,
                (f"expert_skill_{uuid4().hex}", expert_id, skill_id),
            )

    def _replace_knowledge_bases(self, expert_id: str, knowledge_base_ids: list[str]) -> None:
        execute(
            self.connection,
            "delete from expert_knowledge_bases where expert_id = ?",
            (expert_id,),
        )
        for knowledge_base_id in _unique_strings(knowledge_base_ids):
            execute(
                self.connection,
                """
                insert into expert_knowledge_bases (id, expert_id, knowledge_base_id)
                values (?, ?, ?)
                """,
                (f"expert_kb_{uuid4().hex}", expert_id, knowledge_base_id),
            )

    def _list_skill_ids(self, expert_id: str) -> list[str]:
        rows = fetch_all(
            self.connection,
            """
            select skill_id from expert_skills
            where expert_id = ?
            order by created_at asc, skill_id asc
            """,
            (expert_id,),
        )
        return [str(row["skill_id"]) for row in rows]

    def _list_knowledge_base_ids(self, expert_id: str) -> list[str]:
        rows = fetch_all(
            self.connection,
            """
            select knowledge_base_id from expert_knowledge_bases
            where expert_id = ?
            order by created_at asc, knowledge_base_id asc
            """,
            (expert_id,),
        )
        return [str(row["knowledge_base_id"]) for row in rows]

    def _require_category(self, category_id: str) -> None:
        row = fetch_one(
            self.connection,
            "select id from expert_categories where id = ? limit 1",
            (category_id,),
        )
        if not row:
            raise ApiError(404, "EXPERT_CATEGORY_NOT_FOUND", "Expert category not found")

    def _require_skills(self, skill_ids: list[str]) -> None:
        for skill_id in _unique_strings(skill_ids):
            row = fetch_one(
                self.connection,
                "select id from skills where id = ? limit 1",
                (skill_id,),
            )
            if not row:
                raise ApiError(404, "SKILL_NOT_FOUND", "Skill not found", {"skillId": skill_id})

    def _require_knowledge_bases(self, knowledge_base_ids: list[str]) -> None:
        for knowledge_base_id in _unique_strings(knowledge_base_ids):
            row = fetch_one(
                self.connection,
                """
                select id from knowledge_bases
                where id = ? and deleted_at is null
                limit 1
                """,
                (knowledge_base_id,),
            )
            if not row:
                raise ApiError(
                    404,
                    "KB_NOT_FOUND",
                    "Knowledge base not found",
                    {"knowledgeBaseId": knowledge_base_id},
                )


def _unique_strings(values: list[str]) -> list[str]:
    return [value for value in dict.fromkeys(values) if value]


def _json_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    if isinstance(value, str):
        try:
            raw = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(raw, list):
            return [str(item) for item in raw if isinstance(item, str)]
    parsed = json_load(value)
    if isinstance(parsed, list):
        return [str(item) for item in parsed if isinstance(item, str)]
    return []
