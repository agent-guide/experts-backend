create table if not exists knowledge_bases (
  id text primary key,
  tenant_id text not null references tenants(id) on delete cascade,
  owner_user_id text references users(id) on delete set null,
  name text not null,
  description text,
  scope text not null check (scope in ('personal', 'official')),
  visibility text not null check (visibility in ('private', 'tenant_public', 'official_public')),
  status text not null check (status in ('active', 'archived')),
  default_chunk_strategy text not null,
  default_chunk_config jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_knowledge_bases_tenant_status
  on knowledge_bases (tenant_id, status, visibility);

create index if not exists idx_knowledge_bases_owner_status
  on knowledge_bases (owner_user_id, status);
