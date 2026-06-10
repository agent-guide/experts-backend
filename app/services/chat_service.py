from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from app.clients.ngent import NgentClient
from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.chat import (
    ChatSession,
    ChatTurnRequest,
    CreateSessionRequest,
    ResolvePermissionRequest,
)
from app.services.chat_repository import ChatRepository


class ChatService:
    """Local DB is the system of record; ngent is the compute engine.

    Sessions/turns are mirrored into chat_sessions/chat_turns so reads are tenant-scoped and
    survive ngent (whose SQLite store is single-node, unbacked, and enforces no isolation).
    """

    def __init__(self, connection: DatabaseConnection, ngent: NgentClient) -> None:
        self.connection = connection
        self.ngent = ngent
        self.repo = ChatRepository(connection)

    # --- Sessions -------------------------------------------------------------

    async def create_session(self, principal: Principal, request: CreateSessionRequest) -> ChatSession:
        agent_options = {"knowledgeBaseIds": request.knowledgeBaseIds}
        cwd = self.ngent.prepare_cwd(str(principal.active_tenant_id))
        data = await self.ngent.request(
            "POST",
            "/v1/threads",
            tenant_id=principal.active_tenant_id,
            json={
                "agent": self.ngent.default_agent,
                "cwd": cwd,
                "title": request.title,
                "agentOptions": agent_options,
            },
        )
        thread_id = data["threadId"]
        now = _now_iso()
        self.repo.create_session(
            session_id=thread_id,
            tenant_id=str(principal.active_tenant_id),
            user_id=principal.user_id,
            title=request.title,
            knowledge_base_ids=request.knowledgeBaseIds,
            agent_options=agent_options,
            now=now,
        )
        self.connection.commit()
        return ChatSession(
            id=thread_id,
            title=request.title,
            knowledgeBaseIds=request.knowledgeBaseIds,
            isPinned=False,
            createdAt=now,
            updatedAt=now,
        )

    def list_sessions(self, principal: Principal) -> list[ChatSession]:
        return self.repo.list_sessions(str(principal.active_tenant_id), principal.user_id)

    def get_session(self, principal: Principal, session_id: str) -> ChatSession:
        self._require_session(principal, session_id)
        # Re-read through list mapping for a consistent shape.
        sessions = {s.id: s for s in self.repo.list_sessions(str(principal.active_tenant_id), principal.user_id)}
        session = sessions.get(session_id)
        if session is None:
            raise _session_not_found()
        return session

    async def rename_session(self, principal: Principal, session_id: str, title: str) -> ChatSession:
        self._require_session(principal, session_id)
        try:
            await self.ngent.request(
                "PATCH",
                f"/v1/threads/{session_id}",
                tenant_id=principal.active_tenant_id,
                json={"title": title},
            )
        except ApiError:
            # Local store is authoritative; keep the rename even if ngent is unavailable.
            pass
        self.repo.update_session_title(session_id, title, _now_iso())
        self.connection.commit()
        return self.get_session(principal, session_id)

    def pin_session(self, principal: Principal, session_id: str, is_pinned: bool) -> ChatSession:
        self._require_session(principal, session_id)
        now = _now_iso()
        self.repo.set_session_pin(session_id, is_pinned, now if is_pinned else None, now)
        self.connection.commit()
        return self.get_session(principal, session_id)

    async def delete_session(self, principal: Principal, session_id: str) -> None:
        self._require_session(principal, session_id)
        try:
            await self.ngent.request(
                "DELETE", f"/v1/threads/{session_id}", tenant_id=principal.active_tenant_id
            )
        except ApiError:
            # Local store is authoritative; drop our record even if ngent already lost it.
            pass
        self.repo.delete_session(session_id)
        self.connection.commit()

    def list_messages(self, principal: Principal, session_id: str) -> list[dict]:
        self._require_session(principal, session_id)
        return [turn.model_dump() for turn in self.repo.list_turns(session_id)]

    # --- Turns ----------------------------------------------------------------

    async def stream_turn(
        self, principal: Principal, session_id: str, request: ChatTurnRequest
    ) -> AsyncIterator[str]:
        self._require_session(principal, session_id)
        tenant_id = principal.active_tenant_id
        payload = {
            "input": request.question,
            "stream": True,
        }

        # SSE parse state, accumulated while tee-ing the stream to the caller.
        current_event: str | None = None
        data_line = ""
        turn_id: str | None = None
        parts: list[str] = []
        stop_reason: str | None = None
        error_message: str | None = None

        def dispatch() -> None:
            nonlocal turn_id, stop_reason, error_message
            if not current_event:
                return
            try:
                data = json.loads(data_line) if data_line else {}
            except json.JSONDecodeError:
                data = {}
            if current_event == "turn_started":
                tid = data.get("turnId")
                if tid and turn_id is None:
                    turn_id = str(tid)
                    self.repo.create_turn(
                        turn_id=turn_id,
                        session_id=session_id,
                        tenant_id=str(tenant_id),
                        user_id=principal.user_id,
                        request_text=request.question,
                        model=request.llmModel,
                        knowledge_base_ids=request.knowledgeBaseIds,
                        query_rewrite=bool(request.queryRewrite),
                        multi_hop_config=request.multiHop,
                        now=_now_iso(),
                    )
                    self.connection.commit()
            elif current_event == "message_delta":
                delta = data.get("delta")
                if delta:
                    parts.append(str(delta))
            elif current_event == "error":
                error_message = str(data.get("message", "")) or "error"
            elif current_event == "turn_completed":
                reason = data.get("stopReason")
                stop_reason = str(reason) if reason is not None else None

        async for line in self.ngent.stream(
            "POST", f"/v1/threads/{session_id}/turns", tenant_id=tenant_id, json=payload
        ):
            if line.startswith("event:"):
                current_event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_line = line[len("data:"):].strip()
            elif line == "":
                dispatch()
                current_event = None
                data_line = ""
            yield f"{line}\n"

        # Tail flush in case the stream ends without a trailing blank line.
        dispatch()

        if turn_id is not None:
            if error_message is not None:
                status = "failed"
            elif stop_reason == "cancelled":
                status = "cancelled"
            else:
                status = "completed"
            self.repo.finalize_turn(
                turn_id=turn_id,
                status=status,
                response_text="".join(parts),
                stop_reason=stop_reason,
                error_message=error_message,
                completed_at=_now_iso(),
            )
            self.connection.commit()

    async def cancel_turn(self, principal: Principal, turn_id: str) -> dict:
        self._require_turn(principal, turn_id)
        data = await self.ngent.request(
            "POST", f"/v1/turns/{turn_id}/cancel", tenant_id=principal.active_tenant_id
        )
        return {"turnId": turn_id, "status": (data or {}).get("status", "cancelling")}

    async def stream_turn_events(
        self, principal: Principal, turn_id: str, after: int | None
    ) -> AsyncIterator[str]:
        self._require_turn(principal, turn_id)
        tenant_id = principal.active_tenant_id
        path = f"/v1/turns/{turn_id}/events"
        if after is not None:
            path += f"?after={after}"

        async def events() -> AsyncIterator[str]:
            async for line in self.ngent.stream("GET", path, tenant_id=tenant_id):
                yield f"{line}\n"

        return events()

    async def resolve_permission(
        self, principal: Principal, permission_id: str, body: ResolvePermissionRequest
    ) -> dict:
        payload = {
            k: v
            for k, v in {"outcome": body.outcome, "optionId": body.optionId}.items()
            if v is not None
        }
        data = await self.ngent.request(
            "POST",
            f"/v1/permissions/{permission_id}",
            tenant_id=principal.active_tenant_id,
            json=payload,
        )
        return data or {"permissionId": permission_id, "status": "resolved"}

    # --- Ownership guards -----------------------------------------------------

    def _require_session(self, principal: Principal, session_id: str) -> dict:
        row = self.repo.get_session_row(str(principal.active_tenant_id), principal.user_id, session_id)
        if row is None:
            raise _session_not_found()
        return row

    def _require_turn(self, principal: Principal, turn_id: str) -> dict:
        row = self.repo.get_turn_owner(turn_id)
        if (
            row is None
            or str(row.get("tenant_id")) != str(principal.active_tenant_id)
            or str(row.get("user_id")) != str(principal.user_id)
        ):
            raise ApiError(404, "CHAT_TURN_NOT_FOUND", "Chat turn not found")
        return row


def _session_not_found() -> ApiError:
    return ApiError(404, "CHAT_SESSION_NOT_FOUND", "Chat session not found")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
