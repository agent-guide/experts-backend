# Uploads API

Base path:

```text
/api/v1/uploads
```

All APIs in this group are tenant-scoped and require:

```text
Authorization: Bearer <accessToken>
x-tenant-id: <tenant_id>
```

Required tenant permission for all endpoints:

```text
doc:upload
```

Implementation is delegated to PageIndex.
Expert Next API forwards the active tenant to PageIndex as `X-Tenant-Id`;
PageIndex must scope upload/session operations to that tenant.

## POST /initiate

Initiate a direct upload.

Request:

```json
{
  "knowledgeBaseId": "kb_1",
  "fileName": "reviews.csv",
  "fileSizeBytes": 12345,
  "contentType": "text/csv"
}
```

Response body is returned from PageIndex.

## POST /complete

Complete a direct upload.

Request:

```json
{
  "uploadSessionId": "upload_1",
  "etag": "etag-value",
  "fileSizeBytes": 12345
}
```

Response:

```text
202 Accepted
```

The response body is returned from PageIndex.

## POST /multipart/initiate

Initiate a multipart upload.

Request is the same as `POST /initiate`.

Response body is returned from PageIndex.

## POST /multipart/parts

Request multipart upload part URLs or metadata.

Request:

```json
{
  "uploadSessionId": "upload_1",
  "partNumbers": [1, 2, 3]
}
```

Response body is returned from PageIndex.

## POST /multipart/complete

Complete a multipart upload.

Request:

```json
{
  "uploadSessionId": "upload_1",
  "parts": [
    {
      "partNumber": 1,
      "etag": "etag-1"
    }
  ],
  "etag": "final-etag",
  "fileSizeBytes": 12345
}
```

Response:

```text
202 Accepted
```

The response body is returned from PageIndex.

## POST /multipart/abort

Abort a multipart upload.

Request:

```json
{
  "uploadSessionId": "upload_1"
}
```

Response:

```text
204 No Content
```
