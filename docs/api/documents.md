# Documents API

Base path:

```text
/api/v1/documents
```

All APIs in this group are tenant-scoped and require:

```text
Authorization: Bearer <accessToken>
x-tenant-id: <tenant_id>
```

Implementation is delegated to PageIndex.
Expert Next API forwards the active tenant to PageIndex as `X-Tenant-Id`;
PageIndex must scope document-id operations to that tenant.

## GET /{document_id}

Get document status.

Required tenant permission:

```text
kb:read
```

Response body is returned from PageIndex.

## GET /{document_id}/jobs

List document jobs.

Required tenant permission:

```text
kb:read
```

Response body is returned from PageIndex.

## GET /{document_id}/chunks

List document chunks.

Required tenant permission:

```text
kb:read
```

Response body is returned from PageIndex.

## DELETE /{document_id}

Delete a document.

Required tenant permission:

```text
doc:delete
```

Response:

```text
204 No Content
```

## POST /{document_id}/reindex

Request document reindexing.

Required tenant permission:

```text
doc:reindex
```

Response:

```text
202 Accepted
```

The response body is returned from PageIndex.
