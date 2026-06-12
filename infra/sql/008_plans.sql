-- Expert plan configuration, expert authorization groups, tenant subscriptions, and snapshots.
create table if not exists plans (
  id text primary key,
  code text not null unique,
  name text not null,
  level integer not null unique check (level >= 1 and level <= 99),
  description text not null,
  type_label text,
  subtitle text,
  badge_label text,
  highlight_items jsonb not null default '[]'::jsonb,
  upgrade_rules jsonb not null default '{}'::jsonb,
  status text not null default 'active' check (status in ('active', 'disabled')),
  is_recommended boolean not null default false,
  sort_order integer not null default 0 check (sort_order >= 0 and sort_order <= 9999),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists plan_prices (
  id text primary key,
  plan_id text not null references plans(id) on delete cascade,
  billing_period text not null check (billing_period in ('free', 'monthly', 'yearly', 'sales')),
  currency text not null,
  amount_cents integer not null check (amount_cents >= 0),
  discount_label text,
  is_enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (plan_id, billing_period, currency)
);

create table if not exists plan_entitlements (
  id text primary key,
  plan_id text not null unique references plans(id) on delete cascade,
  monthly_question_limit integer not null check (monthly_question_limit >= 0),
  monthly_token_limit integer not null check (monthly_token_limit >= 0),
  seat_limit integer not null check (seat_limit >= 1),
  single_turn_token_limit integer check (
    single_turn_token_limit is null or single_turn_token_limit >= 0
  ),
  model_tiers jsonb not null default '[]'::jsonb,
  features jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists expert_groups (
  id text primary key,
  code text not null unique,
  name text not null,
  description text,
  sort_order integer not null default 0 check (sort_order >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists expert_group_members (
  id text primary key,
  group_id text not null references expert_groups(id) on delete cascade,
  expert_id text not null references experts(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (group_id, expert_id)
);

create table if not exists plan_expert_groups (
  id text primary key,
  plan_id text not null references plans(id) on delete cascade,
  group_id text not null references expert_groups(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (plan_id, group_id)
);

create table if not exists tenant_subscriptions (
  id text primary key,
  tenant_id text not null references tenants(id) on delete cascade,
  plan_id text not null references plans(id) on delete restrict,
  status text not null check (status in ('active', 'trialing', 'past_due', 'cancelled', 'expired')),
  billing_period text not null check (billing_period in ('free', 'monthly', 'yearly', 'sales')),
  current_period_start timestamptz not null,
  current_period_end timestamptz,
  cancel_at_period_end boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists subscription_entitlement_snapshots (
  id text primary key,
  subscription_id text not null references tenant_subscriptions(id) on delete cascade,
  plan_code text not null,
  plan_name text not null,
  billing_period text not null check (billing_period in ('free', 'monthly', 'yearly', 'sales')),
  price_snapshot jsonb not null default '{}'::jsonb,
  entitlements_snapshot jsonb not null default '{}'::jsonb,
  starts_at timestamptz not null,
  ends_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists idx_plans_status_sort
  on plans (status, sort_order, level);

create index if not exists idx_plan_prices_plan
  on plan_prices (plan_id, billing_period, is_enabled);

create index if not exists idx_expert_group_members_expert
  on expert_group_members (expert_id);

create index if not exists idx_plan_expert_groups_group
  on plan_expert_groups (group_id);

create index if not exists idx_tenant_subscriptions_tenant_status
  on tenant_subscriptions (tenant_id, status, current_period_start desc);

create index if not exists idx_subscription_snapshots_subscription
  on subscription_entitlement_snapshots (subscription_id, starts_at desc);

alter table plans add column if not exists type_label text;
alter table plans add column if not exists subtitle text;
alter table plans add column if not exists badge_label text;
alter table plans add column if not exists highlight_items jsonb not null default '[]'::jsonb;
alter table plans add column if not exists upgrade_rules jsonb not null default '{}'::jsonb;

alter table plans drop constraint if exists plans_level_check;
alter table plans add constraint plans_level_check check (level >= 1 and level <= 99);
alter table plans drop constraint if exists plans_sort_order_check;
alter table plans add constraint plans_sort_order_check check (sort_order >= 0 and sort_order <= 9999);

insert into plans (
  id,
  code,
  name,
  level,
  description,
  type_label,
  subtitle,
  badge_label,
  highlight_items,
  upgrade_rules,
  status,
  is_recommended,
  sort_order
)
values
  (
    'plan_free',
    'free',
    '免费版',
    1,
    '入门级运营助手，适合首次体验专家问答能力。',
    '免费版',
    '入门级运营助手',
    '入门体验',
    '["基础专家问答", "基础体验权限", "轻量运营辅助"]'::jsonb,
    '{"fromPlanIds": [], "toPlanIds": ["plan_pro", "plan_max", "plan_business"], "rules": ["立即生效"], "selfServiceEnabled": true}'::jsonb,
    'active',
    false,
    10
  ),
  (
    'plan_pro',
    'pro',
    '专业版',
    2,
    '进阶级效率专家，解锁更多专业专家和更高月度额度。',
    '个人付费',
    '进阶级效率专家',
    '最受欢迎',
    '["深度评论拆解", "精准申诉顾问", "地道客服话术", "高频使用权限"]'::jsonb,
    '{"fromPlanIds": ["plan_free"], "toPlanIds": ["plan_max", "plan_business"], "rules": ["立即生效", "按差价补款"], "selfServiceEnabled": true}'::jsonb,
    'active',
    true,
    20
  ),
  (
    'plan_max',
    'max',
    'Max 版',
    3,
    '战略级决策顾问，支持高级专家、更强模型和更高使用额度。',
    '个人付费',
    '战略级决策顾问',
    '高频决策',
    '["高级专家访问", "高频问答额度", "高级模型能力", "复杂任务处理"]'::jsonb,
    '{"fromPlanIds": ["plan_free", "plan_pro"], "toPlanIds": ["plan_business"], "rules": ["立即生效", "按差价补款"], "selfServiceEnabled": true}'::jsonb,
    'active',
    false,
    30
  ),
  (
    'plan_business',
    'business',
    'Business 版',
    4,
    '团队协作与企业级能力，适合多人席位和组织管理。',
    '团队',
    '团队协作与企业级能力',
    '团队协作',
    '["多人席位", "团队协作", "企业定制专家", "组织级管理"]'::jsonb,
    '{"fromPlanIds": ["plan_free", "plan_pro", "plan_max"], "toPlanIds": [], "rules": ["联系销售"], "selfServiceEnabled": false}'::jsonb,
    'active',
    false,
    40
  )
on conflict (code) do nothing;

update plans
set name = '免费版',
    description = '入门级运营助手，适合首次体验专家问答能力。',
    type_label = '免费版',
    subtitle = '入门级运营助手',
    badge_label = '入门体验',
    highlight_items = '["基础专家问答", "基础体验权限", "轻量运营辅助"]'::jsonb,
    upgrade_rules = '{"fromPlanIds": [], "toPlanIds": ["plan_pro", "plan_max", "plan_business"], "rules": ["立即生效"], "selfServiceEnabled": true}'::jsonb,
    updated_at = CURRENT_TIMESTAMP
where id = 'plan_free';

update plans
set name = '专业版',
    description = '进阶级效率专家，解锁更多专业专家和更高月度额度。',
    type_label = '个人付费',
    subtitle = '进阶级效率专家',
    badge_label = '最受欢迎',
    highlight_items = '["深度评论拆解", "精准申诉顾问", "地道客服话术", "高频使用权限"]'::jsonb,
    upgrade_rules = '{"fromPlanIds": ["plan_free"], "toPlanIds": ["plan_max", "plan_business"], "rules": ["立即生效", "按差价补款"], "selfServiceEnabled": true}'::jsonb,
    updated_at = CURRENT_TIMESTAMP
where id = 'plan_pro';

update plans
set name = 'Max 版',
    description = '战略级决策顾问，支持高级专家、更强模型和更高使用额度。',
    type_label = '个人付费',
    subtitle = '战略级决策顾问',
    badge_label = '高频决策',
    highlight_items = '["高级专家访问", "高频问答额度", "高级模型能力", "复杂任务处理"]'::jsonb,
    upgrade_rules = '{"fromPlanIds": ["plan_free", "plan_pro"], "toPlanIds": ["plan_business"], "rules": ["立即生效", "按差价补款"], "selfServiceEnabled": true}'::jsonb,
    updated_at = CURRENT_TIMESTAMP
where id = 'plan_max';

update plans
set name = 'Business 版',
    description = '团队协作与企业级能力，适合多人席位和组织管理。',
    type_label = '团队',
    subtitle = '团队协作与企业级能力',
    badge_label = '团队协作',
    highlight_items = '["多人席位", "团队协作", "企业定制专家", "组织级管理"]'::jsonb,
    upgrade_rules = '{"fromPlanIds": ["plan_free", "plan_pro", "plan_max"], "toPlanIds": [], "rules": ["联系销售"], "selfServiceEnabled": false}'::jsonb,
    updated_at = CURRENT_TIMESTAMP
where id = 'plan_business';

insert into plan_prices (id, plan_id, billing_period, currency, amount_cents, discount_label, is_enabled)
values
  ('plan_price_free_free_cny', 'plan_free', 'free', 'CNY', 0, null, true),
  ('plan_price_pro_monthly_cny', 'plan_pro', 'monthly', 'CNY', 9900, null, true),
  ('plan_price_pro_yearly_cny', 'plan_pro', 'yearly', 'CNY', 99900, '年付优惠', true),
  ('plan_price_max_monthly_cny', 'plan_max', 'monthly', 'CNY', 29900, null, true),
  ('plan_price_max_yearly_cny', 'plan_max', 'yearly', 'CNY', 299900, '年付优惠', true),
  ('plan_price_business_sales_cny', 'plan_business', 'sales', 'CNY', 0, '联系销售', true)
on conflict (plan_id, billing_period, currency) do nothing;

update plan_prices
set discount_label = '年付优惠',
    updated_at = CURRENT_TIMESTAMP
where id in ('plan_price_pro_yearly_cny', 'plan_price_max_yearly_cny');

update plan_prices
set discount_label = '联系销售',
    updated_at = CURRENT_TIMESTAMP
where id = 'plan_price_business_sales_cny';

insert into plan_entitlements (
  id,
  plan_id,
  monthly_question_limit,
  monthly_token_limit,
  seat_limit,
  single_turn_token_limit,
  model_tiers,
  features
)
values
  (
    'plan_entitlement_free',
    'plan_free',
    100,
    100000,
    1,
    null,
    '["core"]'::jsonb,
    '{"teamManagement": false, "apiAccess": false, "privateDeployment": false}'::jsonb
  ),
  (
    'plan_entitlement_pro',
    'plan_pro',
    1000,
    2000000,
    1,
    null,
    '["core", "enhanced"]'::jsonb,
    '{"teamManagement": false, "apiAccess": false, "privateDeployment": false}'::jsonb
  ),
  (
    'plan_entitlement_max',
    'plan_max',
    5000,
    10000000,
    1,
    null,
    '["core", "enhanced", "advanced"]'::jsonb,
    '{"teamManagement": true, "apiAccess": true, "privateDeployment": false}'::jsonb
  ),
  (
    'plan_entitlement_business',
    'plan_business',
    50000,
    100000000,
    5,
    null,
    '["core", "enhanced", "advanced"]'::jsonb,
    '{"teamManagement": true, "apiAccess": true, "privateDeployment": true}'::jsonb
  )
on conflict (plan_id) do nothing;

insert into expert_groups (id, code, name, description, sort_order)
values
  ('expert_group_basic', 'basic', '基础专家组', 'Free 版及以上可访问', 10),
  ('expert_group_professional', 'professional', '专业专家组', 'Pro 版及以上可访问', 20),
  ('expert_group_advanced', 'advanced', '高级专家组', 'Max 版及以上可访问', 30),
  (
    'expert_group_enterprise_custom',
    'enterprise_custom',
    '企业定制专家组',
    'Business 版专属访问',
    40
  )
on conflict (code) do nothing;

update expert_groups
set name = '基础专家组',
    description = 'Free 版及以上可访问',
    updated_at = CURRENT_TIMESTAMP
where id = 'expert_group_basic';

update expert_groups
set name = '专业专家组',
    description = 'Pro 版及以上可访问',
    updated_at = CURRENT_TIMESTAMP
where id = 'expert_group_professional';

update expert_groups
set name = '高级专家组',
    description = 'Max 版及以上可访问',
    updated_at = CURRENT_TIMESTAMP
where id = 'expert_group_advanced';

update expert_groups
set name = '企业定制专家组',
    description = 'Business 版专属访问',
    updated_at = CURRENT_TIMESTAMP
where id = 'expert_group_enterprise_custom';

insert into plan_expert_groups (id, plan_id, group_id)
values
  ('plan_expert_group_free_basic', 'plan_free', 'expert_group_basic'),
  ('plan_expert_group_pro_basic', 'plan_pro', 'expert_group_basic'),
  ('plan_expert_group_pro_professional', 'plan_pro', 'expert_group_professional'),
  ('plan_expert_group_max_basic', 'plan_max', 'expert_group_basic'),
  ('plan_expert_group_max_professional', 'plan_max', 'expert_group_professional'),
  ('plan_expert_group_max_advanced', 'plan_max', 'expert_group_advanced'),
  ('plan_expert_group_business_basic', 'plan_business', 'expert_group_basic'),
  ('plan_expert_group_business_professional', 'plan_business', 'expert_group_professional'),
  ('plan_expert_group_business_advanced', 'plan_business', 'expert_group_advanced'),
  (
    'plan_expert_group_business_enterprise_custom',
    'plan_business',
    'expert_group_enterprise_custom'
  )
on conflict (plan_id, group_id) do nothing;
