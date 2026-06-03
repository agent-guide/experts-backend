create table if not exists skills (
  id text primary key,
  slug text not null unique,
  name text not null,
  description text not null,
  version text,
  allowed_tools jsonb not null default '[]'::jsonb,
  file_paths jsonb not null default '[]'::jsonb,
  tags jsonb not null default '[]'::jsonb,
  storage_uri text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_skills_created_at
  on skills (created_at desc);
