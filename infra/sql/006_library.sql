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
  deleted_at timestamptz
);

create index if not exists idx_library_files_user_tenant_updated
  on library_files (user_id, tenant_id, updated_at desc)
  where deleted_at is null;

create index if not exists idx_library_files_user_tenant_type
  on library_files (user_id, tenant_id, file_type, updated_at desc)
  where deleted_at is null;

create unique index if not exists idx_library_files_storage_object_key
  on library_files (storage_object_key);
