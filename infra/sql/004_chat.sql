-- Chat sessions: a durable local copy of the ngent thread plus the ownership/product fields
-- ngent does not track (tenant, user, pin). The ngent store is single-node and unbacked, so it is
-- treated as a compute engine, not the source of truth -- session metadata is mirrored here for
-- reliable, tenant-scoped reads. The id equals the ngent threadId.
create table if not exists chat_sessions (
  id text primary key,
  tenant_id text not null references tenants(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  title text,
  knowledge_base_ids jsonb not null default '[]'::jsonb,
  agent_options jsonb not null default '{}'::jsonb,
  summary text,
  status text not null default 'active' check (status in ('active', 'archived')),
  is_pinned boolean not null default false,
  pinned_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_chat_sessions_tenant_user
  on chat_sessions (tenant_id, user_id, is_pinned desc, pinned_at desc, updated_at desc);

-- chat_messages was removed: turn-level conversation records now live in chat_turns (005), and
-- ngent owns the fine-grained event stream.
drop table if exists chat_messages;
