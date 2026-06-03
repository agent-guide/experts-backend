# Documents API

Base path:

```text
/api/v1/documents
```

Documents are part of the platform-provided knowledge base capability. All APIs in this
group are **platform-scoped** and require a platform role:

```text
Authorization: Bearer <accessToken>
```

No `x-tenant-id` header is used. Implementation is delegated to PageIndex, and these
platform operations do not send an upstream `X-Tenant-Id`.

## GET /{document_id}

Get document status.

Required platform permission:

```text
kb:read
```

Response body is returned from PageIndex.

## GET /{document_id}/jobs

List document jobs.

Required platform permission:

```text
kb:read
```

Response body is returned from PageIndex.

## GET /{document_id}/chunks

List document chunks.

Required platform permission:

```text
kb:read
```

Response body is returned from PageIndex.

## DELETE /{document_id}

Delete a document.

Required platform permission:

```text
doc:delete
```

Response:

```text
204 No Content
```

## POST /{document_id}/reindex

Request document reindexing.

Required platform permission:

```text
doc:reindex
```

Response:

```text
202 Accepted
```

The response body is returned from PageIndex.
