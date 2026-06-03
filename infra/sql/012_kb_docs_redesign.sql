-- 012_kb_docs_redesign.sql
-- Knowledge base documents and uploads redesign -- legacy cleanup.
-- See docs/KNOWLEDGE_BASE_STORAGE_AND_BUILD_DESIGN.md.
--
-- The canonical (final) schema now lives in 002 (knowledge_bases) and 003 (documents,
-- upload_sessions): no tenant_id, MinIO direct-upload shape, deferred build columns. The
-- migration runner re-runs every file on each boot with no applied-migrations table, so an
-- unconditional drop/recreate would wipe data on restart. Instead this file idempotently
-- reshapes databases that were created with the OLD shape. On a fresh database every step
-- here is a no-op (the columns/indexes either already match or never existed).
--
-- No backward compatibility for the dropped columns: legacy chunk/storage_url metadata and the
-- tenant_id linkage are removed outright. Local dev databases created before this change can
-- simply be deleted and re-migrated.
--
-- Portability note: app/db.py splits statements on the terminator, recognizes only one
-- "add column if not exists" per ALTER, and does not support DROP ... CASCADE on SQLite.
-- So: one ALTER per column, no CASCADE, and no terminator characters inside comments.

-- 1. knowledge_bases: reduce to the minimal platform-owned shape.
-- Drop the legacy tenant linkage and its indexes, the vestigial chunk defaults, the
-- scope/visibility access fields (access is permission-based now), and all build-control
-- columns (build is deferred, and a single status answers whether the base is usable). metadata
-- is retained as part of the final shape, so its add-if-not-exists is a no-op on fresh DBs.
drop index if exists idx_knowledge_bases_tenant_status;

drop index if exists idx_knowledge_bases_scope_visibility;

alter table knowledge_bases
  drop column if exists tenant_id;

alter table knowledge_bases
  drop column if exists default_chunk_strategy;

alter table knowledge_bases
  drop column if exists default_chunk_config;

alter table knowledge_bases
  drop column if exists scope;

alter table knowledge_bases
  drop column if exists visibility;

alter table knowledge_bases
  drop column if exists build_provider;

alter table knowledge_bases
  drop column if exists build_status;

alter table knowledge_bases
  drop column if exists active_build_id;

alter table knowledge_bases
  drop column if exists last_built_at;

alter table knowledge_bases
  add column if not exists metadata jsonb not null default '{}'::jsonb;

-- Soft-delete marker. delete is a soft delete so the documents/upload_sessions cascade does not
-- strand MinIO objects -- GC reclaims the objects and then hard-deletes the rows. No-op on fresh
-- DBs (002 already declares the column).
alter table knowledge_bases
  add column if not exists deleted_at timestamptz;

-- 2. documents: drop tenant linkage and chunk/storage_url metadata, add MinIO-upload columns.
alter table documents
  drop column if exists tenant_id;

alter table documents
  drop column if exists storage_url;

alter table documents
  drop column if exists chunk_strategy;

alter table documents
  drop column if exists chunk_strategy_version;

alter table documents
  drop column if exists chunk_config;

alter table documents
  add column if not exists object_bucket text;

alter table documents
  add column if not exists object_version text;

alter table documents
  add column if not exists content_hash text;

alter table documents
  add column if not exists deleted_at timestamptz;

alter table documents
  add column if not exists metadata jsonb not null default '{}'::jsonb;

-- 3. upload_sessions: drop tenant linkage, add document_id and object_bucket.
alter table upload_sessions
  drop column if exists tenant_id;

alter table upload_sessions
  add column if not exists document_id text;

alter table upload_sessions
  add column if not exists object_bucket text;

-- 4. Drop the legacy ingestion model outright. document_chunks and ingestion_jobs are unused by
-- the control plane and superseded by the build/provider model. No backward compatibility: the
-- tables and any data they hold are removed. Dropped in FK order (children before parents).
drop table if exists document_chunks;

drop table if exists ingestion_jobs;
