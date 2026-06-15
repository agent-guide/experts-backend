-- Experts are platform-authored capability bundles. They can combine one category,
-- multiple skills, multiple knowledge bases, and optional prompt guide questions.
create table if not exists expert_categories (
  id text primary key,
  name text not null unique,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists experts (
  id text primary key,
  category_id text not null references expert_categories(id) on delete restrict,
  name text not null,
  ability_intro text not null,
  tags jsonb not null default '[]'::jsonb,
  status text not null default 'draft' check (status in ('published', 'draft', 'unlisted')),
  guide_questions jsonb not null default '[]'::jsonb,
  summon_button_text text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists expert_skills (
  id text primary key,
  expert_id text not null references experts(id) on delete cascade,
  skill_id text not null references skills(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (expert_id, skill_id)
);

create table if not exists expert_knowledge_bases (
  id text primary key,
  expert_id text not null references experts(id) on delete cascade,
  knowledge_base_id text not null references knowledge_bases(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (expert_id, knowledge_base_id)
);

create index if not exists idx_experts_category_status
  on experts (category_id, status);

create index if not exists idx_experts_status_created
  on experts (status, created_at desc);

create index if not exists idx_expert_skills_skill
  on expert_skills (skill_id);

create index if not exists idx_expert_knowledge_bases_kb
  on expert_knowledge_bases (knowledge_base_id);
