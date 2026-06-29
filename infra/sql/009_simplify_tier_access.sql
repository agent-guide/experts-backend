-- Remove obsolete normalized plan tables after flattening plan configuration into plans JSON.
drop table if exists tenant_subscriptions;
drop table if exists subscription_entitlement_snapshots;
drop table if exists plan_experts;
drop table if exists plan_expert_groups;
drop table if exists expert_group_members;
drop table if exists expert_groups;
drop table if exists plan_entitlements;
drop table if exists plan_prices;
