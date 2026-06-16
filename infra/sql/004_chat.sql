-- Chat sessions: a durable local copy of the upstream thread plus the ownership/product fields
-- the compute engine does not track (tenant, user, pin). The engine (ngent or the agent-gateway
-- ACP backend) is treated as compute, not the source of truth -- session metadata is mirrored
-- here for reliable, tenant-scoped reads. The id equals the upstream threadId (ngent) or a
-- caller-generated thread id (ACP). acp_session_id holds the agent-assigned ACP session id
-- (surfaced by the first turn via a `session` event) so follow-up turns resume the same instance.
create table if not exists chat_sessions (
  id text primary key,
  tenant_id text not null references tenants(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  title text,
  knowledge_base_ids jsonb not null default '[]'::jsonb,
  agent_options jsonb not null default '{}'::jsonb,
  acp_session_id text,
  summary text,
  status text not null default 'active' check (status in ('active', 'archived')),
  is_pinned boolean not null default false,
  pinned_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create index if not exists idx_chat_sessions_tenant_user
  on chat_sessions (tenant_id, user_id, is_pinned desc, pinned_at desc, updated_at desc);

-- Preserve deployments whose chat_sessions predates these columns (the create table above is a
-- no-op once the table exists, so new columns are backfilled here).
alter table chat_sessions add column if not exists agent_options jsonb not null default '{}'::jsonb;
alter table chat_sessions add column if not exists summary text;
alter table chat_sessions add column if not exists acp_session_id text;
alter table chat_sessions add column if not exists deleted_at timestamptz;

-- chat_messages was removed: turn-level conversation records now live in chat_turns (005), and
-- ngent owns the fine-grained event stream.
drop table if exists chat_messages;
