# Knowledge Bases API

Base path:

```text
/api/v1/knowledge-bases
```

Tenant knowledge base APIs require:

```text
Authorization: Bearer <accessToken>
x-tenant-id: <tenant_id>
```

Implementation is delegated to PageIndex.
For tenant endpoints, Expert Next API forwards the active tenant to PageIndex as
`X-Tenant-Id`; PageIndex must scope resource-id operations to that tenant.
Official platform endpoints intentionally omit this upstream tenant header.

## POST /

Create a knowledge base.

Required tenant permission:

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

Required tenant permission:

```text
kb:read
```

Response body is returned from PageIndex.

## GET /{knowledge_base_id}

Get a knowledge base.

Required tenant permission:

```text
kb:read
```

Response body is returned from PageIndex.

## PATCH /{knowledge_base_id}

Update a knowledge base.

Required tenant permission:

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

Required tenant permission:

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

Required tenant permission:

```text
kb:read
```

Response body is returned from PageIndex.
