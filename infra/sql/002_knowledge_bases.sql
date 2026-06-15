-- Knowledge bases are platform-authored resources. They have NO tenant_id: tenants never
-- own or operate knowledge bases / documents / skills (see USER_TENANT_RBAC_DESIGN.md and
-- KNOWLEDGE_BASE_STORAGE_AND_BUILD_DESIGN.md section 10). Tenants only consume them via chat.
--
-- Deliberately minimal. There is no scope/visibility -- all knowledge bases are platform-owned,
-- access is governed by platform permissions, and any sharing rules belong in a dedicated table
-- rather than here. There is no build_provider/build_status/active_build_id either -- build is
-- deferred and a single status answers whether the knowledge base is usable. owner_user_id is
-- creator attribution only, not an access-control input.
create table if not exists knowledge_bases (
  id text primary key,
  owner_user_id text references users(id) on delete set null,
  name text not null,
  description text,
  status text not null default 'active' check (status in ('active', 'archived')),
  -- Soft delete. delete is a soft delete (set deleted_at) rather than a hard row delete: the
  -- documents/upload_sessions children cascade on a hard delete, which would drop their rows
  -- and strand the MinIO objects (no storage_key left to reclaim by). GC
  -- (purge_deleted_knowledge_bases) removes the objects first, then hard-deletes the rows.
  deleted_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_knowledge_bases_owner_status
  on knowledge_bases (owner_user_id, status);
