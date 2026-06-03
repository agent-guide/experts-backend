alter table chat_tasks
  add column if not exists priority text not null default 'low'
  check (priority in ('high', 'low'));

create index if not exists idx_chat_tasks_priority_status_created
  on chat_tasks (priority, status, created_at asc);
