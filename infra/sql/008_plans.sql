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

delete from plans
where id in ('plan_free', 'plan_pro', 'plan_max', 'plan_business')
  and not exists (
    select 1 from subscriptions s where s.plan_id = plans.id
  );

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
    'plan_default',
    'default',
    '默认套餐',
    1,
    '系统默认套餐，包含默认专家和基础使用额度。',
    '默认套餐',
    '基础默认能力',
    '默认',
    '["默认专家访问", "基础问答额度"]'::jsonb,
    '{"fromPlanIds": [], "toPlanIds": [], "rules": ["默认开通"], "selfServiceEnabled": false}'::jsonb,
    '[{"id": "plan_price_default_free_cny", "planId": "plan_default", "billingPeriod": "free", "currency": "CNY", "amountCents": 0, "discountLabel": null, "isEnabled": true}]'::jsonb,
    '{"id": "plan_entitlement_default", "planId": "plan_default", "monthlyQuestionLimit": 100, "monthlyTokenLimit": 100000, "seatLimit": 1, "singleTurnTokenLimit": null, "modelTiers": ["core"], "features": {"teamManagement": false, "apiAccess": false, "privateDeployment": false}}'::jsonb,
    '["expert_default"]'::jsonb,
    'active',
    true,
    10
  )
on conflict (code) do nothing;
