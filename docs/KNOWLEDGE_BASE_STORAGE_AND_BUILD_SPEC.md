# Knowledge Base Storage & Build — Architecture & Technical Specification

> Status: **implemented** (Phase 1 + Phase 2).
> This document is the English architecture design and technical specification for the
> knowledge base storage and build subsystem as it exists in the codebase. The original
> design rationale (in Chinese) is retained in
> [`KNOWLEDGE_BASE_STORAGE_AND_BUILD_DESIGN.md`](./KNOWLEDGE_BASE_STORAGE_AND_BUILD_DESIGN.md).
> Where this spec and the design doc disagree, **this spec reflects the shipped code**.

---

## 1. Overview

Knowledge bases, documents, and uploads are managed by this service's own PostgreSQL
database, with original document bytes stored in the configured object storage backend
(`local` by default, `minio` for production). The API service authorizes requests,
mints object keys, signs short-lived upload/download URLs, verifies uploaded objects,
and persists metadata. In `minio` mode, clients upload and download directly against
MinIO/S3 using presigned URLs. In `local` mode, clients use signed backend storage
routes; uploads are streamed to disk with size enforcement.

Key properties of the shipped design:

- The local database is the single source of truth for knowledge base / document /
  upload-session metadata. There is no PageIndex pass-through.
- Documents are uploaded through the configured object storage backend. MinIO mode
  uses direct presigned object-store URLs; local mode uses signed backend storage URLs.
- Knowledge bases, documents, and upload sessions carry **no `tenant_id`** — they are
  platform-owned resources. Tenants only consume knowledge bases indirectly via chat.
- Access is decided **entirely by platform permission bits on the route**. There is no
  `scope` / `visibility` / owner-based resource check; `owner_user_id` is creator
  attribution only.
- **Build is deferred.** Build endpoints exist as a fixed `501` placeholder contract; they
  create no records and mutate no state. Real worker/provider implementation is a later phase.

### 1.1 Scope

| Phase | Area | Status |
| --- | --- | --- |
| 1 | DB schema, KB CRUD, docs CRUD, object storage upload, soft delete, GC | **Implemented** |
| 2 | Build endpoints as `501` placeholders | **Implemented** |
| 3 | `knowledge_base_builds` table, build worker, provider abstraction | Deferred (§11) |
| 4 | Chat/search retrieval integration | Deferred (§11) |

---

## 2. Architecture

```text
Client / Web Console
        |
        | 1. request presigned upload URL  (control plane)
        v
   Expert API  ────────────────────────────────────────────┐
        | router → service → repository → DB                │
        |                                                   │
        +-- PostgreSQL (metadata, source of truth)          │
        |      +-- knowledge_bases                           │
        |      +-- documents                                 │
        |      +-- upload_sessions                           │
        |                                                   │
        +-- ObjectStore (control-plane view of MinIO)       │
               +-- presigned PUT / GET                       │
               +-- HEAD (stat) / remove                      │
                                                             │
Client  ── 2. PUT bytes directly ──►  MinIO / S3  ◄──────────┘  3. HEAD verify on complete
```

The API service responsibilities:

- Authorize the caller (platform principal + action permission) and the resource
  (knowledge base lifecycle).
- Generate the object key (clients never choose it).
- Sign short-lived presigned PUT/GET URLs.
- Verify upload completion via HEAD (object existence + size).
- Persist metadata and manage upload-session state.

The configured object store is the **storage plane** for original bytes. Clients receive
only object-scoped, short-TTL upload/download URLs. MinIO is recommended for production;
local storage is the default development backend.

### 2.1 Layering

The subsystem follows the project's standard four-layer pattern (mirroring `skills`):

```text
app/domain/knowledge.py            Pydantic request/response models (camelCase wire shape)
app/services/*_repository.py       Raw SQL; "?" placeholders, rewritten to "%s" for Postgres
app/services/*_service.py          Orchestration: repo + object store + commit
app/api/v1/routers/*.py            FastAPI routes; Depends(get_database) + permission guards
```

Relevant modules:

| Module | Responsibility |
| --- | --- |
| `app/domain/knowledge.py` | Wire models + status `Literal` types |
| `app/services/knowledge_base_repository.py` | KB CRUD SQL |
| `app/services/knowledge_base_service.py` | KB orchestration + authz |
| `app/services/document_repository.py` | `documents` + `upload_sessions` SQL |
| `app/services/document_service.py` | Upload flow, CRUD, GC, object-key/file-name logic |
| `app/services/object_store.py` | `ObjectStore` abstraction + `MinioObjectStore` |
| `app/services/kb_authz.py` | `authorize_kb_access` lifecycle gate |
| `app/api/v1/routers/knowledge_bases.py` | KB routes |
| `app/api/v1/routers/documents.py` | Docs routes (nested under KB) |
| `app/api/v1/routers/builds.py` | Build placeholder routes |
| `app/api/deps.py` | `get_object_store`, `require_platform_permission` |

---

## 3. Data Model

> **Migration model (important).** `app/db.py` re-runs **every** `infra/sql/*.sql` file on
> each boot and has **no applied-migrations table**; idempotency relies on
> `create table if not exists`. There is **no migration history** — each file holds the
> canonical (final) shape of its tables, with every column/index/constraint folded into the
> `create table`. The **canonical schema lives in `002_knowledge_bases.sql` and
> `003_documents.sql`** (documents, upload_sessions). Files are numbered only to order FK
> dependencies (`sorted(glob)`). Evolve a table by editing its `create table` in place; add an
> idempotent `alter ... if [not] exists` only when an existing deployment must be preserved.
>
> Portability constraint (relevant if you ever add an `ALTER`): the runner splits statements on
> the terminator, recognizes only one `add column if not exists` per `ALTER`, and does not
> support `DROP ... CASCADE` on SQLite. Hence: one `ALTER` per column, no `CASCADE`, and no `;`
> inside comments.

### 3.1 `knowledge_bases`

Minimal, platform-owned shape. No `tenant_id`, no scope/visibility, no build-control columns.

```sql
create table if not exists knowledge_bases (
  id text primary key,
  owner_user_id text references users(id) on delete set null,
  name text not null,
  description text,
  status text not null default 'active' check (status in ('active', 'archived')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_knowledge_bases_owner_status
  on knowledge_bases (owner_user_id, status);
```

| Column | Meaning |
| --- | --- |
| `status` | Single lifecycle/usability state. `active` = usable; `archived` = retired, rejects writes. |
| `owner_user_id` | Creator attribution only — **not** an access-control input. |
| `metadata` | Free-form business tags. |

### 3.2 `documents`

```sql
create table if not exists documents (
  id text primary key,
  knowledge_base_id text not null references knowledge_bases(id) on delete cascade,
  file_name text not null,
  file_type text not null
    check (file_type in ('pdf', 'docx', 'pptx', 'xlsx', 'md', 'txt', 'html', 'csv', 'json')),
  mime_type text,
  storage_key text not null,
  object_bucket text not null,
  object_version text,
  content_hash text,
  file_size_bytes bigint not null,
  language text check (language in ('zh', 'en', 'mixed')),
  parse_status text not null default 'pending'
    check (parse_status in ('pending', 'processing', 'ready', 'failed')),
  index_status text not null default 'pending'
    check (index_status in ('pending', 'processing', 'ready', 'failed', 'stale')),
  created_by text not null references users(id),
  deleted_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_documents_kb_status
  on documents (knowledge_base_id, parse_status, index_status)
  where deleted_at is null;

create unique index if not exists idx_documents_storage_key
  on documents (storage_key);
```

Notes:

- `storage_key` (plus `object_bucket`) is the only locator for the MinIO object. There is no
  `storage_url`.
- `object_bucket` comes from `settings.minio_bucket` today but is persisted **`not null`** so
  historical objects stay locatable if the configured bucket changes.
- Chunking is decided at build time — there are **no** `chunk_strategy*` columns.
- On upload completion, `parse_status` and `index_status` both default to `pending`.
- `content_hash` is left null at completion (see §5.3) and is intended to be recomputed at
  build time.

### 3.3 `upload_sessions`

Tracks a single MinIO direct-upload handshake.

```sql
create table if not exists upload_sessions (
  id text primary key,
  knowledge_base_id text not null references knowledge_bases(id) on delete cascade,
  document_id text not null,
  actor_user_id text not null references users(id) on delete cascade,
  upload_mode text not null default 'single_put'
    check (upload_mode in ('single_put', 'multipart')),
  file_name text not null,
  file_type text not null
    check (file_type in ('pdf', 'docx', 'pptx', 'xlsx', 'md', 'txt', 'html', 'csv', 'json')),
  content_type text,
  file_size_bytes bigint not null,
  object_bucket text not null,
  object_key text not null unique,
  multipart_upload_id text,
  status text not null default 'initiated'
    check (status in ('initiated', 'completed', 'aborted', 'expired', 'failed')),
  expires_at timestamptz not null,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_upload_sessions_status
  on upload_sessions (status, expires_at);

create index if not exists idx_upload_sessions_document
  on upload_sessions (document_id);
```

Notes:

- `document_id` is allocated at **upload-url** time (the object key depends on it), but the
  `documents` row is only inserted at **complete-upload**. Therefore `document_id` here is
  plain text, **not** a foreign key.
- Only `single_put` is implemented. `multipart` columns (`upload_mode`, `multipart_upload_id`)
  exist for forward compatibility but no multipart endpoints are wired yet.

### 3.4 Removed legacy schema

The legacy ingestion model (`document_chunks`, `ingestion_jobs`) and the legacy columns
(`tenant_id`, `storage_url`, `chunk_strategy` / `chunk_strategy_version` / `chunk_config`, and
the KB `scope` / `visibility` / `build_provider` / `build_status` / `active_build_id` /
`last_built_at`) no longer exist in the schema — they were dropped when the canonical
definitions in `002`/`003` were consolidated. No backward compatibility is kept; databases
created before the redesign should be rebuilt from the current SQL.

---

## 4. API Surface

All routes require a **platform principal** with the listed permission (§7). Documents and
builds are nested under a knowledge base; there are **no** top-level `/documents` or
`/uploads` routes.

### 4.1 Knowledge bases — `/api/v1/knowledge-bases`

| Method | Path | Permission | Notes |
| --- | --- | --- | --- |
| POST | `` | `kb:create` | Creates KB, `status=active`, `owner_user_id=caller`. `201`. |
| GET | `` | `kb:read` | Lists all platform knowledge bases. |
| GET | `/{knowledge_base_id}` | `kb:read` | |
| PATCH | `/{knowledge_base_id}` | `kb:update` | Archived KB rejects write (`409 KB_ARCHIVED`). |
| DELETE | `/{knowledge_base_id}` | `kb:delete` | Hard delete; cascades to documents/sessions. `204`. |

### 4.2 Documents — `/api/v1/knowledge-bases/{knowledge_base_id}/docs`

| Method | Path | Permission | Notes |
| --- | --- | --- | --- |
| POST | `/upload-url` | `doc:create` | Returns presigned PUT + allocated `documentId`/`uploadSessionId`. |
| POST | `/complete-upload` | `doc:create` | Verifies object, inserts `documents` row. `201`. |
| GET | `` | `doc:read` | Lists non-deleted documents. |
| GET | `/{document_id}` | `doc:read` | |
| PATCH | `/{document_id}` | `doc:update` | Updates `fileName` / `metadata` only. |
| DELETE | `/{document_id}` | `doc:delete` | **Soft delete** (`deleted_at`). `204`. |
| GET | `/{document_id}/download-url` | `doc:read` | Returns presigned GET. |

The service always verifies `document_id` belongs to the path `knowledge_base_id` via a
combined `(knowledge_base_id, document_id)` lookup in the repository.

### 4.3 Build (placeholder) — `/api/v1/knowledge-bases/{knowledge_base_id}`

| Method | Path | Permission | Behavior |
| --- | --- | --- | --- |
| POST | `/build` | `kb:build` | `501` stub |
| GET | `/builds` | `kb:read` | `501` stub |
| GET | `/builds/{build_id}` | `kb:read` | `501` stub |
| POST | `/builds/{build_id}/cancel` | `kb:build` | `501` stub |

All four return HTTP `501` with a fixed body and produce **no** DB side effects:

```json
{
  "status": "not_implemented",
  "knowledgeBaseId": "kb_123",
  "message": "Build is not implemented yet; this endpoint is a placeholder."
}
```

The `BuildRequest` model (`force`, `documentIds`, `config`) is parsed for contract stability
but otherwise unused.

---

## 5. Object Storage Upload Flow

### 5.1 Request upload URL

`POST /api/v1/knowledge-bases/{knowledge_base_id}/docs/upload-url`

Request (`UploadUrlRequest`):

```json
{
  "fileName": "guide.pdf",
  "mimeType": "application/pdf",
  "fileSizeBytes": 102400,
  "contentHash": "sha256_optional"
}
```

Server steps (`DocumentService.create_upload_url`):

1. Authorize: load the KB; `authorize_kb_access(principal, kb, "doc")` rejects archived KBs.
2. Validate `fileSizeBytes > 0` (`400 DOC_INVALID_SIZE`) and
   `fileSizeBytes <= EXPERT_NEXT_OBJECT_STORAGE_MAX_UPLOAD_BYTES` (`413 OBJECT_TOO_LARGE`).
3. Sanitize the file name (strip path separators + control chars; reject `.`/`..`/empty —
   `400 DOC_INVALID_FILE_NAME`).
4. Resolve `file_type` from the **file extension** against a whitelist; unknown →
   `400 DOC_UNSUPPORTED_TYPE`. This guarantees the later `documents.file_type` CHECK holds.
5. Allocate `document_id = doc_<hex>` and `session_id = upl_<hex>`.
6. Compute the object key (§6) and an `expires_at = now + presigned_url_ttl_seconds`
   (default **900s**).
7. Insert an `upload_sessions` row with `status='initiated'`, `object_bucket = store.bucket`.
8. Sign a presigned PUT URL, then `commit`.

Response (`UploadUrlResponse`):

```json
{
  "uploadSessionId": "upl_...",
  "documentId": "doc_...",
  "method": "PUT",
  "uploadUrl": "https://minio.example.com/expert-files/...",
  "headers": { "Content-Type": "application/pdf" },
  "objectKey": "knowledge-bases/kb_123/documents/doc_123/guide.pdf",
  "expiresAt": "2026-06-03T10:10:00Z"
}
```

`headers` is populated only when `mimeType` is provided.

In `local` mode, `uploadUrl` is a backend route such as
`/api/v1/storage/objects/<token>` instead of a filesystem path.

### 5.2 Client uploads the object

The client issues `PUT {uploadUrl}` with the raw file body and the matching `Content-Type`
header. In `minio` mode this request goes directly to MinIO/S3. In `local` mode this
request goes to the backend's signed storage route, which streams the body to disk and
rejects bodies larger than the upload session's declared `fileSizeBytes` or
`EXPERT_NEXT_OBJECT_STORAGE_MAX_UPLOAD_BYTES`.

### 5.3 Complete upload

`POST /api/v1/knowledge-bases/{knowledge_base_id}/docs/complete-upload`

Request (`CompleteUploadRequest`):

```json
{
  "uploadSessionId": "upl_...",
  "etag": "minio-etag",
  "fileSizeBytes": 102400
}
```

Server steps (`DocumentService.complete_upload`):

1. Authorize (same as §5.1).
2. Load the session; `404 UPLOAD_SESSION_NOT_FOUND` if missing.
3. Verify `session.knowledge_base_id` matches the path (`400 UPLOAD_SESSION_MISMATCH`).
4. Verify `status == 'initiated'` (`409 UPLOAD_SESSION_NOT_ACTIVE`).
5. If past `expires_at`: set session `expired`, commit, `409 UPLOAD_SESSION_EXPIRED`.
6. **HEAD the object** and enforce size: `stat.size` must equal
   `upload_sessions.file_size_bytes`. A presigned PUT does **not** bound the written size, so
   the stored size (HEAD) is authoritative — the client-supplied `fileSizeBytes` is **not**
   trusted. On mismatch: set session `failed`, commit, best-effort remove the object, and
   return `400 UPLOAD_SIZE_MISMATCH` with `{declared, actual}`. (A missing object yields
   `404 DOC_OBJECT_NOT_FOUND` from the object store.)
7. Insert the `documents` row (`parse_status='pending'`, `index_status='pending'`,
   `content_hash=null`). The single-PUT ETag is the object MD5, not the declared sha256, so
   `contentHash` is **not** verified here — it is deferred to build-time recomputation.
8. Set session `completed` (+ `completed_at`), commit.

Response is the created `Document` (`201`):

```json
{
  "id": "doc_123",
  "knowledgeBaseId": "kb_123",
  "fileName": "guide.pdf",
  "fileType": "pdf",
  "mimeType": "application/pdf",
  "fileSizeBytes": 102400,
  "storageKey": "knowledge-bases/kb_123/documents/doc_123/guide.pdf",
  "contentHash": null,
  "parseStatus": "pending",
  "indexStatus": "pending",
  "metadata": {},
  "createdAt": "2026-06-03T10:00:00Z",
  "updatedAt": "2026-06-03T10:00:00Z"
}
```

> Note: the design doc mentions marking the KB `stale` on document change. Since the KB
> `build_status` column was removed, **the shipped code performs no such marking** — there is
> no build state to update yet.

---

## 6. Object Key Specification

Object keys are generated by the server; clients never supply them. There is **no tenant
prefix** — KB/doc are platform-side resources.

```text
knowledge-bases/{knowledge_base_id}/documents/{document_id}/{safe_file_name}
```

Example: `knowledge-bases/kb_123/documents/doc_123/guide.pdf`

Rules:

- `safe_file_name` has path separators and control characters stripped to a clean basename.
- Each `document_id` maps to exactly one object key (enforced by the unique
  `idx_documents_storage_key` index and the unique `upload_sessions.object_key`).
- Deletion locates the object via the database `storage_key`, never a client-supplied key.

---

## 7. Authorization Model

### 7.1 Permissions

Two-segment `resource:action` names (matching `app/domain/auth.py`), matched by exact string —
there is no prefix/wildcard inheritance, so three-segment names like `kb:doc:*` are not used.

```text
kb:create   kb:read   kb:update   kb:delete   kb:build
doc:create  doc:read  doc:update  doc:delete
```

Platform role grants (`platform_role_permissions`):

| Role | KB | Doc |
| --- | --- | --- |
| `expert` | create/read/update/delete/build | create/read/update/delete |
| `admin` | create/read/update/delete/build | create/read/update/delete |
| `operator` | read only | — |

Tenant roles hold **no** `kb:*` / `doc:*` permissions and cannot reach these routes at all —
they consume knowledge bases only through the chat product workflow.

### 7.2 Two-stage authorization

1. **Action-level (route guard).** `require_platform_permission("<perm>")` in `deps.py`
   requires a platform principal (`require_platform_principal`) that holds the exact
   permission, else `403 AUTH_FORBIDDEN`.
2. **Resource-level (lifecycle gate).** `authorize_kb_access(principal, kb, action)` in
   `kb_authz.py` adds the **only** remaining resource rule: a write action
   (`update` / `delete` / `doc` / `build`) against a non-`active` KB raises
   `409 KB_ARCHIVED`. Read actions are unrestricted beyond the route permission.

There is deliberately **no** owner/scope/visibility check — `owner_user_id` is attribution
only. This is not tenant isolation; tenant principals never reach these routes.

Document-to-KB membership is enforced structurally: the repository queries by
`(knowledge_base_id, document_id, deleted_at is null)`, so a document under the wrong KB is
simply `404 DOC_NOT_FOUND`.

---

## 8. Deletion Semantics

`DELETE /docs/{document_id}` is a **soft delete**: it sets `documents.deleted_at` and returns
`204`. The MinIO object is **not** removed in the request path.

Immediate-effect guarantee: every read path filters `deleted_at is null`
(`get_document`, `list_documents`, `get_storage_key`), so a soft-deleted document disappears
from all API responses instantly without waiting for any rebuild.

Retrieval-side requirement (Phase 4, not yet implemented): chat/search must likewise filter
referenced documents by `documents.deleted_at is null` so residual chunks in a stale index are
never returned. This closes the "deleted content still retrievable until rebuild" window.

The underlying object is reclaimed asynchronously by GC (§9).

---

## 9. Garbage Collection

Two background reclamation methods exist on `DocumentService` (callable by ops/cron; no
scheduler or ops HTTP endpoint is wired yet):

- `expire_stale_sessions()` — finds `initiated` sessions past `expires_at`, sets them
  `expired`, and best-effort removes their (possibly orphan) MinIO objects. This reclaims the
  case where a client fetched an upload URL but never completed.
- `purge_deleted_objects(limit=100)` — for soft-deleted documents, best-effort removes the
  object by `storage_key` then hard-deletes the row.

Object removal is best-effort (`_best_effort_remove` swallows errors); GC retries by key on a
later pass.

---

## 10. Security Requirements

- The bucket grants no anonymous write access.
- Presigned URLs are short-lived: `presigned_url_ttl_seconds` defaults to **900s** (15 min),
  used for both PUT and GET. Local `/api/v1/storage/objects/{token}` routes are public
  presigned-URL endpoints and rely on this token TTL plus the `object-store` JWT audience.
- Object keys are server-generated only (§6).
- `complete-upload` HEADs the object to confirm existence **and** exact declared size.
- File type (extension whitelist), positive size and the configured maximum upload size are
  validated **before** signing the URL.
- Deletion uses the DB `storage_key`, never a client-supplied key.
- Downloads are served via short-lived presigned GET URLs, not API proxying.
- ETag ≠ content hash: the single-PUT ETag is the object MD5, so the client's declared sha256
  `contentHash` is not verifiable at completion; integrity verification is deferred to
  build-time recomputation.
- Orphan objects and dangling `initiated` sessions are reclaimed by GC (§9).

---

## 11. Deferred Work (Phases 3–4)

The following are designed in
[`KNOWLEDGE_BASE_STORAGE_AND_BUILD_DESIGN.md`](./KNOWLEDGE_BASE_STORAGE_AND_BUILD_DESIGN.md)
(sections 7.4, 8, 9) but **not implemented**:

- **Phase 3 — Build worker & providers.** A `knowledge_base_builds` table; build endpoints
  that create records, snapshot the document set (`input_snapshot`), and queue work; a worker
  that downloads objects by `storage_key`, parses/chunks/indexes, and writes back status; a
  `KnowledgeBaseBuildProvider` abstraction (`None` / PageIndex / Qdrant / custom). PageIndex
  becomes one provider, not an API pass-through target.
  - Open design points to resolve at that time: a comparable KB-level version watermark to
    guard the `stale` transition; concurrency mutual-exclusion (one queued/running build per
    KB); a foreign key for `active_build_id`; reconciling KB-level vs build-record status
    vocabularies; and reintroducing whichever build-control columns the worker needs (they
    were removed from `knowledge_bases` in the minimal shape).
- **Phase 4 — Retrieval integration.** Chat/search locate the usable index via the (future)
  active build, may continue serving the previous build while a KB has unbuilt changes, and
  **must** filter retrieved hits by `documents.deleted_at is null` (§8).

Large-file **multipart** upload is likewise deferred; the schema reserves `upload_mode` and
`multipart_upload_id`, but only `single_put` is implemented.

---

## 12. Key Decisions (summary)

- Local DB is the single source of truth; no PageIndex pass-through.
- The API is a control plane and never proxies document bytes.
- Object keys are server-generated, with no tenant prefix.
- KB/doc/upload carry no `tenant_id`; access is purely permission-based; `owner_user_id` is
  attribution only.
- `complete-upload` trusts the MinIO HEAD size, which must equal the session-recorded size,
  else it rejects and cleans up.
- Document deletion is soft and effective immediately; reads filter `deleted_at is null`.
- `object_bucket` is persisted `not null` (single bucket from config today).
- Build endpoints are `501` placeholders — no table, no records, no state changes.
- The migration runner re-runs all SQL every boot, so each file holds the final schema as
  create-if-not-exists definitions — no migration history, no incremental patch files.
