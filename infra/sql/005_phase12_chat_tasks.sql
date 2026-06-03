create table if not exists chat_tasks (
  id text primary key,
  tenant_id text not null references tenants(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  session_id text not null references chat_sessions(id) on delete cascade,
  question text not null,
  knowledge_base_ids jsonb not null default '[]'::jsonb,
  llm_model text,
  query_rewrite boolean not null default false,
  status text not null check (status in ('queued', 'running', 'cancel_requested', 'succeeded', 'failed', 'cancelled')),
  error_message text,
  active_subscriber_id text,
  active_subscribed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);

create index if not exists idx_chat_tasks_status_created
  on chat_tasks (status, created_at asc);

create index if not exists idx_chat_tasks_tenant_user
  on chat_tasks (tenant_id, user_id, created_at desc);

create table if not exists chat_task_events (
  id text primary key,
  task_id text not null references chat_tasks(id) on delete cascade,
  tenant_id text not null references tenants(id) on delete cascade,
  event_type text not null check (event_type in ('queued', 'picked', 'retrieval', 'stop', 'error', 'cancel_requested', 'cancelled')),
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_chat_task_events_task_created
  on chat_task_events (task_id, created_at asc);
