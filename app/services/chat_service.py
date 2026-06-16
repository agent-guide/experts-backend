from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import uuid4

from app.clients.acp_admin import AcpAdminClient
from app.clients.acp_gateway import AcpGatewayClient
from app.clients.ngent import NgentClient
from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.chat import (
    ChatSession,
    ChatSessionStatus,
    ChatTurnRequest,
    CreateSessionRequest,
    ResolvePermissionRequest,
)
from app.services.chat_repository import ChatRepository, _json_list


class ChatService:
    """Local DB is the system of record; the compute engine is pluggable.

    Sessions/turns are mirrored into chat_sessions/chat_turns so reads are tenant-scoped and
    survive the engine. Two backends are supported, selected by `backend`:

    - "ngent": thread/turn are server-side resources. The thread id is assigned by ngent on
      create; the turn id arrives in the `turn_started` stream event.
    - "acp": the agent-gateway ACP data plane exposes only POST {prefix}/turn and
      POST {prefix}/permission. The thread id is generated locally at create time (no upstream
      call); a turn has no server id, so one is generated locally. The agent-assigned ACP
      session id arrives via the first turn's `session` event and is echoed back on later turns
      to resume the same instance. ACP events are translated to the same public SSE contract
      ngent exposes (turn_started -> message_delta -> turn_completed / error / permission_required)
      so callers do not change.
    """

    def __init__(
        self,
        connection: DatabaseConnection,
        *,
        backend: str = "ngent",
        ngent: NgentClient | None = None,
        acp: AcpGatewayClient | None = None,
        acp_admin: AcpAdminClient | None = None,
    ) -> None:
        self.connection = connection
        self.backend = backend
        self.ngent = ngent
        self.acp = acp
        self.acp_admin = acp_admin
        self.repo = ChatRepository(connection)

    def _require_acp(self) -> AcpGatewayClient:
        if self.acp is None:
            raise ApiError(503, "ACP_UNCONFIGURED", "acp gateway client is not configured")
        return self.acp

    def _require_ngent(self) -> NgentClient:
        if self.ngent is None:
            raise ApiError(503, "NGENT_UNCONFIGURED", "ngent client is not configured")
        return self.ngent

    # --- Sessions -------------------------------------------------------------

    async def create_session(self, principal: Principal, request: CreateSessionRequest) -> ChatSession:
        agent_options = {"knowledgeBaseIds": request.knowledgeBaseIds}
        now = _now_iso()
        if self.backend == "acp":
            # The ACP data plane has no thread-create endpoint: the agent materializes a session
            # lazily on the first turn. Generate the caller-owned thread id locally.
            thread_id = f"thread_{uuid4().hex}"
        else:
            cwd = self._require_ngent().prepare_cwd(str(principal.active_tenant_id))
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
            status="active",
            isPinned=False,
            createdAt=now,
            updatedAt=now,
        )

    def list_sessions(
        self, principal: Principal, status: ChatSessionStatus = "active"
    ) -> list[ChatSession]:
        return self.repo.list_sessions(str(principal.active_tenant_id), principal.user_id, status)

    def get_session(self, principal: Principal, session_id: str) -> ChatSession:
        session = self.repo.get_session(str(principal.active_tenant_id), principal.user_id, session_id)
        if session is None:
            raise _session_not_found()
        return session

    async def rename_session(self, principal: Principal, session_id: str, title: str) -> ChatSession:
        self._require_session(principal, session_id)
        # The ACP data plane has no thread-rename endpoint; title is a local-only concept there.
        if self.backend != "acp":
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

    def archive_session(
        self, principal: Principal, session_id: str, archived: bool
    ) -> ChatSession:
        self._require_session(principal, session_id)
        now = _now_iso()
        self.repo.set_session_status(session_id, "archived" if archived else "active", now)
        self.connection.commit()
        return self.get_session(principal, session_id)

    async def delete_session(self, principal: Principal, session_id: str) -> None:
        self._require_session(principal, session_id)

        # The ACP data plane has no thread-delete endpoint (sessions are evicted via the admin
        # plane); the local store is authoritative, so drop our record either way.
        if self.backend != "acp":
            try:
                await self.ngent.request(
                    "DELETE", f"/v1/threads/{session_id}", tenant_id=principal.active_tenant_id
                )
            except ApiError:
                # Local store is authoritative; drop our record even if ngent already lost it.
                pass
        self.repo.delete_session(session_id, _now_iso())
        self.connection.commit()

    def list_messages(self, principal: Principal, session_id: str) -> list[dict]:
        self._require_session(principal, session_id)
        return [turn.model_dump() for turn in self.repo.list_turns(session_id)]

    async def get_transcript(self, principal: Principal, session_id: str) -> dict:
        """Replay a session's conversation history.

        For the ACP backend the agent-side transcript (coalesced user/assistant/reasoning
        messages) is loaded from the gateway admin plane when a session has been materialized and
        the admin plane is configured; otherwise it falls back to the durable local turn records.
        ngent has no session-transcript admin endpoint, so it always uses the local records. The
        shape is uniform: {sessionId, messages: [{role, text}], source: "agent" | "local"}.
        """
        row = self._require_session(principal, session_id)
        acp_session_id = str(row["acp_session_id"]) if row.get("acp_session_id") else None
        if self.backend == "acp" and acp_session_id and self.acp_admin is not None:
            cwd = self._require_acp().prepare_cwd(str(principal.active_tenant_id))
            data = await self.acp_admin.get_transcript(session_id=acp_session_id, cwd=cwd)
            messages = list((data or {}).get("messages") or [])
            return {"sessionId": session_id, "messages": messages, "source": "agent"}
        return {"sessionId": session_id, "messages": self._local_transcript(session_id), "source": "local"}

    def _local_transcript(self, session_id: str) -> list[dict]:
        messages: list[dict] = []
        for turn in self.repo.list_turns(session_id):
            messages.append({"role": "user", "text": turn.requestText})
            if turn.responseText:
                messages.append({"role": "assistant", "text": turn.responseText})
        return messages

    # --- Turns ----------------------------------------------------------------

    async def stream_turn(
        self, principal: Principal, session_id: str, request: ChatTurnRequest
    ) -> AsyncIterator[str]:
        if self.backend == "acp":
            async for line in self._stream_turn_acp(principal, session_id, request):
                yield line
            return
        async for line in self._stream_turn_ngent(principal, session_id, request):
            yield line

    async def _stream_turn_ngent(
        self, principal: Principal, session_id: str, request: ChatTurnRequest
    ) -> AsyncIterator[str]:
        row = self._require_session(principal, session_id)
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
        # Auto session title: the agent's generated title rides the turn stream as a
        # `session_info_update` event. Persist it only while the local title is still empty so a
        # user's manual rename is never clobbered.
        local_title = str(row.get("title") or "").strip()
        pending_title: str | None = None

        def dispatch() -> None:
            nonlocal turn_id, stop_reason, error_message, pending_title
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
                    # ngent's turn API takes only the prompt, so model / knowledge-base /
                    # retrieval options are not part of a turn request and are stored as
                    # defaults -- persisting caller-supplied values would record options that
                    # never reached the engine.
                    self.repo.create_turn(
                        turn_id=turn_id,
                        session_id=session_id,
                        tenant_id=str(tenant_id),
                        user_id=principal.user_id,
                        request_text=request.question,
                        model=None,
                        knowledge_base_ids=[],
                        query_rewrite=False,
                        multi_hop_config=None,
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
            elif current_event == "session_info_update":
                title = str(data.get("title") or "").strip()
                if title:
                    pending_title = title

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
            # Flush a captured title as its own frame, emitted after the blank line that
            # terminates the upstream frame so SSE framing stays valid.
            if pending_title is not None:
                if not local_title:
                    self.repo.update_session_title(session_id, pending_title, _now_iso())
                    self.connection.commit()
                    local_title = pending_title
                    yield _sse("session_title_updated", {"title": pending_title})
                pending_title = None

        # Tail flush in case the stream ends without a trailing blank line.
        dispatch()
        if pending_title is not None and not local_title:
            self.repo.update_session_title(session_id, pending_title, _now_iso())
            self.connection.commit()
            local_title = pending_title
            yield _sse("session_title_updated", {"title": pending_title})

        if turn_id is not None:
            self._finalize(turn_id, parts, stop_reason, error_message)

    async def _stream_turn_acp(
        self, principal: Principal, session_id: str, request: ChatTurnRequest
    ) -> AsyncIterator[str]:
        row = self._require_session(principal, session_id)
        acp = self._require_acp()
        tenant_id = principal.active_tenant_id
        acp_session_id = str(row["acp_session_id"]) if row.get("acp_session_id") else None
        knowledge_base_ids = _json_list(row.get("knowledge_base_ids"))
        cwd = acp.prepare_cwd(str(tenant_id))

        # The ACP data plane has no server turn id; generate one up front and persist immediately
        # so the public contract still opens with turn_started before any text.
        turn_id = f"turn_{uuid4().hex}"
        self.repo.create_turn(
            turn_id=turn_id,
            session_id=session_id,
            tenant_id=str(tenant_id),
            user_id=principal.user_id,
            request_text=request.question,
            model=acp.default_model,
            knowledge_base_ids=knowledge_base_ids,
            query_rewrite=False,
            multi_hop_config=None,
            now=_now_iso(),
        )
        self.connection.commit()
        yield _sse("turn_started", {"turnId": turn_id})

        parts: list[str] = []
        stop_reason: str | None = None
        error_message: str | None = None
        bound_session_id = acp_session_id
        current_event: str | None = None
        data_line = ""
        # Auto session title: the gateway replays the agent's title as a `session_info` event at
        # turn start. Persist it only while the local title is still empty so a user's manual
        # rename is never clobbered.
        local_title = str(row.get("title") or "").strip()

        async for line in acp.stream_turn(
            thread_id=session_id,
            input=request.question,
            tenant_id=tenant_id,
            session_id=acp_session_id,
            cwd=cwd,
            config_overrides=_acp_config_overrides(knowledge_base_ids),
        ):
            if line.startswith("event:"):
                current_event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_line = line[len("data:"):].strip()
            elif line == "":
                if current_event:
                    try:
                        data = json.loads(data_line) if data_line else {}
                    except json.JSONDecodeError:
                        data = {}
                    if current_event == "session":
                        sid = str(data.get("session_id") or "").strip()
                        if sid and sid != bound_session_id:
                            # Persist the agent-assigned id so follow-up turns resume this instance.
                            bound_session_id = sid
                            self.repo.set_acp_session_id(session_id, sid, _now_iso())
                            self.connection.commit()
                    elif current_event == "delta":
                        text = data.get("text")
                        if text:
                            parts.append(str(text))
                            yield _sse("message_delta", {"delta": str(text)})
                    elif current_event == "permission":
                        # Translate to ngent's permission_required shape; the request id replaces
                        # ngent's permissionId and the ACP options ride along under `data`.
                        payload: dict = {"permissionId": data.get("request_id")}
                        if data.get("data") is not None:
                            payload["data"] = data["data"]
                        yield _sse("permission_required", payload)
                    elif current_event == "error":
                        error_message = str(data.get("message") or "") or "error"
                        yield _sse("error", {"message": error_message})
                    elif current_event == "done":
                        reason = data.get("stop_reason")
                        stop_reason = str(reason) if reason is not None else None
                    elif current_event == "session_info":
                        # Agents that push session_info_update (e.g. opencode) surface the title
                        # live here; the gateway wraps the raw ACP update under `data`, so it is
                        # nested. codex-acp does NOT emit it -- that title comes from the admin
                        # session/list reconciliation after the turn (below).
                        title = str(((data.get("data") or {}).get("title")) or "").strip()
                        if title and not local_title:
                            self.repo.update_session_title(session_id, title, _now_iso())
                            self.connection.commit()
                            local_title = title
                            yield _sse("session_title_updated", {"title": title})
                current_event = None
                data_line = ""

        self._finalize(turn_id, parts, stop_reason, error_message)
        # codex-acp never emits session_info_update, so the live event above never fires for it;
        # its title is only exposed via the admin session/list (codex auto-derives it from the
        # first user message). Pull it once the turn has bound an acp_session_id, filling only an
        # empty local title so a manual rename is never clobbered. Best-effort: a missing/unhealthy
        # admin plane must never fail the turn.
        if (
            error_message is None
            and not local_title
            and bound_session_id
            and self.acp_admin is not None
        ):
            title = await self._fetch_acp_title(str(tenant_id), bound_session_id, cwd)
            if title:
                self.repo.update_session_title(session_id, title, _now_iso())
                self.connection.commit()
                local_title = title
                yield _sse("session_title_updated", {"title": title})
        if error_message is None:
            yield _sse("turn_completed", {"stopReason": stop_reason})

    async def _fetch_acp_title(
        self, tenant_id: str, acp_session_id: str, cwd: str
    ) -> str | None:
        """Look up a session's auto-derived title via the admin session/list.

        Keyed by the agent-assigned ACP session id (chat_sessions.acp_session_id), not the local
        thread id. Pages the cwd-filtered list until the id is found; bounded so an absent id can
        never loop forever. Returns None (never raises) if the admin plane is unhealthy.
        """
        cursor: str | None = None
        for _ in range(20):
            try:
                data = await self.acp_admin.list_sessions(cwd=cwd, cursor=cursor)
            except ApiError:
                return None
            for s in (data or {}).get("sessions") or []:
                if str(s.get("session_id") or "") == acp_session_id:
                    return str(s.get("title") or "").strip() or None
            cursor = (data or {}).get("next_cursor") or ""
            if not cursor:
                return None
        return None

    def _finalize(
        self,
        turn_id: str,
        parts: list[str],
        stop_reason: str | None,
        error_message: str | None,
    ) -> None:
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
        if self.backend == "acp":
            # The ACP data plane has no turn-cancel endpoint; cancellation is by client
            # disconnect. Best-effort: mark a still-running turn cancelled in the local record.
            self.repo.cancel_running_turn(turn_id, _now_iso())
            self.connection.commit()
            return {"turnId": turn_id, "status": "cancelled"}
        data = await self.ngent.request(
            "POST", f"/v1/turns/{turn_id}/cancel", tenant_id=principal.active_tenant_id
        )
        return {"turnId": turn_id, "status": (data or {}).get("status", "cancelling")}

    async def stream_turn_events(
        self, principal: Principal, turn_id: str, after: int | None
    ) -> AsyncIterator[str]:
        self._require_turn(principal, turn_id)
        if self.backend == "acp":
            # The ACP data plane has no event-replay endpoint; replay the stored turn from the
            # local record (no live mid-turn resume -- `after` is ignored).
            return self._replay_turn_acp(turn_id)
        tenant_id = principal.active_tenant_id
        path = f"/v1/turns/{turn_id}/events"
        if after is not None:
            path += f"?after={after}"

        ngent = self._require_ngent()

        async def events() -> AsyncIterator[str]:
            async for line in ngent.stream("GET", path, tenant_id=tenant_id):
                yield f"{line}\n"

        return events()

    def _replay_turn_acp(self, turn_id: str) -> AsyncIterator[str]:
        turn = self.repo.get_turn(turn_id)

        async def events() -> AsyncIterator[str]:
            if turn is None:
                return
            yield _sse("turn_started", {"turnId": turn.id})
            if turn.responseText:
                yield _sse("message_delta", {"delta": turn.responseText})
            if turn.status == "failed":
                yield _sse("error", {"message": turn.errorMessage or "error"})
            else:
                yield _sse("turn_completed", {"stopReason": turn.stopReason})

        return events()

    async def resolve_permission(
        self, principal: Principal, permission_id: str, body: ResolvePermissionRequest
    ) -> dict:
        if self.backend == "acp":
            # ACP requires a concrete outcome discriminator; the request id travels in the body.
            outcome = body.outcome or ("selected" if body.optionId else "cancelled")
            data = await self._require_acp().resolve_permission(
                request_id=permission_id,
                outcome=outcome,
                option_id=body.optionId,
                tenant_id=principal.active_tenant_id,
            )
            return data or {"permissionId": permission_id, "status": "resolved"}
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


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _acp_config_overrides(knowledge_base_ids: list[str]) -> dict[str, str] | None:
    if not knowledge_base_ids:
        return None
    # config_overrides is a string->string map on the wire, so the selection is JSON-encoded.
    # TODO(acp): confirm the exact key/encoding the ACP agent expects for knowledge-base selection.
    return {"knowledge_base_ids": json.dumps(knowledge_base_ids)}
