# Expert Next API Architecture

## 1. Goal

Replace the current TypeScript/Node expert-system API with a Python 3 + FastAPI
service while reducing owned implementation surface.

The new service should keep the client-facing API stable enough for the current
web/API consumers, while owning control-plane data locally and delegating agent
runtime work to external systems:

- agent-gateway ACP data plane: chat sessions, turns, streaming and agent runtime.
- Codex skills: skill discovery, installation and file management.
- Expert Next API: tenant/auth/RBAC, compatibility routing, orchestration,
  audit/metrics, and API-level governance.

## 2. External References

- agent-gateway ACP route contract:
  - `POST {prefix}/turn`
  - `POST {prefix}/permission`
  - `GET {prefix}/sessions`
  - `GET {prefix}/sessions/{id}/transcript`

## 3. High-Level Architecture

```text
Client / Web Console
        |
        v
FastAPI Expert Next API
        |
        +-- AuthService / TenantService / RBAC
        |
        +-- KnowledgeBaseService / DocumentService
        |      +-- local metadata database
        |      +-- shared object storage
        |
        +-- AcpGatewayClient
        |      +-- codex ACP runtime
        |      +-- local chat sessions as ACP thread ids
        |      +-- local chat turns with translated ACP SSE events
        |
        +-- CodexSkillsClient
               +-- ~/.codex/skills or configured skills dir
               +-- install/uninstall/read skill files
```

## 4. API Classification

### 4.1 Auth and Tenant APIs

Owned by Expert Next API.

Current scaffold:

- `POST /api/v1/users/register`
- `POST /api/v1/users/platform/activate`
- `POST /api/v1/users/platform`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/rbac/tenant/users`
- `POST /api/v1/rbac/tenant/users/{id}/roles`
- `DELETE /api/v1/rbac/tenant/users/{id}`
- `POST /api/v1/rbac/platform/users/{id}/roles`
- `DELETE /api/v1/rbac/platform/users/{id}/roles/{role}`

Authorization behavior:

- Access tokens carry identity and roles only; permission lists are derived from
  role mappings server-side.
- Auth dependencies reload the user and current roles from the database on each
  authenticated request, so user disablement and role/membership revocation are
  enforced immediately.
- Tenant-scoped APIs require `x-tenant-id` to match the active tenant context.

Future work:

- Add audit log for role changes and login failures.

### 4.2 Knowledge Base APIs

Platform-authored resources. Knowledge bases have **no tenant relationship** (no `tenant_id`,
no official/tenant/private visibility); access is decided purely by the platform permission on
the route. Canonical contract: `docs/KNOWLEDGE_BASE_STORAGE_AND_BUILD_SPEC.md`.

Current API shell:

- `POST /api/v1/knowledge-bases`
- `GET /api/v1/knowledge-bases`
- `GET /api/v1/knowledge-bases/{id}`
- `PATCH /api/v1/knowledge-bases/{id}`
- `DELETE /api/v1/knowledge-bases/{id}` — soft delete; objects are reclaimed by storage GC

Design:

- Expert Next API enforces auth and platform RBAC (`kb:*`). `owner_user_id` is creator
  attribution, not access control.
- A single `status` (`active`/`archived`) answers whether a base is usable; archived bases
  reject writes.
- Build is deferred: `POST /{id}/build` and the `/{id}/builds*` routes are placeholders
  (validate the base, then return 501). See section 4.3 of the spec.

### 4.3 Document and Upload APIs

Documents are nested under a knowledge base and uploaded through the configured object storage
backend. In `minio` mode the client uploads directly to MinIO/S3 via presigned URLs; in `local`
mode the client uploads to a signed backend storage route that streams to disk. There are **no**
top-level `/documents` or `/uploads` routes, and no jobs/chunks/reindex/multipart endpoints.
Canonical contract:
`docs/KNOWLEDGE_BASE_STORAGE_AND_BUILD_SPEC.md`.

Current API shell (all nested under `/api/v1/knowledge-bases/{id}/docs`):

- `POST .../docs/upload-url` — mint a presigned PUT + create an upload session
- `POST .../docs/complete-upload` — verify the object (HEAD) and create the document
- `GET .../docs` / `GET .../docs/{documentId}`
- `PATCH .../docs/{documentId}` — rename / metadata
- `DELETE .../docs/{documentId}` — soft delete; object reclaimed by storage GC
- `GET .../docs/{documentId}/download-url` — presigned GET

Design:

- The control plane only mints/verifies presigned URLs and removes objects; chunking and
  indexing are decided at build time, not here.
- Delete is a soft delete (`deleted_at`) so the cascade never strands MinIO objects. Storage GC
  (`POST /api/v1/ops/storage/gc`, `system:ops`) reclaims expired upload-session objects,
  soft-deleted document objects and soft-deleted knowledge-base objects, then hard-deletes rows.

### 4.4 Chat APIs

Compatibility API owned by Expert Next API; execution delegated to the ACP data plane.

Current API shell:

- `POST /api/v1/chat/sessions`
- `GET /api/v1/chat/sessions`
- `GET /api/v1/chat/sessions/{id}`
- `DELETE /api/v1/chat/sessions/{id}`
- `GET /api/v1/chat/sessions/{id}/messages`
- `PATCH /api/v1/chat/sessions/{id}/title`
- `PATCH /api/v1/chat/sessions/{id}/pin`
- `POST /api/v1/chat/sessions/{id}/turns` (create + stream)
- `POST /api/v1/chat/turns/{id}/cancel`
- `GET /api/v1/chat/turns/{id}/events`
- `POST /api/v1/chat/permissions/{id}`

Mapping:

- Chat session -> locally generated ACP thread id.
- Chat turn -> locally generated turn id plus a durable assembled turn record.
- Turn creation streams SSE in one shot (no separate create/subscribe step); the
  `GET /turns/{id}/events` endpoint replays the stored turn record.
- ACP SSE events are translated to the existing public event names.
- Chat does not accept or forward knowledge-base scope; knowledge-base management remains
  owned by the KB/document APIs.
- Tenant-scoped ACP calls include `X-Tenant-Id`; local ownership remains the primary
  authorization boundary.

Open decisions:

- Whether retrieval context is injected into Codex prompt by Expert Next API,
  by ACP tools, by MCP, or by Codex skills.
- Whether session pinning remains local metadata.
- How to expand ACP permission requests for richer web UI flows.

### 4.5 Skill APIs

Owned by Expert Next API, backed by the `skills` database table and the shared
object storage backend. Skills are platform-managed assets, not tenant/user
installation records.

Current APIs:

- `POST /api/v1/skills`
- `GET /api/v1/skills`
- `GET /api/v1/skills/{slug}`
- `PUT /api/v1/skills/{slug}`
- `DELETE /api/v1/skills/{slug}`
- `GET /api/v1/skills/{slug}/file`

Design:

- Treat skills as Codex-native assets, not a separate product-specific format.
- Upload accepts a zip containing `SKILL.md`, parses frontmatter, validates a
  slug, stores files, and records metadata.
- Database metadata includes slug, name, description, version, allowed tools,
  file paths, tags and storage URI.
- Storage backend is selected by `EXPERT_OBJECT_STORAGE_BACKEND`, which
  defaults to local storage for development and should be set to `minio` for
  production. The same setting is used by documents and library files. Skill
  objects always use the `skills/{slug}/...` object-key prefix.

### 4.6 Models and Ops APIs

Current API shell:

- `GET /api/v1/models/llm`
- `GET /api/v1/models/embedding`
- `GET /api/v1/ops/metrics`
- `GET /health`

Design:

- LLM model discovery should eventually use ACP/gateway route metadata when available.
- Embedding model metadata is currently unconfigured and should be wired only
  when a concrete retrieval backend is selected.
- Metrics should expose local adapter metrics and upstream health.

## 5. Project Structure

```text
next_api/
  app/
    api/
      deps.py                 # FastAPI dependencies and auth guards
      v1/routers/             # Old API-compatible route groups
    clients/
      acp_gateway.py          # agent-gateway ACP data-plane adapter
      codex_skills.py         # Codex skills filesystem adapter
    core/
      config.py               # pydantic-settings configuration
      errors.py               # unified API error handling
      security.py             # JWT/password helpers
    domain/                   # Pydantic request/response/domain models
    services/
      auth_service.py         # placeholder auth service
    main.py                   # FastAPI app factory
  docs/
    ARCHITECTURE.md
```

## 6. Migration Plan

### Phase 1: Framework and API Shell

- Create FastAPI project and route modules.
- Preserve old route paths and coarse response shapes.
- Add adapters for ACP and Codex skills.
- Make OpenAPI load and fail clearly when upstreams are not configured.

Status: scaffolded.

### Phase 2: Persistent Auth and Tenancy

- Add SQLAlchemy/Alembic.
- Migrate tenant, user, role, refresh token and platform user activation flows.
- Add request-scoped tenant enforcement and audit logging.
- Add test coverage for auth and RBAC.

### Phase 3: Retrieval Integration

- Decide the retrieval/indexing backend and integration mode.
- Implement exact mappings for document indexing and job status.
- Keep knowledge-base, document and upload-session metadata in the local database.
- Remove all legacy ingestion/vector-store assumptions.

### Phase 4: ACP/Codex Chat Integration

- Align old session/task API to ACP turn/session APIs.
- Normalize SSE events to the existing web client contract.
- Add cancellation, event replay, active-turn conflict behavior and permission
  workflow.
- Decide how retrieval context is made available to Codex.

### Phase 5: Skills Integration

- Parse and validate `SKILL.md`.
- Add install/uninstall semantics across users/tenants if needed.
- Add marketplace/listing behavior only if product requirements demand it.

### Phase 6: Governance and Operations

- Add rate limiting.
- Add upstream health checks.
- Add metrics for auth, ACP, skills and request latency.
- Add structured logging and trace IDs.

## 7. Risks and Design Notes

- Retrieval/indexing backend selection is still open; keep document metadata and
  upload contracts owned by this service.
- ACP sessions are not a perfect match for legacy chat sessions; pinning, ownership
  and tenant scoping need local metadata.
- Codex skills are filesystem assets; multi-tenant skill isolation must be
  designed before production.
- The current scaffold uses in-memory auth only. It is suitable for API shape
  development, not production.
