# AGENTS.md

Self-readme for AI agents working in `experts-backend`.

## What this is

FastAPI control-plane backend. It owns auth/RBAC, knowledge bases, documents, chat and skills.
ngent / Codex are upstream/optional integrations, not the source of truth.

## Conventions

- All code text (comments, messages, identifiers, commit messages) is in **English**.
- Layering (see `skills` / `knowledge_bases` for the canonical pattern):
  `app/domain/*` (pydantic models, camelCase fields) → `app/services/*_repository.py`
  (raw SQL, `?` placeholders) → `app/services/*_service.py` (orchestration + `commit`) →
  `app/api/v1/routers/*` (`Depends(get_database)` + `Depends(require_platform_permission(...))`).
- Shared SQL helpers: `app/services/_sql.py` (`execute`/`fetch_one`/`fetch_all`/`json_param`/`json_load`).
  `prepare_sql` rewrites `?`→`%s` for Postgres; pass JSON via `json_param`.

## Database & migrations (read before touching `infra/sql/`)

- Backends: SQLite (default/tests) and PostgreSQL. `app/db.py` migrates both.
- **Foreign keys are enforced at runtime on both backends**: `_open_sqlite` sets
  `pragma foreign_keys = on` per connection (off by default in SQLite), matching PostgreSQL.
  So `ON DELETE CASCADE` and FK constraints fire at runtime — rely on cascade instead of
  manually deleting child rows. Note soft-deleted parents (e.g. knowledge bases) never trigger
  cascade; filter `deleted_at is null` on reads instead.
- **The runner re-runs every `infra/sql/*.sql` on each boot and has NO applied-migrations
  table.** Idempotency is mandatory: use `create table if not exists` / `add column if not
  exists` / `drop ... if exists`. **Never** write an unconditional `drop table + create table`
  — it wipes data on every restart.
- SQLite quirks the runner imposes: one `add column if not exists` per `ALTER`; no
  `DROP TABLE ... CASCADE`; statements split on `;`, so **no `;` inside SQL comments**;
  `alter column` / `add constraint` are skipped on SQLite.
- Each file is the canonical (final) shape of its tables, with every column/index/constraint
  folded into the `create table if not exists`. Files are numbered only to order FK dependencies
  (`sorted(glob)`), not as a migration history — there are no incremental patch files. When you
  evolve a table, edit its `create table` in place (dev rebuilds the DB); add an idempotent
  `alter ... if [not] exists` only when an existing deployment must be preserved.

## Auth model

- Platform roles (`admin`/`expert`/`operator`) vs tenant roles (`admin`/`member`).
- Knowledge bases, documents and skills are **platform-authored and have no tenant relationship**
  (no `tenant_id`). Tenants hold no `kb:*`/`doc:*`/`skill:*` and consume only via chat.
- Permission checks are exact-string membership (`app/api/deps.py`), no wildcard/prefix hierarchy.
- Knowledge bases are platform-owned with a deliberately minimal shape: a single `status`
  (`active`/`archived`), no scope/visibility, no build columns. Access is decided purely by the
  route permission; `owner_user_id` is creator attribution, not access control. The only
  resource-level rule (an archived KB rejects writes) lives in `app/services/kb_authz.py`.
- **KB and document delete are soft deletes** (`deleted_at`), so the `documents`/`upload_sessions`
  ON DELETE CASCADE never strands MinIO objects (a hard cascade drops the rows that hold the
  `storage_key` needed to reclaim them). `DocumentService` GC reclaims objects then hard-deletes:
  `purge_deleted_objects` (docs) and `purge_deleted_knowledge_bases` (KBs). All reads must filter
  `deleted_at is null`. GC has no scheduler/entry point yet — call it directly. complete-upload
  guards concurrent completion via the `documents` PK and maps the collision to 409, not 500.
- **Batch upload endpoints (`/docs/upload-urls`, `/docs/complete-uploads`) are non-atomic**: each
  file is its own transaction (`DocumentService` loops the single-item method). They never abort
  mid-batch — each `items[]` entry reports `status` (`created`/`completed` vs `failed`) and a
  per-item `error`, so callers retry only failures. Both return `200` (not `201`).

## Chat (ngent integration)

- **ngent is a compute engine, not the source of truth.** Its store is single-node SQLite,
  unbacked, and enforces **no tenant/user isolation** (any bearer token can read/delete any
  thread/turn by id). So the **local DB is the system of record**: `chat_sessions` / `chat_turns`
  mirror ngent's thread/turn shape plus ownership (`tenant_id`, `user_id`) and product fields
  (pin) ngent lacks. Session/turn ids equal ngent's thread/turn ids.
- Every chat endpoint authorizes by **local ownership** (caller's tenant+user) before calling
  ngent — never trust ngent to scope. Flat `/turns/{id}/*` ops check `chat_turns` ownership.
- **Per-tenant working dir**: when `EXPERT_NGENT_CWD_BASE` is set, `NgentClient.prepare_cwd`
  gives each session `cwd = <base>/<tenant_id>` (created on demand, since ngent requires cwd to
  exist); empty base shares `ngent_default_cwd`. This is soft filesystem separation, not a
  sandbox — the real boundary is ngent's `allowedRoots`. Backend and ngent must share the host so
  the mkdir is visible to ngent.
- Turn creation is **single-step streaming**: `POST /sessions/{id}/turns` returns the ngent SSE
  stream directly; `ChatService.stream_turn` tees it — forwards to the caller while parsing
  `turn_started` (captures turnId → insert) / `message_delta` (assemble) / `turn_completed`
  (finalize). Client disconnect before completion can leave a turn `running` (known gap; reconcile
  on read later). Only the assembled turn is stored — no per-event log table yet.
- **Auto session title**: persisted via `repo.update_session_title` and re-emitted to the caller
  as a unified `session_title_updated` SSE frame. Fill-only-when-empty: written solely while the
  local title is blank, so a user's manual rename (`PATCH /sessions/{id}/title`) is never
  clobbered. Source differs per backend:
  - ngent: rides the turn stream as a `session_info_update` event (title at `data.title`). Note
    `GET /v1/threads/{id}` returns the manual `thread.title`, a *separate* field from this evolving
    session title.
  - ACP: **codex-acp does NOT emit `session_info_update`**, so the live `session_info` SSE event
    never fires for it — codex's title is only on the route-scoped `session/list`
    (`GET {prefix}/sessions` → `sessions[].title`, auto-derived from the first user message).
    `_stream_turn_acp` reconciles it after the turn via `_fetch_acp_title` (`AcpGatewayClient.list_sessions`),
    matching `sessions[].session_id` to `chat_sessions.acp_session_id`. The inline `session_info`
    branch is kept for agents that *do* emit it (e.g. opencode).
- The turn request body is **`question` plus `attachmentFileIds`** (and `webSearchEnabled`).
  ngent's turn API takes just the prompt (`{input, stream}`), so model / knowledge-base / retrieval
  options are not accepted and the `chat_turns` option columns are stored as defaults — do not
  re-add request fields without wiring them into the outgoing payload. `attachmentFileIds` *is*
  wired (see Chat attachments below). The streaming handler opens its own DB connection
  (`open_database_connection`) inside the generator, since the request-scoped `get_database`
  connection is closed before the `StreamingResponse` body runs; a route-level pre-flight
  (`validate_turn_preconditions`) authorizes the session + attachments before the stream starts,
  so denials are clean HTTP errors rather than an empty 200 stream.

### Chat attachments & library file lifecycle

- Chat temporary files **reuse the library tables** (`library_files`) rather than a new store — see
  `docs/LIBRARY_FILE_LIFECYCLE.md`. `library_files` carries lifecycle columns (`source`, `lifecycle`,
  `expires_at`, `promoted_at`, `chat_session_id`) under a named cross-column invariant
  (`library_files_lifecycle_invariant`): `temporary => expires_at not null` (its `chat_session_id`
  may be null while **unbound**); `permanent => expires_at null`. The invariant is a table-level
  check (fresh DBs) + an existing-PostgreSQL `DO` block (drop-then-add, so it updates in place) +
  **app-layer `validate_lifecycle_invariant` on every write** (the only enforcement on existing
  SQLite, where `ADD CONSTRAINT` is skipped).
- **Upload is unified under `/library/files`** (no `/chat/attachments/*` routes):
  `POST /library/files/upload-url` + `/complete-upload` with `lifecycle: "temporary"|"permanent"`. A
  temporary file is created **unbound** (`chat_session_id is null`), so it can be uploaded before a
  chat session exists.
- **Storage object keys are ASCII-only** (`_ascii_key_name` in `library_service.py`). A non-ASCII key
  (e.g. a Chinese filename) forces PyJWT to `\uXXXX`-escape the object key inside the signed
  presigned-URL token; a client that re-encodes the URL (codex did this) strips the backslashes and
  breaks the signature → 401. The real display name is preserved separately as `original_name`, so
  the key name is cosmetic. The delivered URL must also be **absolute** — set
  `EXPERT_OBJECT_STORAGE_PUBLIC_BASE_URL` (local backend) / a reachable MinIO host, never a bare
  relative path, or the agent resolves it against the wrong origin.
- **Binding is deferred to first turn use**: when a turn's `attachmentFileIds` first references an
  unbound temporary file, `resolve_turn_attachments(..., bind=True)` binds it to that session via a
  once-only conditional update (`where chat_session_id is null`, idempotent/race-safe). The turn
  route pre-flights with `bind=False` (authorize-only) before the SSE stream so denials are clean
  HTTP errors. Authorization (§5): temporary unbound → owner-scoped; temporary bound → owner + that
  session; bound-to-another-session → 403; permanent → owner.
- **Listing**: `GET /library/files` is permanent-only by default (repository layer);
  `?lifecycle=temporary` lists the caller's non-expired temporary files (unbound when no `sessionId`,
  a session's bound files with `&sessionId=`). `user_id`+`tenant_id` are always in the where clause,
  so the `lifecycle` filter can't leak across users. `POST /library/files/{id}/promote` flips
  temporary→permanent with no byte copy (works on unbound files too).
- A turn snapshots its referenced files into `chat_turns.attachments` (jsonb, self-contained) for
  durable provenance that survives GC. Delivery is **presigned-URL** (§8 option A): each authorized
  attachment gets a short-lived GET URL (`attachment_delivery_url`, TTL
  `attachment_delivery_url_ttl_seconds`, default 1h) appended to the runtime input as an
  `[Attachment: name (mime)] Content available at: <url>` block; the engine fetches it. `request_text`
  stays the bare question and the URL is never persisted. The §8.2 server-side text-extraction form
  is a no-network fallback but is not currently wired.
- GC: `LibraryService.purge_expired_temporary_files` (in `/ops/storage/gc`) hard-deletes expired
  temporary rows + objects. Session deletion is **TTL-only** — `delete_session` does no attachment
  cleanup; expired attachments are reclaimed on their own deadline.
- **Expert marketplace (`/expert-market/*`) requires sign-in** (`require_principal`, any
  authenticated caller) but no specific permission; it lists only `published` experts/categories.

### Pluggable compute backend (`EXPERT_CHAT_BACKEND` = `ngent` | `acp`)

- `ChatService` is backend-agnostic; the local DB stays the source of truth either way. The
  router (`build_chat_service`) injects both clients and the configured backend. ngent is the
  default and unchanged; `acp` targets the agent-gateway ACP data plane (`AcpGatewayClient`).
- **ACP exposes four route-scoped data-plane endpoints**: `POST {prefix}/turn` (SSE),
  `POST {prefix}/permission`, `GET {prefix}/sessions`, and `GET {prefix}/sessions/{id}/transcript`
  — all authenticated by the route's VirtualKey (`acp_auth_token`), no admin plane. There is
  **no thread/turn lifecycle, no cancel, no event-replay**.
  Consequences, all hidden behind the same public chat API:
  - `create_session` mints the `thread_id` locally (no upstream call); the agent materializes the
    session lazily on the first turn.
  - The agent-assigned ACP session id arrives via a `session` event on the first turn and is
    stored in `chat_sessions.acp_session_id`, then echoed back as `TurnRequest.session_id` on
    follow-up turns so the gateway resumes the same pooled instance (scope keys on
    `service|cwd|thread_id|session_id|model`, so cwd/model must stay stable per thread).
  - A turn has no server id, so `ChatService` generates one locally and emits `turn_started`
    before any text. ACP events are **translated to the same public contract** ngent exposes
    (`reasoning`/`tool_call`→`reasoning_delta`, `delta`→`message_delta`, `done`→`turn_completed`,
    `permission`→`permission_required`, `error`→`error`), so the frontend is unchanged.
    `rename`/`delete` are local-only; `cancel` best-effort marks the local turn cancelled;
    turn-event replay reads the stored turn.
- Chat does not accept or forward knowledge-base scope to ACP. Knowledge-base management stays
  in the KB/document/expert APIs; ACP retrieval wiring belongs outside the public chat payload.
- **Permission resolution is in-memory on the gateway**: the answer (`POST {prefix}/permission`,
  request id in the body) must reach the same gateway replica holding the pending request — keep
  the ACP gateway single-replica or session-affine.
- **History replay** (`GET /sessions/{id}/transcript`, `ChatService.get_transcript`): returns
  `{sessionId, messages: [{role, text}], source}` with a uniform shape across backends. For ACP,
  when the session has an `acp_session_id`, it loads the agent-side coalesced transcript
  (user/assistant/reasoning) from the **route-scoped** `GET {prefix}/sessions/{id}/transcript`
  (`AcpGatewayClient.get_transcript`); otherwise (ngent, or no turn yet) it rebuilds from the
  durable local `chat_turns` (`source: "local"`). The route-scoped sessions/transcript APIs share
  the data plane's base URL + route prefix and are authenticated by the same VirtualKey
  (`acp_auth_token`) — **no separate admin address, login, or service id** (the route is the scope).
  The transcript is addressed by the ACP session id + tenant cwd (not the local thread id);
  `list_sessions` on the same client backs title reconciliation.
- **Live smoke test**: `python scripts/acp_smoke.py` drives the real `AcpGatewayClient`
  against a running gateway (config from env/.env or `--base-url` etc.). It runs a
  turn and prints the translated events, with `--resume` (session resume), `--transcript` /
  `--list-sessions` (route history APIs), and `--auto-permission` (answer prompts). Use it to validate the
  integration against a real gateway before relying on the backend — the pytest suite only covers
  fakes.

## Tests & lint

- `python -m pytest tests/test_app.py -q` and `ruff check app/ tests/`. Run both before finishing.
- Tests use a TestClient + temp SQLite; inject fakes (e.g. MinIO) via `app.dependency_overrides`.

## Key designs

- `docs/KNOWLEDGE_BASE_STORAGE_AND_BUILD_SPEC.md` (architecture + technical spec, reflects shipped code) — design rationale in `docs/KNOWLEDGE_BASE_STORAGE_AND_BUILD_DESIGN.md`
- `docs/USER_TENANT_RBAC_DESIGN.md`
- `docs/LIBRARY_FILE_LIFECYCLE.md` (chat temporary files & promotion, reflects shipped code).
- API reference under `docs/api/`.
