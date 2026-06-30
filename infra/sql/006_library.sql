-- User library files are personal user-owned files scoped to the active tenant.
-- MinIO/S3 stores bytes and this table owns metadata, ownership and soft deletion.
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
  deleted_at timestamptz,
  -- Chat temporary-file lifecycle (docs/LIBRARY_FILE_LIFECYCLE.md). A chat upload is a user-owned
  -- file with a shorter life. Promotion flips it to permanent with no byte copy.
  source text not null default 'library' check (source in ('library', 'chat_upload')),
  lifecycle text not null default 'permanent' check (lifecycle in ('temporary', 'permanent')),
  expires_at timestamptz,
  promoted_at timestamptz,
  chat_session_id text references chat_sessions(id) on delete set null,
  -- Cross-column lifecycle invariant (§3.4): a temporary file always has a deadline. Its
  -- chat_session_id is null while unbound and set once on first turn use (§5/§7). A permanent
  -- file never has an expiry, so the GC expires_at filter cannot catch it. Named so the
  -- existing-PostgreSQL DO block below can update it in place.
  constraint library_files_lifecycle_invariant check (
    (lifecycle = 'temporary' and expires_at is not null)
    or (lifecycle = 'permanent' and expires_at is null)
  )
);

create index if not exists idx_library_files_user_tenant_updated
  on library_files (user_id, tenant_id, updated_at desc)
  where deleted_at is null;

create index if not exists idx_library_files_user_tenant_type
  on library_files (user_id, tenant_id, file_type, updated_at desc)
  where deleted_at is null;

create unique index if not exists idx_library_files_storage_object_key
  on library_files (storage_object_key);

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
  file_size_bytes bigint not null,
  storage_bucket text not null,
  storage_object_key text not null unique,
  content_hash text,
  status text not null default 'initiated' check (status in ('initiated', 'completed', 'expired', 'failed')),
  expires_at timestamptz not null,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  -- Chat uploads carry their session context here and route complete-upload (§4). The
  -- on delete cascade is documentary only — chat sessions are soft-deleted, so it never fires.
  chat_session_id text references chat_sessions(id) on delete cascade
);

create index if not exists idx_library_upload_sessions_status
  on library_upload_sessions (status, expires_at);

create index if not exists idx_library_upload_sessions_file
  on library_upload_sessions (file_id);

-- Backfill lifecycle columns on databases whose library_files predates this design. The create
-- table above is a no-op once the table exists, so new columns are added here. Existing rows
-- default to source='library', lifecycle='permanent', expires_at=null -- already invariant-valid.
alter table library_files add column if not exists source text not null default 'library' check (source in ('library', 'chat_upload'));
alter table library_files add column if not exists lifecycle text not null default 'permanent' check (lifecycle in ('temporary', 'permanent'));
alter table library_files add column if not exists expires_at timestamptz;
alter table library_files add column if not exists promoted_at timestamptz;
alter table library_files add column if not exists chat_session_id text references chat_sessions(id) on delete set null;

alter table library_upload_sessions add column if not exists chat_session_id text references chat_sessions(id) on delete cascade;

-- Temporary-file lifecycle indexes (§3.2): expiry sweep and per-session listing.
create index if not exists idx_library_files_temporary_expiry
  on library_files (lifecycle, expires_at)
  where deleted_at is null;

create index if not exists idx_library_files_chat_session
  on library_files (chat_session_id, created_at desc)
  where deleted_at is null;

-- Land the cross-column lifecycle invariant on existing PostgreSQL tables (create table if not
-- exists never alters an existing table, and the runner skips bare ADD CONSTRAINT under SQLite).
-- _sqlite_compatible_sql strips this DO block, so SQLite relies on the canonical create-table
-- check plus app-layer re-validation (§3.4).
do $$
begin
  -- Drop-then-add so the definition is updated in place on existing PostgreSQL tables (the
  -- invariant was relaxed to allow unbound temporary files: chat_session_id may be null).
  alter table library_files drop constraint if exists library_files_lifecycle_invariant;
  alter table library_files add constraint library_files_lifecycle_invariant check (
    (lifecycle = 'temporary' and expires_at is not null)
    or (lifecycle = 'permanent' and expires_at is null)
  );
end $$;
