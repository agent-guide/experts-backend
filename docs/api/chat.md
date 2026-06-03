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

Execution is delegated to ngent.
Expert Next API forwards the active tenant to ngent as `X-Tenant-Id`; ngent must
scope session/task operations to that tenant.

## POST /sessions

Create a chat session.

Request:

```json
{
  "title": "Review analysis",
  "knowledgeBaseIds": ["kb_1"]
}
```

Response `201`:

```json
{
  "id": "thread_1",
  "title": "Review analysis",
  "knowledgeBaseIds": ["kb_1"]
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

List messages or turns for a session.

Response:

```json
{
  "items": []
}
```

Items are adapted from ngent thread history.

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

Current response:

```json
{
  "id": "session_1",
  "isPinned": true
}
```

## POST /tasks

Create a chat task.

Request:

```json
{
  "sessionId": "thread_1",
  "question": "Analyze recent review trends",
  "knowledgeBaseIds": ["kb_1"],
  "llmModel": "codex/gpt-5",
  "queryRewrite": true,
  "multiHop": {
    "enabled": true
  }
}
```

Response `202`:

```json
{
  "taskId": "turn_1",
  "status": "queued",
  "queuePosition": null
}
```

## POST /tasks/{task_id}/cancel

Cancel a chat task.

Response:

```json
{
  "taskId": "turn_1",
  "status": "cancel_requested"
}
```

## GET /tasks/{task_id}/position

Get queue position.

Current response:

```json
{
  "taskId": "turn_1",
  "position": null,
  "queueDepth": null
}
```

## GET /tasks/{task_id}/events

Stream task events.

Response content type:

```text
text/event-stream
```

The stream is proxied from ngent turn events.
