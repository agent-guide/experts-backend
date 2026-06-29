-- Expert plan configuration and subscriptions.
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
  prices jsonb not null default '[]'::jsonb,
  entitlements jsonb,
  expert_ids jsonb not null default '[]'::jsonb,
  status text not null default 'active' check (status in ('active', 'disabled')),
  is_recommended boolean not null default false,
  sort_order integer not null default 0 check (sort_order >= 0 and sort_order <= 9999),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists subscriptions (
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

create index if not exists idx_plans_status_sort
  on plans (status, sort_order, level);

create index if not exists idx_subscriptions_tenant_status
  on subscriptions (tenant_id, status, current_period_start desc);

alter table plans add column if not exists type_label text;
alter table plans add column if not exists subtitle text;
alter table plans add column if not exists badge_label text;
alter table plans add column if not exists highlight_items jsonb not null default '[]'::jsonb;
alter table plans add column if not exists upgrade_rules jsonb not null default '{}'::jsonb;
alter table plans add column if not exists prices jsonb not null default '[]'::jsonb;
alter table plans add column if not exists entitlements jsonb;
alter table plans add column if not exists expert_ids jsonb not null default '[]'::jsonb;

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
  prices,
  entitlements,
  expert_ids,
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
    '[{"id": "plan_price_free_free_cny", "planId": "plan_free", "billingPeriod": "free", "currency": "CNY", "amountCents": 0, "discountLabel": null, "isEnabled": true}]'::jsonb,
    '{"id": "plan_entitlement_free", "planId": "plan_free", "monthlyQuestionLimit": 100, "monthlyTokenLimit": 100000, "seatLimit": 1, "singleTurnTokenLimit": null, "modelTiers": ["core"], "features": {"teamManagement": false, "apiAccess": false, "privateDeployment": false}}'::jsonb,
    '[]'::jsonb,
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
    '[{"id": "plan_price_pro_monthly_cny", "planId": "plan_pro", "billingPeriod": "monthly", "currency": "CNY", "amountCents": 9900, "discountLabel": null, "isEnabled": true}, {"id": "plan_price_pro_yearly_cny", "planId": "plan_pro", "billingPeriod": "yearly", "currency": "CNY", "amountCents": 99900, "discountLabel": "年付优惠", "isEnabled": true}]'::jsonb,
    '{"id": "plan_entitlement_pro", "planId": "plan_pro", "monthlyQuestionLimit": 1000, "monthlyTokenLimit": 2000000, "seatLimit": 1, "singleTurnTokenLimit": null, "modelTiers": ["core", "enhanced"], "features": {"teamManagement": false, "apiAccess": false, "privateDeployment": false}}'::jsonb,
    '[]'::jsonb,
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
    '[{"id": "plan_price_max_monthly_cny", "planId": "plan_max", "billingPeriod": "monthly", "currency": "CNY", "amountCents": 29900, "discountLabel": null, "isEnabled": true}, {"id": "plan_price_max_yearly_cny", "planId": "plan_max", "billingPeriod": "yearly", "currency": "CNY", "amountCents": 299900, "discountLabel": "年付优惠", "isEnabled": true}]'::jsonb,
    '{"id": "plan_entitlement_max", "planId": "plan_max", "monthlyQuestionLimit": 5000, "monthlyTokenLimit": 10000000, "seatLimit": 1, "singleTurnTokenLimit": null, "modelTiers": ["core", "enhanced", "advanced"], "features": {"teamManagement": true, "apiAccess": true, "privateDeployment": false}}'::jsonb,
    '[]'::jsonb,
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
    '[{"id": "plan_price_business_sales_cny", "planId": "plan_business", "billingPeriod": "sales", "currency": "CNY", "amountCents": 0, "discountLabel": "联系销售", "isEnabled": true}]'::jsonb,
    '{"id": "plan_entitlement_business", "planId": "plan_business", "monthlyQuestionLimit": 50000, "monthlyTokenLimit": 100000000, "seatLimit": 5, "singleTurnTokenLimit": null, "modelTiers": ["core", "enhanced", "advanced"], "features": {"teamManagement": true, "apiAccess": true, "privateDeployment": true}}'::jsonb,
    '[]'::jsonb,
    'active',
    false,
    40
  )
on conflict (code) do nothing;
