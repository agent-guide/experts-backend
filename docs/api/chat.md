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

Execution is delegated to the agent-gateway ACP data plane, but the **local database is
the system of record**. Sessions and turns are mirrored into `chat_sessions` /
`chat_turns` so reads are tenant/user-scoped and survive agent restarts. Every endpoint
authorizes by local ownership (the caller's tenant + user) before touching ACP. Session
and turn ids are generated locally; `chat_sessions.acp_session_id` stores the
agent-assigned session id after the first turn so later turns resume the same instance.

Turn creation is **single-step streaming**: `POST /sessions/{session_id}/turns` returns
an SSE stream directly. The backend emits `turn_started` with a locally generated
`turnId` before forwarding translated ACP events. There is no separate "create then
subscribe" step. Use `GET /turns/{turn_id}/events` only to replay the stored local turn.

There are no `/chat/tasks` endpoints in the current backend. Clients should create or
select a session first, then post the user's message to `/sessions/{session_id}/turns`.

## POST /sessions

Create a chat session.

The ACP working directory is resolved per tenant: when `EXPERT_NEXT_ACP_CWD_BASE` is
configured, it is `<base>/<tenant_id>` (created on demand); otherwise the shared
`EXPERT_NEXT_ACP_DEFAULT_CWD` is used. The path must resolve under the ACP service's
`allowedRoots`.

Request:

```json
{
  "title": "Review analysis"
}
```

Response `201` (a session object):

```json
{
  "id": "thread_1",
  "title": "Review analysis",
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
      "reasoningText": "...",
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

Delete a session locally.

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
  "webSearchEnabled": true
}
```

`question` is required. `webSearchEnabled` is optional and only applies to the ACP
agent-gateway backend: `true` routes to the configured search ACP prefix with
`search_mode: "auto"`, while `false` or omitted routes to the default ACP prefix with
`search_mode: "off"`. Model / knowledge-base / retrieval options are not accepted here.

Response content type:

```text
text/event-stream
```

The response is the live SSE stream translated from ACP `POST {prefix}/turn`. The first
event is `turn_started`, carrying `turnId`, followed by `reasoning_delta` (model
thinking), `message_delta` (assistant answer), tool / usage / `turn_completed` events.
A mid-turn
`permission_required` event must be answered via `POST /permissions/{permission_id}`.
The backend owns this separation: process output (thinking, retrieval, tool progress)
is emitted only as `reasoning_delta` or structured tool/usage events, while
`message_delta` carries only the final user-facing answer. `message_delta.delta` is
normalized Markdown, so clients should render it as Markdown rather than infer headings
or list structure themselves. Both `reasoning_delta` and `message_delta` are emitted as
smoothed incremental deltas; clients should append each delta to the relevant buffer and
render progressively.
For `reasoning_delta`, `reasoningId` is stable for the turn and `mode` is `append`;
clients must update one reasoning block keyed by `reasoningId`, not create a new
reasoning item for each event.

The public backend request field is `question`. Internally, the backend sends it as ACP
turn `input`.

While streaming, the backend persists the assembled turn record (`request_text`,
`reasoning_text`, `response_text`, `status`, `stop_reason`, ...) to `chat_turns`. If the
client disconnects before `turn_completed`, the local turn may remain `running`; there is
no live ACP event-replay endpoint yet.

## POST /turns/{turn_id}/cancel

Cancel a running turn.

Response:

```json
{
  "turnId": "turn_1",
  "status": "cancelled"
}
```

## GET /turns/{turn_id}/events

Replay a stored turn's events. Use this to reconnect to a turn created by
`POST /sessions/{session_id}/turns`.

Query parameters:

- `after` (optional, integer >= 0): accepted for compatibility, currently ignored.

Response content type:

```text
text/event-stream
```

The stream is rebuilt from the stored local turn record.

## POST /permissions/{permission_id}

Resolve a `permission_required` event raised mid-turn (e.g. a tool approval). Proxies to
ACP `POST {prefix}/permission`.

Request (one of `outcome` / `optionId` is required):

```json
{
  "outcome": "approved",
  "optionId": "opt_1"
}
```

`outcome` is one of `approved`, `declined`, `cancelled`.
