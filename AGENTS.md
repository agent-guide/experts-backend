# AGENTS.md

Self-readme for AI agents working in `amazon-experts-backend`.

## What this is

FastAPI control-plane backend. It owns auth/RBAC, knowledge bases, documents, chat and skills.
PageIndex / ngent / Codex are upstream/optional integrations, not the source of truth.

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
- **The runner re-runs every `infra/sql/*.sql` on each boot and has NO applied-migrations
  table.** Idempotency is mandatory: use `create table if not exists` / `add column if not
  exists` / `drop ... if exists`. **Never** write an unconditional `drop table + create table`
  — it wipes data on every restart.
- SQLite quirks the runner imposes: one `add column if not exists` per `ALTER`; no
  `DROP TABLE ... CASCADE`; statements split on `;`, so **no `;` inside SQL comments**;
  `alter column` / `add constraint` are skipped on SQLite.
- Canonical schema lives in the create-if-not-exists definitions (e.g. `002`/`003`); later
  files are idempotent patches.

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

## Tests & lint

- `python -m pytest tests/test_app.py -q` and `ruff check app/ tests/`. Run both before finishing.
- Tests use a TestClient + temp SQLite; inject fakes (e.g. MinIO) via `app.dependency_overrides`.

## Key designs

- `docs/KNOWLEDGE_BASE_STORAGE_AND_BUILD_SPEC.md` (architecture + technical spec, reflects shipped code) — design rationale in `docs/KNOWLEDGE_BASE_STORAGE_AND_BUILD_DESIGN.md` + `docs/KNOWLEDGE_BASE_IMPLEMENTATION_PLAN.md`
- `docs/USER_TENANT_RBAC_DESIGN.md`
- API reference under `docs/api/`.
