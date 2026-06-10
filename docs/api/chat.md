# Chat API

Base path:

```text
/api/v1/chat
```

All APIs in this group are tenant-scoped and require:

```text
Authorization: Bearer <accessToken>
x-tenant-id: <tenant_id>
```

Required tenant permission for all endpoints:

```text
chat:ask
```

Execution is delegated to ngent, but the **local database is the system of record**.
A **session** maps to an ngent thread and a **turn** maps to an ngent turn; both are
mirrored into `chat_sessions` / `chat_turns` so reads are tenant/user-scoped and survive
ngent (whose store is single-node, unbacked, and enforces no isolation). Every endpoint
authorizes by local ownership (the caller's tenant + user) before touching ngent. Session
and turn ids equal the ngent thread/turn ids.

Turn creation is **single-step streaming**: `POST /sessions/{session_id}/turns` returns
an SSE stream directly (the `turnId` arrives in the first `turn_started` event). There is
no separate "create then subscribe" step. Use `GET /turns/{turn_id}/events` only to
reconnect/replay an existing turn.

There are no `/chat/tasks` endpoints in the current backend. Clients should create or
select a session first, then post the user's message to `/sessions/{session_id}/turns`.

## POST /sessions

Create a chat session.

The session's working directory (the ngent thread `cwd`) is resolved per tenant: when
`EXPERT_NEXT_NGENT_CWD_BASE` is configured, it is `<base>/<tenant_id>` (created on demand);
otherwise the shared `EXPERT_NEXT_NGENT_DEFAULT_CWD` is used. The path must resolve under
ngent's `allowedRoots`.

Request:

```json
{
  "title": "Review analysis",
  "knowledgeBaseIds": ["kb_1"]
}
```

Response `201` (a session object):

```json
{
  "id": "thread_1",
  "title": "Review analysis",
  "knowledgeBaseIds": ["kb_1"],
  "isPinned": false,
  "createdAt": "2026-06-07T00:00:00+00:00",
  "updatedAt": "2026-06-07T00:00:00+00:00"
}
```

## GET /sessions

List chat sessions.

Response `200`:

```json
{
  "items": [
    {
      "id": "thread_1",
      "title": "Review analysis",
      "knowledgeBaseIds": ["kb_1"],
      "createdAt": "2026-06-03T00:00:00+00:00",
      "updatedAt": "2026-06-03T00:00:00+00:00",
      "isPinned": false
    }
  ]
}
```

## GET /sessions/{session_id}/messages

List the turns of a session (the conversational record), read from the local store.

Response:

```json
{
  "items": [
    {
      "id": "turn_1",
      "sessionId": "thread_1",
      "requestText": "Analyze recent review trends",
      "responseText": "...",
      "model": "codex/gpt-5",
      "status": "completed",
      "stopReason": "end_turn",
      "errorMessage": null,
      "createdAt": "2026-06-07T00:00:00+00:00",
      "completedAt": "2026-06-07T00:00:05+00:00"
    }
  ]
}
```

## GET /sessions/{session_id}

Get a single session.

Response is a session object.

## DELETE /sessions/{session_id}

Delete a session (proxies ngent `DELETE /v1/threads/{id}`).

Response `200`:

```json
{
  "id": "thread_1",
  "status": "deleted"
}
```

## PATCH /sessions/{session_id}/title

Rename a session.

Request:

```json
{
  "title": "New title"
}
```

Response is a session object.

## PATCH /sessions/{session_id}/pin

Pin or unpin a session.

Request:

```json
{
  "isPinned": true
}
```

Response is a session object:

```json
{
  "id": "thread_1",
  "title": "Review analysis",
  "knowledgeBaseIds": ["kb_1"],
  "isPinned": true,
  "createdAt": "2026-06-07T00:00:00+00:00",
  "updatedAt": "2026-06-07T00:00:05+00:00"
}
```

## POST /sessions/{session_id}/turns

Create a turn and stream its events. The session (thread) id is taken from the path.

Request:

```json
{
  "question": "Analyze recent review trends",
  "knowledgeBaseIds": ["kb_1"],
  "llmModel": "codex/gpt-5",
  "queryRewrite": true,
  "multiHop": {
    "enabled": true
  }
}
```

Response content type:

```text
text/event-stream
```

The response is the live SSE stream proxied from ngent
`POST /v1/threads/{id}/turns`. The first event is `turn_started`, carrying `turnId`,
followed by `message_delta` / tool / `turn_completed` events. A mid-turn
`permission_required` event must be answered via `POST /permissions/{permission_id}`.

The public backend request field is `question`. Internally, the backend adapts that field
to the current ngent turn protocol (`input` + `stream`) before proxying the request.

While proxying, the backend tees the stream and persists the assembled turn record
(`request_text`, `response_text`, `status`, `stop_reason`, ...) to `chat_turns`. If the
client disconnects before `turn_completed`, the local turn may remain `running` (ngent
finishes server-side); this is reconciled on the next read in a later iteration.

## POST /turns/{turn_id}/cancel

Cancel a running turn.

Response:

```json
{
  "turnId": "turn_1",
  "status": "cancelling"
}
```

## GET /turns/{turn_id}/events

Replay and live-stream a turn's events. Use this to reconnect to a turn created by
`POST /sessions/{session_id}/turns`.

Query parameters:

- `after` (optional, integer >= 0): resume from this event `seq`, skipping already-seen events.

Response content type:

```text
text/event-stream
```

The stream is proxied from ngent `GET /v1/turns/{id}/events`.

## POST /permissions/{permission_id}

Resolve a `permission_required` event raised mid-turn (e.g. a tool approval). Proxies
ngent `POST /v1/permissions/{permissionId}`.

Request (one of `outcome` / `optionId` is required):

```json
{
  "outcome": "approved",
  "optionId": "opt_1"
}
```

`outcome` is one of `approved`, `declined`, `cancelled`.
