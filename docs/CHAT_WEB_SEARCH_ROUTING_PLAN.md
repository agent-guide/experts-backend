# Chat Web Search Routing Plan

## Purpose

This document defines the first-version backend plan for per-turn web search in chat when
the compute backend is the local Agent Gateway ACP data plane.

The backend exposes a single product chat session to the frontend, but it may route each
turn to one of two Agent Gateway ACP routes depending on the frontend's
`webSearchEnabled` flag.

## Request Contract

The public backend turn endpoint remains:

```http
POST /api/v1/chat/sessions/{session_id}/turns
Content-Type: application/json
Accept: text/event-stream
```

Request body:

```json
{
  "question": "User question",
  "webSearchEnabled": true
}
```

Field semantics:

- `question` is required.
- `webSearchEnabled: true` requests web-search-capable execution for this turn.
- `webSearchEnabled: false` requests no-web-search execution for this turn.
- Missing `webSearchEnabled` is treated the same as `false` for route selection.

## Agent Gateway Routes

The first version uses two explicit ACP routes:

| Backend input | ACP route | Search mode |
| --- | --- | --- |
| `webSearchEnabled === true` | `/acp/codex-qa-search/turn` | `auto` |
| `webSearchEnabled === false` | `/acp/codex-qa/turn` | `off` |
| Missing `webSearchEnabled` | `/acp/codex-qa/turn` | `off` |

Backend configuration:

- `EXPERT_NEXT_ACP_ROUTE_PREFIX` configures the no-search route prefix, for example
  `/acp/codex-qa`.
- `EXPERT_NEXT_ACP_SEARCH_ROUTE_PREFIX` configures the search route prefix, for example
  `/acp/codex-qa-search`.
- If the search prefix is not configured, search turns fall back to the default ACP prefix
  while still sending `search_mode: "auto"`.

Search route request:

```http
POST {gateway}/acp/codex-qa-search/turn
Authorization: Bearer <virtual-key>
Content-Type: application/json
Accept: text/event-stream
```

```json
{
  "thread_id": "local-chat-session-id",
  "input": "User question",
  "search_mode": "auto"
}
```

No-search route request:

```http
POST {gateway}/acp/codex-qa/turn
Authorization: Bearer <virtual-key>
Content-Type: application/json
Accept: text/event-stream
```

```json
{
  "thread_id": "local-chat-session-id",
  "input": "User question",
  "search_mode": "off"
}
```

## Session Model

The local backend database remains the source of truth for product chat sessions and
turns. A single `chat_sessions.id` represents the user-visible conversation.

Agent Gateway sessions are route-scoped. The search route and no-search route are backed
by different ACP services, so their `session_id` values must not be reused across routes.

The backend should track route-specific ACP session ids:

```text
sessionByMode.noSearch
sessionByMode.search
```

Implementation uses a dedicated `acp_search_session_id` column while keeping the existing
`acp_session_id` for no-search turns. Two explicit columns are simpler and easier to query
for the first version.

## Turn Routing

For each user turn:

1. Read `webSearchEnabled` from the request.
2. Select the target route and mode:
   - `true` -> search route, `search_mode: "auto"`.
   - `false` or missing -> no-search route, `search_mode: "off"`.
3. Use only the ACP session id associated with that route.
4. Stream the ACP SSE response back to the frontend.
5. When a `session` event returns a `session_id`, persist it into the matching route-specific
   ACP session field.
6. Persist the assembled local turn as usual in `chat_turns`.

Never send the search route's `session_id` to the no-search route, or the no-search
route's `session_id` to the search route.

## Context Continuity

Switching `webSearchEnabled` inside one product chat session means the backend may switch
between two independent ACP sessions. Those upstream sessions do not share memory.

The user-visible conversation should still remain continuous because local chat history is
authoritative. The first-version behavior can be:

- Keep all turns in the same local `chat_sessions` and `chat_turns` records.
- Use separate ACP session ids per route.
- On mode switch, optionally prepend a compact local history summary or recent turns to
  the next `input`.

Recommended first-version product behavior:

- Allow per-turn switching.
- Do not cross-reuse ACP session ids.
- Preserve local history for display and replay.
- Add history injection only if user testing shows mode switches lose important context.

## SSE Handling

The backend must continue to consume Agent Gateway ACP SSE frames:

- `session`: captures the route-scoped `session_id`.
- `delta`: appends assistant answer text.
- `done`: marks the turn complete.
- `error`: reports gateway/runtime errors.
- `reasoning`, `tool_call`, and `permission` should continue to be translated to the
  public backend stream contract where applicable.

## Future Option

A later gateway version may expose a single prefix that internally routes by
`search_mode`:

```http
POST /acp/codex-qa/turn
```

```json
{
  "thread_id": "local-chat-session-id",
  "input": "User question",
  "search_mode": "auto"
}
```

If that becomes available, the backend can simplify route selection while still preserving
the route-specific session isolation rule if gateway services remain separate internally.
