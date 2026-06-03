# Knowledge Bases API

Base path:

```text
/api/v1/knowledge-bases
```

Knowledge bases are **platform-provided capabilities**: they are authored and managed
by platform users, not by tenants. All endpoints in this group require platform
permissions and a platform role:

```text
Authorization: Bearer <accessToken>
```

No `x-tenant-id` header is used. Implementation is delegated to PageIndex, and these
platform operations intentionally do not send an upstream `X-Tenant-Id`. Tenants do not
own or author knowledge bases; they consume them through product workflows (chat).
Which tenants/users may use a knowledge base is governed by the entitlement mechanism
(deferred — see `docs/RBAC_CAPABILITY_OWNERSHIP_TODO.md`).

## POST /

Create a knowledge base.

Required platform permission:

```text
kb:create
```

Request:

```json
{
  "name": "Amazon Reviews",
  "description": "Review analysis corpus",
  "visibility": "private",
  "defaultChunkStrategy": null,
  "defaultChunkConfig": {}
}
```

Allowed `visibility` values:

- `private`
- `tenant_public`
- `official_public`

Response:

```text
201 Created
```

The response body is returned from PageIndex.

## POST /official

Create an official platform knowledge base.

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
platform:kb_publish_official
```

Request:

```json
{
  "name": "Official Amazon KB",
  "description": "Platform-managed knowledge base",
  "visibility": "private",
  "defaultChunkStrategy": null,
  "defaultChunkConfig": {}
}
```

The service overrides `visibility` to `official_public` before forwarding to
PageIndex. No `X-Tenant-Id` is sent upstream for this platform operation.

Response:

```text
201 Created
```

The response body is returned from PageIndex.

## GET /

List knowledge bases.

Required platform permission:

```text
kb:read
```

Response body is returned from PageIndex.

## GET /{knowledge_base_id}

Get a knowledge base.

Required platform permission:

```text
kb:read
```

Response body is returned from PageIndex.

## PATCH /{knowledge_base_id}

Update a knowledge base.

Required platform permission:

```text
kb:update
```

Request:

```json
{
  "name": "Updated Name",
  "description": "Updated description",
  "visibility": "tenant_public",
  "defaultChunkStrategy": null,
  "defaultChunkConfig": {}
}
```

All fields are optional.

Response body is returned from PageIndex.

## DELETE /{knowledge_base_id}

Delete a knowledge base.

Required platform permission:

```text
kb:delete
```

Response:

```text
204 No Content
```

## POST /{knowledge_base_id}/documents

Compatibility placeholder for document upload through a knowledge base path.

Response `202`:

```json
{
  "message": "Use /api/v1/uploads/* direct-upload APIs until multipart PageIndex mapping is finalized"
}
```

## GET /{knowledge_base_id}/documents

List documents in a knowledge base.

Required platform permission:

```text
kb:read
```

Response body is returned from PageIndex.
