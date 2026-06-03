# Build API (Phase 2 placeholder)

Base path:

```text
/api/v1/knowledge-bases/{knowledge_base_id}
```

Build is decoupled from upload: uploading or changing documents does not trigger anything.
These endpoints reserve the route and contract but are **not implemented yet**. They create no
build records and write no snapshot. Build details (provider, snapshots, per-build tracking) are
intentionally deferred until the shape is settled; for now a knowledge base only exposes whether
it is usable via its `status`. The real worker/provider lands in a later phase (see
[Knowledge Base Storage and Build Design](../KNOWLEDGE_BASE_STORAGE_AND_BUILD_DESIGN.md)
sections 4.3 / 8 / 9).

Resource semantics are still honoured before the stub responds: the knowledge base must exist
(`404 KB_NOT_FOUND`) and, for build actions, must not be archived (`409 KB_ARCHIVED`). Only then
does the endpoint return `501 Not Implemented`:

```json
{
  "status": "not_implemented",
  "knowledgeBaseId": "kb_123",
  "message": "Build is not implemented yet; this endpoint is a placeholder."
}
```

## POST /build

Trigger a build. Required permission: `kb:build`.

Request (contract, ignored while stubbed):

```json
{ "force": false, "documentIds": [], "config": {} }
```

## GET /builds

List builds. Required permission: `kb:read`.

## GET /builds/{build_id}

Get a build. Required permission: `kb:read`.

## POST /builds/{build_id}/cancel

Cancel a build. Required permission: `kb:build`.
