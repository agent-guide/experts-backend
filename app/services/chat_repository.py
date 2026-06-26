from __future__ import annotations

from typing import Any

from app.db import DatabaseConnection
from app.domain.chat import ChatSession, ChatTurn
from app.services._sql import execute, fetch_all, fetch_one, json_param, rowcount


class ChatRepository:
    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection

    # --- Sessions -------------------------------------------------------------

    def create_session(
        self,
        *,
        session_id: str,
        tenant_id: str,
        user_id: str,
        title: str | None,
        agent_options: dict[str, Any],
        now: str,
    ) -> None:
        execute(
            self.connection,
            """
            insert into chat_sessions (
                id, tenant_id, user_id, title, agent_options,
                status, is_pinned, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, 'active', false, ?, ?)
            """,
            (
                session_id,
                tenant_id,
                user_id,
                title,
                json_param(self.connection, agent_options),
                now,
                now,
            ),
        )

    def get_session_row(self, tenant_id: str, user_id: str, session_id: str) -> dict[str, Any] | None:
        return fetch_one(
            self.connection,
            """
            select * from chat_sessions
            where id = ? and tenant_id = ? and user_id = ? and deleted_at is null
            limit 1
            """,
            (session_id, tenant_id, user_id),
        )

    def get_session(self, tenant_id: str, user_id: str, session_id: str) -> ChatSession | None:
        row = self.get_session_row(tenant_id, user_id, session_id)
        return _map_session(row) if row is not None else None

    def list_sessions(
        self, tenant_id: str, user_id: str, status: str = "active"
    ) -> list[ChatSession]:
        rows = fetch_all(
            self.connection,
            """
            select * from chat_sessions
            where tenant_id = ? and user_id = ? and status = ? and deleted_at is null
            order by is_pinned desc, pinned_at desc, updated_at desc
            """,
            (tenant_id, user_id, status),
        )
        return [_map_session(row) for row in rows]

    def update_session_title(self, session_id: str, title: str, now: str) -> bool:
        cursor = execute(
            self.connection,
            """
            update chat_sessions
            set title = ?, updated_at = ?
            where id = ? and deleted_at is null
            """,
            (title, now, session_id),
        )
        return rowcount(cursor) > 0

    def set_acp_session_id(self, session_id: str, acp_session_id: str | None, now: str) -> bool:
        cursor = execute(
            self.connection,
            "update chat_sessions set acp_session_id = ?, updated_at = ? where id = ?",
            (acp_session_id, now, session_id),
        )
        return rowcount(cursor) > 0

    def set_session_pin(self, session_id: str, is_pinned: bool, pinned_at: str | None, now: str) -> bool:
        cursor = execute(
            self.connection,
            """
            update chat_sessions
            set is_pinned = ?, pinned_at = ?, updated_at = ?
            where id = ? and deleted_at is null
            """,
            (is_pinned, pinned_at, now, session_id),
        )
        return rowcount(cursor) > 0

    def set_session_status(self, session_id: str, status: str, now: str) -> bool:
        cursor = execute(
            self.connection,
            """
            update chat_sessions
            set status = ?, updated_at = ?
            where id = ? and deleted_at is null
            """,
            (status, now, session_id),
        )
        return rowcount(cursor) > 0

    def delete_session(self, session_id: str, now: str) -> bool:
        cursor = execute(
            self.connection,
            """
            update chat_sessions
            set deleted_at = ?, updated_at = ?
            where id = ? and deleted_at is null
            """,
            (now, now, session_id),
        )
        return rowcount(cursor) > 0

    # --- Turns ----------------------------------------------------------------

    def create_turn(
        self,
        *,
        turn_id: str,
        session_id: str,
        tenant_id: str,
        user_id: str,
        request_text: str,
        model: str | None,
        query_rewrite: bool,
        multi_hop_config: dict[str, Any] | None,
        now: str,
    ) -> None:
        execute(
            self.connection,
            """
            insert into chat_turns (
                id, session_id, tenant_id, user_id, request_text, model,
                query_rewrite, multi_hop_config, status,
                is_internal, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, 'running', false, ?)
            """,
            (
                turn_id,
                session_id,
                tenant_id,
                user_id,
                request_text,
                model,
                query_rewrite,
                json_param(self.connection, multi_hop_config) if multi_hop_config is not None else None,
                now,
            ),
        )

    def finalize_turn(
        self,
        *,
        turn_id: str,
        status: str,
        response_text: str,
        reasoning_text: str,
        stop_reason: str | None,
        error_message: str | None,
        completed_at: str,
    ) -> bool:
        cursor = execute(
            self.connection,
            """
            update chat_turns
            set status = ?, response_text = ?, reasoning_text = ?, stop_reason = ?, error_message = ?, completed_at = ?
            where id = ?
            """,
            (status, response_text, reasoning_text, stop_reason, error_message, completed_at, turn_id),
        )
        return rowcount(cursor) > 0

    def get_turn_owner(self, turn_id: str) -> dict[str, Any] | None:
        return fetch_one(
            self.connection,
            """
            select t.id, t.session_id, t.tenant_id, t.user_id, t.status
            from chat_turns t
            join chat_sessions s on s.id = t.session_id
            where t.id = ? and s.deleted_at is null
            limit 1
            """,
            (turn_id,),
        )

    def get_turn(self, turn_id: str) -> ChatTurn | None:
        row = fetch_one(self.connection, "select * from chat_turns where id = ? limit 1", (turn_id,))
        return _map_turn(row) if row is not None else None

    def cancel_running_turn(self, turn_id: str, completed_at: str) -> bool:
        cursor = execute(
            self.connection,
            "update chat_turns set status = 'cancelled', completed_at = ? where id = ? and status = 'running'",
            (completed_at, turn_id),
        )
        return rowcount(cursor) > 0

    def list_turns(self, session_id: str) -> list[ChatTurn]:
        rows = fetch_all(
            self.connection,
            "select * from chat_turns where session_id = ? order by created_at asc",
            (session_id,),
        )
        return [_map_turn(row) for row in rows]


def _map_session(row: dict[str, Any]) -> ChatSession:
    return ChatSession(
        id=str(row["id"]),
        title=str(row["title"]) if row.get("title") is not None else None,
        status=str(row.get("status", "active")),
        isPinned=bool(row.get("is_pinned")),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _map_turn(row: dict[str, Any]) -> ChatTurn:
    return ChatTurn(
        id=str(row["id"]),
        sessionId=str(row["session_id"]),
        requestText=str(row["request_text"]),
        reasoningText=str(row["reasoning_text"]) if row.get("reasoning_text") is not None else None,
        responseText=str(row["response_text"]) if row.get("response_text") is not None else None,
        model=str(row["model"]) if row.get("model") is not None else None,
        status=str(row["status"]),
        stopReason=str(row["stop_reason"]) if row.get("stop_reason") is not None else None,
        errorMessage=str(row["error_message"]) if row.get("error_message") is not None else None,
        createdAt=str(row["created_at"]),
        completedAt=str(row["completed_at"]) if row.get("completed_at") is not None else None,
    )
