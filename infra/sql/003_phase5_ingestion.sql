create table if not exists documents (
  id text primary key,
  tenant_id text not null references tenants(id) on delete cascade,
  knowledge_base_id text not null references knowledge_bases(id) on delete cascade,
  file_name text not null,
  file_type text not null check (file_type in ('pdf', 'docx', 'pptx', 'xlsx', 'md', 'txt', 'html', 'csv', 'json')),
  mime_type text,
  storage_key text not null,
  storage_url text not null,
  file_size_bytes bigint not null,
  language text check (language in ('zh', 'en', 'mixed')),
  parse_status text not null check (parse_status in ('pending', 'processing', 'ready', 'failed')),
  index_status text not null check (index_status in ('pending', 'processing', 'ready', 'failed')),
  chunk_strategy text not null,
  chunk_strategy_version text not null,
  chunk_config jsonb not null default '{}'::jsonb,
  created_by text not null references users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_documents_kb_status
  on documents (knowledge_base_id, parse_status, index_status);

create table if not exists document_chunks (
  id text primary key,
  tenant_id text not null references tenants(id) on delete cascade,
  knowledge_base_id text not null references knowledge_bases(id) on delete cascade,
  document_id text not null references documents(id) on delete cascade,
  chunk_index integer not null,
  token_count integer,
  language text check (language in ('zh', 'en', 'mixed')),
  metadata jsonb not null default '{}'::jsonb,
  embedding_model text not null,
  created_at timestamptz not null default now(),
  unique (document_id, chunk_index)
);

create index if not exists idx_document_chunks_document
  on document_chunks (document_id, chunk_index);

alter table document_chunks
  drop column if exists text;

create table if not exists ingestion_jobs (
  id text primary key,
  tenant_id text not null references tenants(id) on delete cascade,
  document_id text not null references documents(id) on delete cascade,
  job_type text not null check (job_type in ('parse', 'embed', 'reindex')),
  status text not null check (status in ('pending', 'running', 'succeeded', 'failed', 'dead_letter')),
  attempts integer not null default 0,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_ingestion_jobs_status
  on ingestion_jobs (status, updated_at);

create table if not exists upload_sessions (
  id text primary key,
  tenant_id text not null references tenants(id) on delete cascade,
  knowledge_base_id text not null references knowledge_bases(id) on delete cascade,
  actor_user_id text not null references users(id) on delete cascade,
  upload_mode text not null check (upload_mode in ('single_put', 'multipart')),
  file_name text not null,
  file_type text not null check (file_type in ('pdf', 'docx', 'pptx', 'xlsx', 'md', 'txt', 'html', 'csv', 'json')),
  content_type text,
  file_size_bytes bigint not null,
  object_key text not null unique,
  multipart_upload_id text,
  status text not null check (status in ('initiated', 'completed', 'aborted', 'expired', 'failed')),
  expires_at timestamptz not null,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_upload_sessions_tenant_status
  on upload_sessions (tenant_id, status, expires_at);

alter table upload_sessions
  add column if not exists upload_mode text;

alter table upload_sessions
  add column if not exists multipart_upload_id text;

update upload_sessions
set upload_mode = coalesce(upload_mode, 'single_put')
where upload_mode is null;

alter table upload_sessions
  alter column upload_mode set default 'single_put';

alter table upload_sessions
  alter column upload_mode set not null;

do $$
begin
  if exists (
    select 1
    from pg_constraint
    where conname = 'upload_sessions_status_check'
  ) then
    alter table upload_sessions drop constraint upload_sessions_status_check;
  end if;
end
$$;

alter table upload_sessions
  add constraint upload_sessions_status_check
  check (status in ('initiated', 'completed', 'aborted', 'expired', 'failed'));
