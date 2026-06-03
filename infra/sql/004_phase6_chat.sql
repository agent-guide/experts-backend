create table if not exists chat_sessions (
  id text primary key,
  tenant_id text not null references tenants(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  title text,
  knowledge_base_ids jsonb not null default '[]'::jsonb,
  status text not null check (status in ('active', 'archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_chat_sessions_tenant_user
  on chat_sessions (tenant_id, user_id, updated_at desc);

create table if not exists chat_messages (
  id text primary key,
  tenant_id text not null references tenants(id) on delete cascade,
  session_id text not null references chat_sessions(id) on delete cascade,
  role text not null check (role in ('system', 'user', 'assistant')),
  content text not null,
  model text,
  citations jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_chat_messages_session_created
  on chat_messages (session_id, created_at asc);
