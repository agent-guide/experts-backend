-- Chat turns: a durable local copy of one ngent turn (the question, the assembled answer, and the
-- terminal status). Mirrors the ngent turn-history shape (requestText/responseText/status/
-- stopReason/...). The ngent store is single-node and unbacked, so the conversational record is
-- persisted here and read back locally. The id equals the ngent turnId (captured from the
-- turn_started stream event).
create table if not exists chat_turns (
  id text primary key,
  session_id text not null references chat_sessions(id) on delete cascade,
  tenant_id text not null references tenants(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  request_text text not null,
  response_text text,
  model text,
  knowledge_base_ids jsonb not null default '[]'::jsonb,
  query_rewrite boolean not null default false,
  multi_hop_config jsonb,
  status text not null check (status in ('running', 'completed', 'failed', 'cancelled')),
  stop_reason text,
  error_message text,
  is_internal boolean not null default false,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists idx_chat_turns_session_created
  on chat_turns (session_id, created_at asc);

create index if not exists idx_chat_turns_tenant_user
  on chat_turns (tenant_id, user_id, created_at desc);

-- chat_tasks/chat_task_events were replaced by chat_turns. The per-event log table will be
-- reintroduced only if exact replay/audit is later required (the current design keeps just the
-- assembled turn record).
drop table if exists chat_task_events;
drop table if exists chat_tasks;
