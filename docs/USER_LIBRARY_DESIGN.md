# User Library Design

> Status: design proposal.
> This document defines the backend design for the user personal library feature. It combines
> the frontend product requirements with the backend's existing control-plane style used by
> knowledge-base documents: database metadata is the source of truth, MinIO stores bytes, and
> access is authorized through backend APIs.

---

## 1. Goal

The user library lets signed-in users upload, view, search, preview, download, and delete their
own files.

Current scope:

- Personal library only.
- A user can only see files they uploaded.
- Files are isolated by `user_id`; `tenant_id` is also recorded so team libraries can be added
  later without reshaping storage paths.

Future scope:

- Personal library: `library_scope = 'user'`.
- Team library: `library_scope = 'tenant'`, shared within a tenant.

---

## 2. Principles

- The database owns file metadata, ownership, soft-delete state, and permission decisions.
- MinIO/S3 stores object bytes only.
- MinIO object paths are organization hints, not permission boundaries.
- Clients must never choose or submit object keys for download or preview.
- Every read, preview, download, update, and delete must first load the row by `file_id` and
  verify `user_id`, `tenant_id`, and `deleted_at is null`.
- The API should prefer short-lived presigned URLs for upload/download, matching the existing
  document subsystem.
- Deletion is soft delete first; object removal is handled by garbage collection.

---

## 3. Data Model

### 3.1 `library_files`

Stores completed files visible in the user's library.

```sql
create table if not exists library_files (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  tenant_id text not null references tenants(id) on delete cascade,
  original_name text not null,
  safe_name text not null,
  mime_type text,
  file_type text not null check (file_type in ('image', 'file')),
  extension text,
  size_bytes bigint not null,
  storage_bucket text not null,
  storage_object_key text not null unique,
  content_hash text,
  preview_supported boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);
```

Recommended indexes:

```sql
create index if not exists idx_library_files_user_tenant_updated
  on library_files (user_id, tenant_id, updated_at desc)
  where deleted_at is null;

create index if not exists idx_library_files_user_tenant_type
  on library_files (user_id, tenant_id, file_type, updated_at desc)
  where deleted_at is null;

create unique index if not exists idx_library_files_storage_object_key
  on library_files (storage_object_key);
```

Field notes:

- `user_id`: primary isolation boundary for the personal library.
- `tenant_id`: current tenant context, retained for future team library support.
- `file_type`: coarse frontend category, `image` or `file`.
- `mime_type`: detailed MIME type for icons, preview, and download headers.
- `preview_supported`: computed by backend from MIME type and extension.
- `deleted_at`: soft-delete marker. Do not add `status = deleted`; `deleted_at` is enough and
  avoids inconsistent state.

### 3.2 `library_upload_sessions`

Tracks a direct-upload handshake. This mirrors the existing knowledge-base document upload flow.

```sql
create table if not exists library_upload_sessions (
  id text primary key,
  file_id text not null,
  user_id text not null references users(id) on delete cascade,
  tenant_id text not null references tenants(id) on delete cascade,
  original_name text not null,
  safe_name text not null,
  mime_type text,
  file_type text not null check (file_type in ('image', 'file')),
  extension text,
  size_bytes bigint not null,
  storage_bucket text not null,
  storage_object_key text not null unique,
  upload_mode text not null default 'single_put'
    check (upload_mode in ('single_put', 'multipart')),
  status text not null default 'initiated'
    check (status in ('initiated', 'completed', 'aborted', 'expired', 'failed')),
  expires_at timestamptz not null,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

Recommended indexes:

```sql
create index if not exists idx_library_upload_sessions_status
  on library_upload_sessions (status, expires_at);

create index if not exists idx_library_upload_sessions_file
  on library_upload_sessions (file_id);
```

---

## 4. Object Storage

Use a single configured MinIO bucket and backend-generated object keys.

Object key format:

```text
library/{tenant_id}/users/{user_id}/{file_id}/{safe_name}
```

Example:

```text
library/tenant_default/users/user_123/file_abcd/report.pdf
```

Reasons:

- Keeps user files organized by tenant and user.
- Supports users who belong to multiple tenants.
- Leaves a natural path for future team files:

```text
library/{tenant_id}/team/{file_id}/{safe_name}
```

Security rule:

```text
file_id -> DB row -> verify user_id and tenant_id -> use storage_object_key -> presign or stream
```

Never allow:

```text
client object_key -> presign directly
```

---

## 5. API Design

Base path:

```text
/api/v1/library/files
```

All endpoints require:

```text
Authorization: Bearer <accessToken>
x-tenant-id: <tenant_id>
```

Recommended route dependency:

```text
require_tenant_permission("chat:ask")
```

Rationale: regular tenant members can use chat and personal library features. If a distinct
permission is needed later, add `library:read` / `library:write` to tenant roles.

### 5.1 List Files

```http
GET /api/v1/library/files
```

Query parameters:

```text
keyword: optional string
type: all | image | file, default all
page: integer >= 1, default 1
pageSize: integer, default 20
sort: updatedAt_desc | updatedAt_asc | name_asc | name_desc | size_desc | size_asc
```

Filtering rule:

```sql
where user_id = ?
  and tenant_id = ?
  and deleted_at is null
```

Add file type filter when `type != 'all'`:

```sql
and file_type = ?
```

Add keyword filter:

```sql
and lower(original_name) like ?
```

Response:

```json
{
  "items": [
    {
      "id": "file_xxx",
      "name": "example.pdf",
      "mimeType": "application/pdf",
      "type": "file",
      "sizeBytes": 102400,
      "sizeLabel": "100 KB",
      "updatedAt": "2026-06-16T10:00:00+08:00",
      "createdAt": "2026-06-16T10:00:00+08:00",
      "previewSupported": true
    }
  ],
  "total": 1,
  "page": 1,
  "pageSize": 20
}
```

### 5.2 Upload, Preferred Direct-Upload Flow

This matches the current backend style for knowledge-base documents.

#### Request Upload URL

```http
POST /api/v1/library/files/upload-url
```

Request:

```json
{
  "fileName": "example.pdf",
  "mimeType": "application/pdf",
  "fileSizeBytes": 102400,
  "contentHash": "sha256_optional"
}
```

Backend steps:

1. Read `user_id` from the token principal.
2. Read `tenant_id` from `x-tenant-id`.
3. Validate size, extension, and MIME type.
4. Generate `file_id` and `upload_session_id`.
5. Build `safe_name`.
6. Build `storage_object_key`.
7. Insert `library_upload_sessions`.
8. Return a short-lived presigned PUT URL.

Response:

```json
{
  "uploadSessionId": "upl_xxx",
  "fileId": "file_xxx",
  "method": "PUT",
  "uploadUrl": "https://minio.example.com/...",
  "headers": {
    "Content-Type": "application/pdf"
  },
  "objectKey": "library/tenant_default/users/user_123/file_xxx/example.pdf",
  "expiresAt": "2026-06-16T10:15:00+08:00"
}
```

#### Complete Upload

```http
POST /api/v1/library/files/complete-upload
```

Request:

```json
{
  "uploadSessionId": "upl_xxx"
}
```

Backend steps:

1. Load upload session by ID.
2. Verify `user_id` and `tenant_id`.
3. Verify session is `initiated` and not expired.
4. `HEAD` MinIO object.
5. Verify object size equals declared `size_bytes`.
6. Insert `library_files`.
7. Mark upload session `completed`.

Response: a file item.

### 5.3 Upload, Optional Multipart Shortcut

For small files and simpler frontend integration, the backend may also support:

```http
POST /api/v1/library/files
Content-Type: multipart/form-data
```

This endpoint should internally apply the same validation and metadata rules, then upload the
bytes to MinIO through the backend. It is easier for the frontend but less ideal for large files.

Recommended implementation order:

1. Implement direct upload first for consistency with existing document APIs.
2. Add multipart only if the product needs a simpler upload path.

### 5.4 Preview

```http
GET /api/v1/library/files/{file_id}/preview
```

Authorization:

```sql
where id = ?
  and user_id = ?
  and tenant_id = ?
  and deleted_at is null
```

Behavior:

- `image/*`: return a short-lived presigned GET URL or proxy image stream.
- `text/plain`, `text/markdown`, `application/json`, `text/csv`: return text content or a
  short-lived URL depending on frontend needs.
- `application/pdf`: return a preview URL.
- Office files such as `doc`, `docx`, `xls`, `xlsx`, `ppt`, `pptx`: initially
  `previewSupported = false` unless a conversion service is added.

Suggested response for URL-based preview:

```json
{
  "previewType": "url",
  "url": "https://minio.example.com/...",
  "expiresAt": "2026-06-16T10:15:00+08:00"
}
```

Suggested response for text preview:

```json
{
  "previewType": "text",
  "content": "# Notes\n...",
  "mimeType": "text/markdown"
}
```

### 5.5 Download

```http
GET /api/v1/library/files/{file_id}/download
```

Recommended response:

```json
{
  "downloadUrl": "https://minio.example.com/...",
  "expiresAt": "2026-06-16T10:15:00+08:00"
}
```

The backend must authorize by DB row first, then presign `storage_object_key`.

### 5.6 Delete

```http
DELETE /api/v1/library/files/{file_id}
```

Soft-delete only:

```sql
update library_files
set deleted_at = ?, updated_at = ?
where id = ?
  and user_id = ?
  and tenant_id = ?
  and deleted_at is null
```

Response:

```json
{
  "id": "file_xxx",
  "status": "deleted"
}
```

MinIO object cleanup should be handled by a GC task, not by relying on cascade.

---

## 6. Validation

File name:

- Strip path separators.
- Strip control characters.
- Reject empty names, `.`, and `..`.
- Store both `original_name` and `safe_name`.

File type:

- `file_type = 'image'` when MIME starts with `image/`.
- Otherwise `file_type = 'file'`.

MIME and extension:

- Apply an allowlist.
- Reject unknown executable or unsafe extensions.
- Do not trust MIME alone; cross-check extension and MIME where possible.

Size:

- Enforce a configured maximum upload size.
- For direct upload, verify actual object size by `stat` / `HEAD` during complete-upload.

---

## 7. Garbage Collection

Soft-deleted files remain in the database until objects are removed successfully.

GC flow:

1. Select rows from `library_files where deleted_at is not null`.
2. Remove `storage_object_key` from MinIO.
3. Hard-delete the DB row only after successful object removal.

Expired upload sessions:

1. Select `library_upload_sessions where status = 'initiated' and expires_at < now`.
2. Remove the object if present.
3. Mark the upload session `expired`.

This mirrors the existing document GC approach.

---

## 8. Layering

Follow existing backend conventions:

```text
app/domain/library.py
app/services/library_repository.py
app/services/library_service.py
app/api/v1/routers/library.py
infra/sql/0xx_library.sql
```

Repository:

- Raw SQL only.
- Use `?` placeholders.
- Use `json_param` / `json_load` for JSON fields.
- Reads must filter `deleted_at is null` unless explicitly doing GC.

Service:

- Orchestrates ownership checks, MinIO calls, and transaction commits.
- Generates IDs and object keys.
- Performs upload completion verification.

Router:

- Uses `Depends(get_database)`.
- Uses tenant principal / permission dependencies.
- Does not accept object keys from clients.

---

## 9. Comparison With Knowledge-Base Documents

Do not reuse the existing `documents` table.

Knowledge-base documents:

- Platform-authored.
- Belong to `knowledge_bases`.
- Have no `tenant_id`.
- Require platform `doc:*` permissions.

User library files:

- User-authored.
- Belong to `user_id` and current `tenant_id`.
- Require tenant-authenticated user access.
- Are not part of knowledge-base indexing by default.

---

## 10. Recommended Final Shape

Use the frontend product design with backend-style implementation:

- `library_files.user_id` is the personal library boundary.
- `library_files.tenant_id` is recorded for multi-tenant and future team-library support.
- `deleted_at` is the only delete marker.
- Object keys include both tenant and user:

```text
library/{tenant_id}/users/{user_id}/{file_id}/{safe_name}
```

- Upload should prefer presigned direct upload.
- Download and preview must load by `file_id`, verify ownership, then presign or stream.
- Lists must come from the database, never from MinIO `listObjects`.
