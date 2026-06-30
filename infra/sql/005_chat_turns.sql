-- Chat turns: a durable local copy of one ACP turn (the question, the assembled reasoning,
-- answer, and the terminal status). The ACP data plane has no server turn id, so the id is
-- generated locally and emitted in the public turn_started stream event.
create table if not exists chat_turns (
  id text primary key,
  session_id text not null references chat_sessions(id) on delete cascade,
  tenant_id text not null references tenants(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  request_text text not null,
  reasoning_text text,
  response_text text,
  model text,
  query_rewrite boolean not null default false,
  multi_hop_config jsonb,
  status text not null check (status in ('running', 'completed', 'failed', 'cancelled')),
  stop_reason text,
  error_message text,
  is_internal boolean not null default false,
  -- Per-turn attachment provenance snapshot (§9). Denormalized, mandatory-on-write for turns that
  -- reference files, so history/audit survive the referenced library_files row being GC-removed.
  -- Each
  -- element: {fileId, name, mimeType, sizeBytes, lifecycle, attachedAt}.
  attachments jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

alter table chat_turns add column if not exists reasoning_text text;
alter table chat_turns add column if not exists attachments jsonb not null default '[]'::jsonb;

create index if not exists idx_chat_turns_session_created
  on chat_turns (session_id, created_at asc);

create index if not exists idx_chat_turns_tenant_user
  on chat_turns (tenant_id, user_id, created_at desc);

-- chat_tasks/chat_task_events were replaced by chat_turns. The per-event log table will be
-- reintroduced only if exact replay/audit is later required (the current design keeps just the
-- assembled turn record).
drop table if exists chat_task_events;
drop table if exists chat_tasks;
