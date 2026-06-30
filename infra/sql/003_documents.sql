-- Documents and upload sessions. Like knowledge_bases, these are platform-authored and carry
-- NO tenant_id (tenants never own/operate documents).
--
-- Chunking is decided at build time, so there are no chunk_strategy columns. Only storage_key
-- (plus object_bucket) locates the MinIO object. object_bucket comes from settings.minio_bucket
-- today but is persisted not null so historical objects stay locatable if the bucket changes.
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

-- Support knowledge-base document list sorted by created_at.
create index if not exists idx_documents_kb_created
  on documents (knowledge_base_id, created_at desc);

-- document_upload_sessions tracks a MinIO direct-upload handshake for knowledge-base documents.
-- document_id is allocated at upload-url time (the object key depends on it) but the documents row
-- is only inserted at complete-upload, so document_id is plain text, not a foreign key.
create table if not exists document_upload_sessions (
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

create index if not exists idx_document_upload_sessions_status
  on document_upload_sessions (status, expires_at);

create index if not exists idx_document_upload_sessions_document
  on document_upload_sessions (document_id);

-- Legacy name cleanup. Upload sessions are ephemeral handshake records (short TTL, GC'd), so the
-- old table is dropped rather than data-migrated after the rename to document_upload_sessions.
drop table if exists upload_sessions;
