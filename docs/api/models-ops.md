# Models and Ops API

## Models

Base path:

```text
/api/v1/models
```

All model APIs are tenant-scoped and require:

```text
Authorization: Bearer <accessToken>
x-tenant-id: <tenant_id>
```

### GET /llm

List available LLM models.

Current response:

```json
{
  "models": [
    {
      "id": "codex/gpt-5",
      "isDefault": true
    }
  ]
}
```

### GET /embedding

Get embedding or retrieval model metadata.

Current response:

```json
{
  "provider": "pageindex",
  "model": "pageindex-managed"
}
```

## Ops

Base path:

```text
/api/v1/ops
```

Ops APIs are platform-scoped.

### GET /metrics

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
system:ops
```

Current response:

```json
{
  "counters": {},
  "gauges": {},
  "derived": {
    "external": {
      "pageIndexConfigured": false,
      "acpConfigured": false
    }
  }
}
```

### POST /storage/gc

Run the object-storage garbage-collection passes. Intended to be called periodically (e.g. from
a cron job).

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
system:ops
```

Each pass is idempotent and best-effort by object key, so repeated runs are safe and a partial
failure is retried on the next call. Reclaims, in order: expired document upload-session objects,
soft-deleted document objects, soft-deleted knowledge-base objects, expired library upload-session
objects, and soft-deleted library file objects.

Current response (counts reclaimed by each pass):

```json
{
  "expiredSessions": 0,
  "purgedDocuments": 0,
  "purgedKnowledgeBases": 0,
  "expiredLibrarySessions": 0,
  "purgedLibraryFiles": 0
}
```
