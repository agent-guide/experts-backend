alter table chat_sessions
  add column if not exists is_pinned boolean not null default false;

alter table chat_sessions
  add column if not exists pinned_at timestamptz;

drop index if exists idx_chat_sessions_tenant_user;

create index if not exists idx_chat_sessions_tenant_user
  on chat_sessions (tenant_id, user_id, is_pinned desc, pinned_at desc, updated_at desc);
