# Expert Next API Architecture

## 1. Goal

Replace the current TypeScript/Node expert-system API with a Python 3 + FastAPI
service while reducing owned implementation surface.

The new service should keep the client-facing API stable enough for the current
web/API consumers, but delegate specialized work to external systems:

- PageIndex: knowledge base, document management, upload/object storage, document
  indexing and retrieval.
- ngent + Codex/ACP adapter: chat sessions, turns, streaming and agent runtime.
- Codex skills: skill discovery, installation and file management.
- Expert Next API: tenant/auth/RBAC, compatibility routing, orchestration,
  audit/metrics, and API-level governance.

## 2. External References

- PageIndex is a vectorless, reasoning-based RAG project that builds a
  hierarchical document tree and performs reasoning/tree-search retrieval instead
  of vector similarity search. Source: <https://github.com/VectifyAI/PageIndex>
- PageIndex can be used through open-source code, cookbooks/examples, API and MCP
  resources according to its README. The exact integration mode should be decided
  before production wiring.
- ngent local reference: `/Users/simpcl/github/middleware/ngent`
  - HTTP contract: `docs/API.md`
  - ACP/Codex integration notes: `docs/ACP_GATEWAY_INTEGRATION.md`

## 3. High-Level Architecture

```text
Client / Web Console
        |
        v
FastAPI Expert Next API
        |
        +-- AuthService / TenantService / RBAC
        |
        +-- PageIndexClient
        |      +-- knowledge bases
        |      +-- documents
        |      +-- uploads / object storage
        |      +-- document index/search
        |
        +-- NgentClient
        |      +-- codex ACP runtime
        |      +-- chat sessions as ngent threads
        |      +-- chat tasks as ngent turns
        |      +-- SSE event passthrough/adaptation
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

Compatibility API owned by Expert Next API; implementation delegated to PageIndex.

Current API shell:

- `POST /api/v1/knowledge-bases`
- `GET /api/v1/knowledge-bases`
- `GET /api/v1/knowledge-bases/{id}`
- `PATCH /api/v1/knowledge-bases/{id}`
- `DELETE /api/v1/knowledge-bases/{id}`
- `POST /api/v1/knowledge-bases/official`

Design:

- Expert Next API enforces auth, tenant and RBAC.
- Tenant-scoped PageIndex calls include `X-Tenant-Id` so PageIndex can enforce
  resource isolation. Official/platform calls intentionally omit that header.
- PageIndex owns actual corpus/index/project state.
- Store only mapping metadata locally if PageIndex IDs do not directly match old
  API IDs.

Open decisions:

- Whether PageIndex is used as a direct Python SDK, self-hosted HTTP service,
  cloud API, or MCP.
- How PageIndex corpus/project IDs map to old `knowledgeBaseId`.
- Whether official/tenant/private visibility lives locally or in PageIndex
  metadata.

### 4.3 Document and Upload APIs

Compatibility API owned by Expert Next API; implementation delegated to PageIndex.

Current API shell:

- `POST /api/v1/knowledge-bases/{id}/documents`
- `GET /api/v1/knowledge-bases/{id}/documents`
- `GET /api/v1/documents/{id}`
- `GET /api/v1/documents/{id}/jobs`
- `GET /api/v1/documents/{id}/chunks`
- `DELETE /api/v1/documents/{id}`
- `POST /api/v1/documents/{id}/reindex`
- `POST /api/v1/uploads/initiate`
- `POST /api/v1/uploads/complete`
- `POST /api/v1/uploads/multipart/initiate`
- `POST /api/v1/uploads/multipart/parts`
- `POST /api/v1/uploads/multipart/complete`
- `POST /api/v1/uploads/multipart/abort`

Design:

- FastAPI should not parse/index documents itself.
- Tenant-scoped PageIndex calls include `X-Tenant-Id` so PageIndex can enforce
  resource isolation for document and upload ids.
- Upload presigning, storage keys, indexing jobs and status should come from
  PageIndex or a PageIndex-side wrapper service.
- If PageIndex does not expose the exact old upload contract, add a small
  adapter translation layer, not new ingestion logic.

### 4.4 Chat APIs

Compatibility API owned by Expert Next API; execution delegated to ngent.

Current API shell:

- `POST /api/v1/chat/sessions`
- `GET /api/v1/chat/sessions`
- `GET /api/v1/chat/sessions/{id}/messages`
- `PATCH /api/v1/chat/sessions/{id}/title`
- `PATCH /api/v1/chat/sessions/{id}/pin`
- `POST /api/v1/chat/tasks`
- `POST /api/v1/chat/tasks/{id}/cancel`
- `GET /api/v1/chat/tasks/{id}/position`
- `GET /api/v1/chat/tasks/{id}/events`

Mapping:

- Old chat session -> ngent thread.
- Old chat task -> ngent turn.
- Old SSE task events -> ngent turn event stream, adapted to existing event names
  when necessary.
- `llmModel`, `queryRewrite`, `multiHop`, and `knowledgeBaseIds` are passed as
  `agentOptions` until a stricter ngent contract is finalized.
- Tenant-scoped ngent calls include `X-Tenant-Id` so ngent can enforce resource
  isolation for thread and turn ids.

Open decisions:

- Whether PageIndex retrieval is injected into Codex prompt by Expert Next API,
  by ngent tools, by MCP, or by Codex skills.
- Whether session pinning remains local metadata.
- How to map ngent permission requests to existing web UI flows.

### 4.5 Skill APIs

Owned by Expert Next API, backed by the `skills` database table and local or
MinIO skill file storage. Skills are platform-managed assets, not tenant/user
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
- Storage backend is selected by `EXPERT_NEXT_SKILL_STORAGE_BACKEND`, currently
  `local` or `minio`.

### 4.6 Models and Ops APIs

Current API shell:

- `GET /api/v1/models/llm`
- `GET /api/v1/models/embedding`
- `GET /api/v1/ops/metrics`
- `GET /health`

Design:

- LLM model discovery should eventually proxy ngent `/v1/agents/{agentId}/models`.
- Embedding model should become PageIndex-managed or return PageIndex retrieval
  mode metadata.
- Metrics should expose local adapter metrics and upstream health.

## 5. Project Structure

```text
next_api/
  app/
    api/
      deps.py                 # FastAPI dependencies and auth guards
      v1/routers/             # Old API-compatible route groups
    clients/
      pageindex.py            # PageIndex SDK/API adapter
      ngent.py                # ngent HTTP/SSE adapter
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
- Add adapters for PageIndex, ngent and Codex skills.
- Make OpenAPI load and fail clearly when upstreams are not configured.

Status: scaffolded.

### Phase 2: Persistent Auth and Tenancy

- Add SQLAlchemy/Alembic.
- Migrate tenant, user, role, refresh token and platform user activation flows.
- Add request-scoped tenant enforcement and audit logging.
- Add test coverage for auth and RBAC.

### Phase 3: PageIndex Integration

- Decide integration mode: direct SDK, self-hosted API, PageIndex cloud API, or MCP.
- Implement exact mappings for knowledge bases, documents, upload sessions and
  job status.
- Add local ID mapping only if PageIndex IDs cannot be exposed directly.
- Remove all legacy ingestion/vector-store assumptions.

### Phase 4: ngent/Codex Chat Integration

- Align old session/task API to ngent thread/turn APIs.
- Normalize SSE events to the existing web client contract.
- Add cancellation, event replay, active-turn conflict behavior and permission
  workflow.
- Decide how PageIndex search context is made available to Codex.

### Phase 5: Skills Integration

- Parse and validate `SKILL.md`.
- Add install/uninstall semantics across users/tenants if needed.
- Add marketplace/listing behavior only if product requirements demand it.

### Phase 6: Governance and Operations

- Add rate limiting.
- Add upstream health checks.
- Add metrics for auth, PageIndex, ngent, skills and request latency.
- Add structured logging and trace IDs.

## 7. Risks and Design Notes

- PageIndex's public project emphasizes document tree/search capability, not the
  exact legacy knowledge-base/upload REST contract. Expect an adapter wrapper.
- ngent threads are not a perfect match for legacy chat sessions; pinning,
  ownership and tenant scoping may need local metadata.
- Codex skills are filesystem assets; multi-tenant skill isolation must be
  designed before production.
- The current scaffold uses in-memory auth only. It is suitable for API shape
  development, not production.
