from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.clients.acp_gateway import AcpGatewayClient
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
from app.services.chat_repository import ChatRepository


class ChatService:
    """Local DB is the system of record; ACP only drives compute.

    Sessions/turns are mirrored into chat_sessions/chat_turns so reads are tenant-scoped and
    survive the engine. The agent-gateway ACP data plane exposes only POST {prefix}/turn and
    POST {prefix}/permission. The thread id is generated locally at create time (no upstream
    call); a turn has no server id, so one is generated locally. The agent-assigned ACP session
    id arrives via the first turn's `session` event and is echoed back on later turns to resume
    the same instance. ACP events are translated to the public SSE contract
    (turn_started -> reasoning_delta -> message_delta -> turn_completed / error /
    permission_required) so callers do not change.
    """

    def __init__(
        self,
        connection: DatabaseConnection,
        *,
        acp: AcpGatewayClient | None = None,
    ) -> None:
        self.connection = connection
        self.acp = acp
        self.repo = ChatRepository(connection)

    def _require_acp(self) -> AcpGatewayClient:
        if self.acp is None:
            raise ApiError(503, "ACP_UNCONFIGURED", "acp gateway client is not configured")
        return self.acp

    # --- Sessions -------------------------------------------------------------

    async def create_session(self, principal: Principal, request: CreateSessionRequest) -> ChatSession:
        now = _now_iso()
        # The ACP data plane has no thread-create endpoint: the agent materializes a session
        # lazily on the first turn. Generate the caller-owned thread id locally.
        thread_id = f"thread_{uuid4().hex}"
        self.repo.create_session(
            session_id=thread_id,
            tenant_id=str(principal.active_tenant_id),
            user_id=principal.user_id,
            title=request.title,
            agent_options={},
            now=now,
        )
        self.connection.commit()
        return ChatSession(
            id=thread_id,
            title=request.title,
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
        self.repo.delete_session(session_id, _now_iso())
        self.connection.commit()

    async def list_messages(self, principal: Principal, session_id: str) -> list[dict]:
        self._require_session(principal, session_id)
        return [turn.model_dump() for turn in self.repo.list_turns(session_id)]

    async def get_transcript(self, principal: Principal, session_id: str) -> dict:
        """Replay a session's conversation history.

        The agent-side transcript (coalesced user/assistant/reasoning messages) is loaded from
        the gateway's route-scoped sessions API when a session has been materialized; otherwise
        it falls back to the durable local turn records. The shape is uniform:
        {sessionId, messages: [{role, text}], source: "agent" | "local"}.
        """
        row = self._require_session(principal, session_id)
        acp_session_id = str(row["acp_session_id"]) if row.get("acp_session_id") else None
        if acp_session_id and self.acp is not None:
            acp = self._require_acp()
            tenant_id = str(principal.active_tenant_id)
            cwd = acp.prepare_cwd(tenant_id)
            data = await acp.get_transcript(
                session_id=acp_session_id, tenant_id=tenant_id, cwd=cwd
            )
            messages = list((data or {}).get("messages") or [])
            return {"sessionId": session_id, "messages": messages, "source": "agent"}
        return {"sessionId": session_id, "messages": self._local_transcript(session_id), "source": "local"}

    def _local_transcript(self, session_id: str) -> list[dict]:
        messages: list[dict] = []
        for turn in self.repo.list_turns(session_id):
            messages.append({"role": "user", "text": turn.requestText})
            if turn.reasoningText:
                messages.append({"role": "reasoning", "text": turn.reasoningText})
            if turn.responseText:
                messages.append({"role": "assistant", "text": turn.responseText})
        return messages

    # --- Turns ----------------------------------------------------------------

    async def stream_turn(
        self, principal: Principal, session_id: str, request: ChatTurnRequest
    ) -> AsyncIterator[str]:
        async for line in self._stream_turn_acp(principal, session_id, request):
            yield line

    async def _stream_turn_acp(
        self, principal: Principal, session_id: str, request: ChatTurnRequest
    ) -> AsyncIterator[str]:
        row = self._require_session(principal, session_id)
        acp = self._require_acp()
        tenant_id = principal.active_tenant_id
        acp_session_id = str(row["acp_session_id"]) if row.get("acp_session_id") else None
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
            query_rewrite=False,
            multi_hop_config=None,
            now=_now_iso(),
        )
        self.connection.commit()
        yield _sse("turn_started", {"turnId": turn_id})

        try:
            result = _AcpTurnResult(bound_session_id=acp_session_id)
            attempt_events: list[str] | None = [] if acp_session_id else None

            drive = self._drive_acp_turn(
                acp=acp,
                principal=principal,
                session_id=session_id,
                request=request,
                initial_acp_session_id=acp_session_id,
                cwd=cwd,
                turn_id=turn_id,
                result=result,
            )
            # A resume attempt is buffered only until it shows a sign of life. Once any
            # output, reasoning, session rebind, permission prompt, or completion arrives,
            # the resume has "taken": flush what was held and stream the rest live so
            # follow-up turns are not stalled until the whole turn completes. A fresh
            # session (attempt_events is None) streams live from the first event.
            committed = attempt_events is None
            async for event in drive:
                if committed:
                    yield event
                    continue
                attempt_events.append(event)
                if (
                    result.saw_delta
                    or result.reasoning_parts
                    or result.saw_done
                    or result.bound_session_id != acp_session_id
                    or event.startswith("event: permission_required")
                ):
                    committed = True
                    for buffered in attempt_events:
                        yield buffered
                    attempt_events = None
        except ApiError as exc:
            self._finalize(turn_id, [], None, exc.message)
            yield _sse("error", {"code": exc.code, "message": exc.message, "details": exc.details})
            return

        # A buffered resume that produced nothing and errored means the upstream session
        # is gone. Drop the dead binding and retry once with a fresh session, streaming the
        # retry live since nothing was emitted to the caller yet.
        if (
            result.error_message is not None
            and acp_session_id is not None
            and not committed
            and result.bound_session_id == acp_session_id
        ):
            self.repo.set_acp_session_id(session_id, None, _now_iso())
            self.connection.commit()
            result = _AcpTurnResult()
            attempt_events = None
            async for event in self._drive_acp_turn(
                acp=acp,
                principal=principal,
                session_id=session_id,
                request=request,
                initial_acp_session_id=None,
                cwd=cwd,
                turn_id=turn_id,
                result=result,
                fresh_session=True,
            ):
                yield event

        if attempt_events is not None:
            for event in attempt_events:
                yield event

        answer = _normalize_answer_markdown("".join(result.parts))
        self._finalize(
            turn_id,
            [answer],
            result.stop_reason,
            result.error_message,
            reasoning_parts=result.reasoning_parts,
        )
        current_row = self.repo.get_session_row(
            str(principal.active_tenant_id), principal.user_id, session_id
        )
        local_title = str((current_row or {}).get("title") or "").strip()
        if result.error_message is None and not local_title and result.bound_session_id:
            title = await self._fetch_acp_title(str(tenant_id), result.bound_session_id, cwd)
            if title:
                self.repo.update_session_title(session_id, title, _now_iso())
                self.connection.commit()
                yield _sse("session_title_updated", {"title": title})
        if result.error_message is None:
            yield _sse("turn_completed", {"stopReason": result.stop_reason})

    async def _drive_acp_turn(
        self,
        *,
        acp: AcpGatewayClient,
        principal: Principal,
        session_id: str,
        request: ChatTurnRequest,
        initial_acp_session_id: str | None,
        cwd: str,
        turn_id: str,
        result: _AcpTurnResult,
        fresh_session: bool = False,
    ) -> AsyncIterator[str]:
        reasoning_buffer = _SmoothTextBuffer(max_chars=48, punctuation=True)
        answer_buffer = _SmoothTextBuffer(max_chars=80, punctuation=True)
        current_event: str | None = None
        data_line = ""
        result.bound_session_id = initial_acp_session_id
        # Auto session title: the gateway replays the agent's title as a `session_info` event at
        # turn start. Persist it only while the local title is still empty so a user's manual
        # rename is never clobbered.
        row = self.repo.get_session_row(
            str(principal.active_tenant_id), principal.user_id, session_id
        )
        local_title = str((row or {}).get("title") or "").strip()

        def emit_reasoning(text: str) -> list[str]:
            result.reasoning_parts.append(text)
            chunk = reasoning_buffer.push(text)
            if chunk:
                return [_sse("reasoning_delta", _reasoning_delta_payload(chunk, turn_id))]
            return []

        def emit_answer(text: str) -> list[str]:
            result.parts.append(text)
            result.saw_delta = True
            events: list[str] = []
            reasoning_tail = reasoning_buffer.flush()
            if reasoning_tail:
                events.append(_sse("reasoning_delta", _reasoning_delta_payload(reasoning_tail, turn_id)))
            chunk = answer_buffer.push(text)
            if chunk:
                events.append(_sse("message_delta", {"delta": _normalize_answer_markdown_delta(chunk, at_line_start=answer_buffer.chunk_at_line_start)}))
            return events

        def flush_reasoning_tail() -> list[str]:
            reasoning_tail = reasoning_buffer.flush()
            if reasoning_tail:
                return [_sse("reasoning_delta", _reasoning_delta_payload(reasoning_tail, turn_id))]
            return []

        def flush_answer_tail() -> list[str]:
            answer_tail = answer_buffer.flush()
            if answer_tail:
                return [_sse("message_delta", {"delta": _normalize_answer_markdown_delta(answer_tail, at_line_start=answer_buffer.chunk_at_line_start)})]
            return []

        async for line in acp.stream_turn(
            thread_id=session_id,
            input=request.question,
            tenant_id=principal.active_tenant_id,
            session_id=initial_acp_session_id,
            cwd=cwd,
            fresh_session=fresh_session,
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
                        if sid and sid != result.bound_session_id:
                            # Persist the agent-assigned id so follow-up turns resume this instance.
                            result.bound_session_id = sid
                            self.repo.set_acp_session_id(session_id, sid, _now_iso())
                            self.connection.commit()
                    elif current_event == "delta":
                        text = data.get("text")
                        if text:
                            for event in emit_answer(str(text)):
                                yield event
                    elif current_event in _ACP_REASONING_EVENTS:
                        reasoning_text = _acp_reasoning_text(current_event, data)
                        if reasoning_text:
                            for event in emit_reasoning(reasoning_text):
                                yield event
                    elif current_event == "permission":
                        # Translate ACP permission prompts to the public permission_required shape.
                        payload: dict = {"permissionId": data.get("request_id")}
                        if data.get("data") is not None:
                            payload["data"] = data["data"]
                        yield _sse("permission_required", payload)
                    elif current_event == "error":
                        result.error_message = str(data.get("message") or "") or "error"
                        yield _sse("error", {"message": result.error_message})
                    elif current_event == "done":
                        result.saw_done = True
                        reason = data.get("stop_reason")
                        result.stop_reason = str(reason) if reason is not None else None
                        for event in flush_reasoning_tail():
                            yield event
                        for event in flush_answer_tail():
                            yield event
                    elif current_event == "session_info":
                        # Agents that push session_info_update (e.g. opencode) surface the title
                        # live here; the gateway wraps the raw ACP update under `data`, so it is
                        # nested. codex-acp does NOT emit it -- that title comes from the
                        # route-scoped session/list reconciliation after the turn (below).
                        title = str(((data.get("data") or {}).get("title")) or "").strip()
                        if title and not local_title:
                            self.repo.update_session_title(session_id, title, _now_iso())
                            self.connection.commit()
                            local_title = title
                            yield _sse("session_title_updated", {"title": title})
                current_event = None
                data_line = ""

        for event in flush_reasoning_tail():
            yield event
        for event in flush_answer_tail():
            yield event

    async def _fetch_acp_title(
        self, tenant_id: str, acp_session_id: str, cwd: str
    ) -> str | None:
        """Look up a session's auto-derived title via the route-scoped session list.

        Keyed by the agent-assigned ACP session id (chat_sessions.acp_session_id), not the local
        thread id. Pages the cwd-filtered list until the id is found; bounded so an absent id can
        never loop forever. Returns None (never raises) if the gateway is unhealthy.
        """
        acp = self._require_acp()
        cursor: str | None = None
        for _ in range(20):
            try:
                data = await acp.list_sessions(tenant_id=tenant_id, cwd=cwd, cursor=cursor)
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
        *,
        reasoning_parts: list[str] | None = None,
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
            reasoning_text="".join(reasoning_parts or []),
            stop_reason=stop_reason,
            error_message=error_message,
            completed_at=_now_iso(),
        )
        self.connection.commit()

    async def cancel_turn(self, principal: Principal, turn_id: str) -> dict:
        self._require_turn(principal, turn_id)
        # The ACP data plane has no turn-cancel endpoint; cancellation is by client
        # disconnect. Best-effort: mark a still-running turn cancelled in the local record.
        self.repo.cancel_running_turn(turn_id, _now_iso())
        self.connection.commit()
        return {"turnId": turn_id, "status": "cancelled"}

    async def stream_turn_events(
        self, principal: Principal, turn_id: str, after: int | None
    ) -> AsyncIterator[str]:
        self._require_turn(principal, turn_id)
        # The ACP data plane has no event-replay endpoint; replay the stored turn from the
        # local record (no live mid-turn resume -- `after` is ignored).
        return self._replay_turn_acp(turn_id)

    def _replay_turn_acp(self, turn_id: str) -> AsyncIterator[str]:
        turn = self.repo.get_turn(turn_id)

        async def events() -> AsyncIterator[str]:
            if turn is None:
                return
            yield _sse("turn_started", {"turnId": turn.id})
            if turn.reasoningText:
                yield _sse("reasoning_delta", _reasoning_delta_payload(turn.reasoningText, turn.id))
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
        # ACP requires a concrete outcome discriminator; the request id travels in the body.
        outcome = body.outcome or ("selected" if body.optionId else "cancelled")
        data = await self._require_acp().resolve_permission(
            request_id=permission_id,
            outcome=outcome,
            option_id=body.optionId,
            tenant_id=principal.active_tenant_id,
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


def _reasoning_delta_payload(delta: str, turn_id: str | None) -> dict:
    payload = {
        "delta": delta,
        "channel": "reasoning",
        "mode": "append",
        "reasoningId": f"{turn_id or 'pending'}:reasoning",
    }
    if turn_id:
        payload["turnId"] = turn_id
    return payload


def _normalize_answer_markdown(text: str) -> str:
    """Apply deterministic Markdown cleanup to final assistant answers."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    normalized_lines: list[str] = []
    blank_seen = False
    for raw_line in text.split("\n"):
        line = _normalize_markdown_line(raw_line.rstrip())
        if not line.strip():
            if blank_seen:
                continue
            blank_seen = True
            normalized_lines.append("")
            continue
        blank_seen = False
        normalized_lines.append(line)
    return "\n".join(normalized_lines).strip()


def _normalize_answer_markdown_delta(text: str, *, at_line_start: bool = True) -> str:
    """Normalize Markdown markers without changing streaming whitespace.

    The line-start markers (headings, list bullets) are anchored at the start of a line, so
    they may only be applied to the first line of a streamed chunk when that chunk actually
    begins at a line boundary. Otherwise a mid-line fragment like "#5" would be mangled into
    "# 5". Lines after an embedded newline are always genuine line starts.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    normalized = [
        line if index == 0 and not at_line_start else _normalize_markdown_line(line)
        for index, line in enumerate(lines)
    ]
    return "\n".join(normalized)


def _normalize_markdown_line(line: str) -> str:
    line = re.sub(r"^(#{1,6})(\S)", r"\1 \2", line)
    line = re.sub(r"^(\s*)[\u2022\u25cf]\s+", r"\1- ", line)
    line = re.sub(r"^(\s*)[-*+]\s+", r"\1- ", line)
    line = re.sub(r"^(\s*)(\d+)[)\uff09\u3001]\s*", r"\1\2. ", line)
    return line


class _SmoothTextBuffer:
    def __init__(self, *, max_chars: int, punctuation: bool = False) -> None:
        self.max_chars = max_chars
        self.punctuation = punctuation
        self._text = ""
        # Whether the chunk most recently returned by push()/flush() began at a line start.
        # The very first chunk does; afterwards a chunk is a line start only when the previous
        # one ended on a newline.
        self.chunk_at_line_start = True
        self._next_at_line_start = True

    def push(self, delta: str) -> str | None:
        self._text += delta
        split_at = self._split_index()
        if split_at is None:
            return None
        chunk = self._text[:split_at]
        self._text = self._text[split_at:]
        self._mark(chunk)
        return chunk

    def flush(self) -> str:
        chunk = self._text
        self._text = ""
        self._mark(chunk)
        return chunk

    def _mark(self, chunk: str) -> None:
        self.chunk_at_line_start = self._next_at_line_start
        if chunk:
            self._next_at_line_start = chunk.endswith("\n")

    def _split_index(self) -> int | None:
        if not self._text:
            return None
        newline = self._text.rfind("\n")
        if newline >= 0:
            return newline + 1
        if self.punctuation:
            for index in range(len(self._text) - 1, -1, -1):
                if _is_soft_flush_char(self._text[index]) and index + 1 >= 12:
                    return index + 1
        if len(self._text) >= self.max_chars:
            return len(self._text)
        return None


def _is_soft_flush_char(char: str) -> bool:
    return char in {
        " ",
        ".",
        "!",
        "?",
        ";",
        ":",
        "\u3002",
        "\uff01",
        "\uff1f",
        "\uff1b",
        "\uff1a",
        "\uff0c",
        "\u3001",
    }


_ACP_REASONING_EVENTS = frozenset({"reasoning", "tool_call", "usage"})


def _acp_reasoning_text(event: str, data: dict) -> str | None:
    """Map ACP process events to the public reasoning channel."""
    text = data.get("text")
    if text is not None and str(text):
        return str(text)
    if event == "tool_call":
        payload = data.get("data")
        if not isinstance(payload, dict):
            if payload is not None:
                return f"[tool] {json.dumps(payload, ensure_ascii=False)}\n"
            return None
        name = str(payload.get("name") or payload.get("tool") or "tool")
        detail = payload.get("input") or payload.get("arguments")
        if detail is not None:
            if isinstance(detail, (dict, list)):
                detail_text = json.dumps(detail, ensure_ascii=False)
            else:
                detail_text = str(detail)
            return f"[tool] {name}: {detail_text}\n"
        return f"[tool] {name}\n"
    if event == "usage":
        return None
    nested = data.get("data")
    if nested is None:
        return None
    if isinstance(nested, str):
        return nested
    return json.dumps(nested, ensure_ascii=False) + "\n"


@dataclass
class _AcpTurnResult:
    parts: list[str] | None = None
    reasoning_parts: list[str] | None = None
    stop_reason: str | None = None
    error_message: str | None = None
    bound_session_id: str | None = None
    saw_delta: bool = False
    saw_done: bool = False

    def __post_init__(self) -> None:
        if self.parts is None:
            self.parts = []
        if self.reasoning_parts is None:
            self.reasoning_parts = []
