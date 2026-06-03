-- Indexes for auth/RBAC hot lookups.
create index if not exists idx_refresh_tokens_user_token
  on refresh_tokens (user_id, token_hash);

create index if not exists idx_tenant_members_user
  on tenant_members (user_id);

create index if not exists idx_platform_user_roles_user
  on platform_user_roles (user_id);
