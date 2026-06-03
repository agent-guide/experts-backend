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
      "ngentConfigured": false
    }
  }
}
```
