from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.db import DatabaseConnection
from app.domain.plans import ExpertGroup
from app.services._sql import execute, fetch_all, fetch_one, rowcount


class ExpertGroupRepository:
    """Raw SQL data access for expert authorization groups."""

    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection

    def list(self) -> list[ExpertGroup]:
        rows = fetch_all(
            self.connection,
            """
            select id, code, name, description, sort_order, created_at, updated_at
            from expert_groups
            order by sort_order asc, created_at asc, id asc
            """,
        )
        return self._map_groups(rows)

    def list_by_ids(self, group_ids: list[str]) -> list[ExpertGroup]:
        if not group_ids:
            return []
        placeholders = ", ".join(["?"] * len(group_ids))
        rows = fetch_all(
            self.connection,
            f"""
            select id, code, name, description, sort_order, created_at, updated_at
            from expert_groups
            where id in ({placeholders})
            order by sort_order asc, created_at asc, id asc
            """,
            group_ids,
        )
        return self._map_groups(rows)

    def list_for_plan(self, plan_id: str) -> list[ExpertGroup]:
        rows = fetch_all(
            self.connection,
            """
            select g.id, g.code, g.name, g.description, g.sort_order, g.created_at, g.updated_at
            from expert_groups g
            inner join plan_expert_groups peg on peg.group_id = g.id
            where peg.plan_id = ?
            order by g.sort_order asc, g.created_at asc, g.id asc
            """,
            (plan_id,),
        )
        return self._map_groups(rows)

    def get(self, group_id: str) -> ExpertGroup | None:
        row = fetch_one(
            self.connection,
            """
            select id, code, name, description, sort_order, created_at, updated_at
            from expert_groups
            where id = ?
            limit 1
            """,
            (group_id,),
        )
        groups = self._map_groups([row]) if row else []
        return groups[0] if groups else None

    def insert(
        self,
        *,
        group_id: str,
        code: str,
        name: str,
        description: str | None,
        sort_order: int,
    ) -> None:
        execute(
            self.connection,
            """
            insert into expert_groups (id, code, name, description, sort_order)
            values (?, ?, ?, ?, ?)
            """,
            (group_id, code, name, description, sort_order),
        )

    def update(
        self,
        group_id: str,
        *,
        code: str,
        name: str,
        description: str | None,
        sort_order: int,
    ) -> None:
        execute(
            self.connection,
            """
            update expert_groups
            set code = ?, name = ?, description = ?, sort_order = ?, updated_at = CURRENT_TIMESTAMP
            where id = ?
            """,
            (code, name, description, sort_order, group_id),
        )

    def delete(self, group_id: str) -> int:
        cursor = execute(self.connection, "delete from expert_groups where id = ?", (group_id,))
        return rowcount(cursor)

    def is_used_by_plan(self, group_id: str) -> bool:
        row = fetch_one(
            self.connection,
            "select id from plan_expert_groups where group_id = ? limit 1",
            (group_id,),
        )
        return row is not None

    def existing_group_ids(self, group_ids: list[str]) -> set[str]:
        if not group_ids:
            return set()
        placeholders = ", ".join(["?"] * len(group_ids))
        rows = fetch_all(
            self.connection,
            f"select id from expert_groups where id in ({placeholders})",
            group_ids,
        )
        return {str(row["id"]) for row in rows}

    def existing_expert_ids(self, expert_ids: list[str]) -> set[str]:
        if not expert_ids:
            return set()
        placeholders = ", ".join(["?"] * len(expert_ids))
        rows = fetch_all(
            self.connection,
            f"select id from experts where id in ({placeholders})",
            expert_ids,
        )
        return {str(row["id"]) for row in rows}

    def replace_members(self, group_id: str, expert_ids: list[str]) -> None:
        execute(self.connection, "delete from expert_group_members where group_id = ?", (group_id,))
        for expert_id in expert_ids:
            execute(
                self.connection,
                """
                insert into expert_group_members (id, group_id, expert_id)
                values (?, ?, ?)
                """,
                (f"expert_group_member_{uuid4().hex}", group_id, expert_id),
            )

    def _map_groups(self, rows: list[dict[str, Any]]) -> list[ExpertGroup]:
        group_ids = [str(row["id"]) for row in rows]
        members = self._expert_ids_by_group(group_ids)
        return [
            ExpertGroup(
                id=str(row["id"]),
                code=str(row["code"]),
                name=str(row["name"]),
                description=str(row["description"]) if row["description"] is not None else None,
                sortOrder=int(row["sort_order"]),
                expertIds=members.get(str(row["id"]), []),
                createdAt=str(row["created_at"]),
                updatedAt=str(row["updated_at"]),
            )
            for row in rows
        ]

    def _expert_ids_by_group(self, group_ids: list[str]) -> dict[str, list[str]]:
        if not group_ids:
            return {}
        placeholders = ", ".join(["?"] * len(group_ids))
        rows = fetch_all(
            self.connection,
            f"""
            select group_id, expert_id
            from expert_group_members
            where group_id in ({placeholders})
            order by group_id, created_at asc, expert_id asc
            """,
            group_ids,
        )
        grouped: dict[str, list[str]] = {}
        for row in rows:
            grouped.setdefault(str(row["group_id"]), []).append(str(row["expert_id"]))
        return grouped
