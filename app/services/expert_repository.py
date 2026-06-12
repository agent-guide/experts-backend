from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from app.db import DatabaseConnection
from app.domain.experts import Expert, ExpertMarketExpert
from app.services._sql import execute, fetch_all, fetch_one, json_param, rowcount


class ExpertRepository:
    """Raw SQL data access for experts and their skill / knowledge-base links."""

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
            {_EXPERT_SELECT}
            {where_sql}
            order by e.created_at desc, e.id asc
            """,
            params,
        )
        return self._map_experts(rows)

    def get(self, expert_id: str) -> Expert | None:
        row = fetch_one(
            self.connection,
            f"""
            {_EXPERT_SELECT}
            where e.id = ?
            limit 1
            """,
            (expert_id,),
        )
        if not row:
            return None
        return self._map_experts([row])[0]

    def list_market(self, *, category_id: str | None = None) -> list[ExpertMarketExpert]:
        where = ["e.status = 'published'"]
        params: list[Any] = []
        if category_id:
            where.append("e.category_id = ?")
            params.append(category_id)
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
              e.guide_questions,
              e.summon_button_text
            from experts e
            inner join expert_categories c on c.id = e.category_id
            where {' and '.join(where)}
            order by e.created_at desc, e.id asc
            """,
            params,
        )
        return [_map_market_expert(row) for row in rows]

    def get_market(self, expert_id: str) -> ExpertMarketExpert | None:
        row = fetch_one(
            self.connection,
            """
            select
              e.id,
              e.name,
              e.category_id,
              c.name as category_name,
              e.ability_intro,
              e.tags,
              e.guide_questions,
              e.summon_button_text
            from experts e
            inner join expert_categories c on c.id = e.category_id
            where e.id = ? and e.status = 'published'
            limit 1
            """,
            (expert_id,),
        )
        return _map_market_expert(row) if row else None

    def status_counts(self) -> dict[str, int]:
        rows = fetch_all(
            self.connection,
            """
            select status, count(*) as count
            from experts
            group by status
            """,
        )
        return {str(row["status"]): int(row["count"]) for row in rows}

    def category_exists(self, category_id: str) -> bool:
        row = fetch_one(
            self.connection,
            "select id from expert_categories where id = ? limit 1",
            (category_id,),
        )
        return row is not None

    def existing_skill_ids(self, skill_ids: list[str]) -> set[str]:
        if not skill_ids:
            return set()
        placeholders = ", ".join(["?"] * len(skill_ids))
        rows = fetch_all(
            self.connection,
            f"select id from skills where id in ({placeholders})",
            skill_ids,
        )
        return {str(row["id"]) for row in rows}

    def existing_knowledge_base_ids(self, knowledge_base_ids: list[str]) -> set[str]:
        if not knowledge_base_ids:
            return set()
        placeholders = ", ".join(["?"] * len(knowledge_base_ids))
        rows = fetch_all(
            self.connection,
            f"""
            select id from knowledge_bases
            where id in ({placeholders}) and deleted_at is null
            """,
            knowledge_base_ids,
        )
        return {str(row["id"]) for row in rows}

    def expert_group_exists(self, group_id: str) -> bool:
        row = fetch_one(
            self.connection,
            "select id from expert_groups where id = ? limit 1",
            (group_id,),
        )
        return row is not None

    def insert(
        self,
        *,
        expert_id: str,
        category_id: str,
        name: str,
        ability_intro: str,
        tags: list[str],
        status: str,
        guide_questions: list[str],
        summon_button_text: str | None,
    ) -> None:
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
                category_id,
                name,
                ability_intro,
                json_param(self.connection, tags),
                status,
                json_param(self.connection, guide_questions),
                summon_button_text,
            ),
        )

    def update(
        self,
        expert_id: str,
        *,
        category_id: str,
        name: str,
        ability_intro: str,
        tags: list[str],
        guide_questions: list[str],
        summon_button_text: str | None,
    ) -> None:
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
                category_id,
                name,
                ability_intro,
                json_param(self.connection, tags),
                json_param(self.connection, guide_questions),
                summon_button_text,
                expert_id,
            ),
        )

    def update_status(self, expert_id: str, status: str) -> None:
        execute(
            self.connection,
            """
            update experts
            set status = ?, updated_at = CURRENT_TIMESTAMP
            where id = ?
            """,
            (status, expert_id),
        )

    def delete(self, expert_id: str) -> int:
        # expert_skills / expert_knowledge_bases rows are removed by ON DELETE CASCADE
        # (foreign keys are enforced on both SQLite and PostgreSQL).
        cursor = execute(self.connection, "delete from experts where id = ?", (expert_id,))
        return rowcount(cursor)

    def replace_skills(self, expert_id: str, skill_ids: list[str]) -> None:
        execute(self.connection, "delete from expert_skills where expert_id = ?", (expert_id,))
        for skill_id in skill_ids:
            execute(
                self.connection,
                "insert into expert_skills (id, expert_id, skill_id) values (?, ?, ?)",
                (f"expert_skill_{uuid4().hex}", expert_id, skill_id),
            )

    def replace_knowledge_bases(self, expert_id: str, knowledge_base_ids: list[str]) -> None:
        execute(
            self.connection,
            "delete from expert_knowledge_bases where expert_id = ?",
            (expert_id,),
        )
        for knowledge_base_id in knowledge_base_ids:
            execute(
                self.connection,
                """
                insert into expert_knowledge_bases (id, expert_id, knowledge_base_id)
                values (?, ?, ?)
                """,
                (f"expert_kb_{uuid4().hex}", expert_id, knowledge_base_id),
            )

    def replace_primary_group(self, expert_id: str, group_id: str | None) -> None:
        execute(self.connection, "delete from expert_group_members where expert_id = ?", (expert_id,))
        if group_id is None:
            return
        execute(
            self.connection,
            """
            insert into expert_group_members (id, group_id, expert_id)
            values (?, ?, ?)
            """,
            (f"expert_group_member_{uuid4().hex}", group_id, expert_id),
        )

    def _map_experts(self, rows: list[dict[str, Any]]) -> list[Expert]:
        expert_ids = [str(row["id"]) for row in rows]
        # Batch-fetch links once for the whole page to avoid an N+1 query per expert.
        skills_by_expert = self._skill_ids_by_expert(expert_ids)
        kbs_by_expert = self._knowledge_base_ids_by_expert(expert_ids)
        groups_by_expert = self._primary_group_by_expert(expert_ids)
        experts = []
        for row in rows:
            expert_id = str(row["id"])
            group = groups_by_expert.get(expert_id)
            experts.append(
                Expert(
                    id=expert_id,
                    name=str(row["name"]),
                    categoryId=str(row["category_id"]),
                    categoryName=str(row["category_name"]),
                    groupId=group["id"] if group else None,
                    groupName=group["name"] if group else None,
                    abilityIntro=str(row["ability_intro"]),
                    tags=_json_string_list(row["tags"]),
                    status=str(row["status"]),
                    skillIds=skills_by_expert.get(expert_id, []),
                    knowledgeBaseIds=kbs_by_expert.get(expert_id, []),
                    guideQuestions=_json_string_list(row["guide_questions"]),
                    summonButtonText=(
                        str(row["summon_button_text"])
                        if row["summon_button_text"] is not None
                        else None
                    ),
                    createdAt=str(row["created_at"]),
                    updatedAt=str(row["updated_at"]),
                )
            )
        return experts

    def _primary_group_by_expert(self, expert_ids: list[str]) -> dict[str, dict[str, str]]:
        if not expert_ids:
            return {}
        placeholders = ", ".join(["?"] * len(expert_ids))
        rows = fetch_all(
            self.connection,
            f"""
            select egm.expert_id, g.id as group_id, g.name as group_name
            from expert_group_members egm
            inner join expert_groups g on g.id = egm.group_id
            where egm.expert_id in ({placeholders})
            order by egm.expert_id, g.sort_order asc, egm.created_at asc, g.id asc
            """,
            expert_ids,
        )
        grouped: dict[str, dict[str, str]] = {}
        for row in rows:
            expert_id = str(row["expert_id"])
            if expert_id not in grouped:
                grouped[expert_id] = {
                    "id": str(row["group_id"]),
                    "name": str(row["group_name"]),
                }
        return grouped

    def _skill_ids_by_expert(self, expert_ids: list[str]) -> dict[str, list[str]]:
        if not expert_ids:
            return {}
        placeholders = ", ".join(["?"] * len(expert_ids))
        rows = fetch_all(
            self.connection,
            f"""
            select expert_id, skill_id from expert_skills
            where expert_id in ({placeholders})
            order by expert_id, created_at asc, skill_id asc
            """,
            expert_ids,
        )
        grouped: dict[str, list[str]] = {}
        for row in rows:
            grouped.setdefault(str(row["expert_id"]), []).append(str(row["skill_id"]))
        return grouped

    def _knowledge_base_ids_by_expert(self, expert_ids: list[str]) -> dict[str, list[str]]:
        if not expert_ids:
            return {}
        placeholders = ", ".join(["?"] * len(expert_ids))
        # Knowledge bases are soft-deleted (deleted_at), so the join-table ON DELETE CASCADE only
        # fires at GC purge time. Filter deleted_at here so a soft-deleted KB never lingers in an
        # expert's knowledgeBaseIds.
        rows = fetch_all(
            self.connection,
            f"""
            select ekb.expert_id, kb.id as knowledge_base_id
            from expert_knowledge_bases ekb
            inner join knowledge_bases kb on kb.id = ekb.knowledge_base_id
            where ekb.expert_id in ({placeholders}) and kb.deleted_at is null
            order by ekb.expert_id, ekb.created_at asc, kb.id asc
            """,
            expert_ids,
        )
        grouped: dict[str, list[str]] = {}
        for row in rows:
            grouped.setdefault(str(row["expert_id"]), []).append(str(row["knowledge_base_id"]))
        return grouped


_EXPERT_SELECT = """
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
"""


def _json_string_list(value: Any) -> list[str]:
    # jsonb columns come back as a list on PostgreSQL and as a JSON text on SQLite.
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    return []


def _map_market_expert(row: dict[str, Any]) -> ExpertMarketExpert:
    return ExpertMarketExpert(
        id=str(row["id"]),
        name=str(row["name"]),
        categoryId=str(row["category_id"]),
        categoryName=str(row["category_name"]),
        abilityIntro=str(row["ability_intro"]),
        tags=_json_string_list(row["tags"]),
        guideQuestions=_json_string_list(row["guide_questions"]),
        summonButtonText=(
            str(row["summon_button_text"])
            if row["summon_button_text"] is not None
            else None
        ),
    )
