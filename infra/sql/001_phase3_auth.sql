create table if not exists users (
  id text primary key,
  email text not null unique,
  password_hash text not null,
  name text not null,
  status text not null check (status in ('pending_activation', 'active', 'disabled')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists tenants (
  id text primary key,
  type text not null default 'personal' check (type in ('personal', 'team')),
  name text not null,
  slug text not null unique,
  owner_user_id text references users(id) on delete set null,
  status text not null check (status in ('active', 'disabled')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists tenant_members (
  id text primary key,
  tenant_id text not null references tenants(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  role text not null check (role in ('admin', 'member')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, user_id)
);

create table if not exists platform_user_roles (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  role text not null check (role in ('admin', 'expert', 'operator')),
  assigned_by text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (user_id, role)
);

create table if not exists refresh_tokens (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  token_hash text not null,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists platform_activation_tokens (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  token_hash text not null unique,
  expires_at timestamptz not null,
  used_at timestamptz,
  created_at timestamptz not null default now()
);
