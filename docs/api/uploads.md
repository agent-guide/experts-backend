# Uploads API

Base path:

```text
/api/v1/uploads
```

Uploads feed the platform-provided knowledge base capability. All APIs in this group are
**platform-scoped** and require a platform role:

```text
Authorization: Bearer <accessToken>
```

Required platform permission for all endpoints:

```text
doc:upload
```

No `x-tenant-id` header is used. Implementation is delegated to PageIndex, and these
platform operations do not send an upstream `X-Tenant-Id`.

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
