# Expert Plan Design

This document describes the current expert plan and subscription design in the backend.
For endpoint-level request and response examples, see `docs/api/plans.md` and
`docs/api/tenants.md`.

## Scope

The plan module provides:

- Admin plan configuration.
- User-side active plan catalog.
- Tenant current subscription lookup.
- Admin tenant subscription changes.
- Tenant subscription and monthly usage summaries.

The plan module does not currently provide:

- Payment provider integration.
- Order, invoice, or refund records.
- Prorated upgrade billing.
- Historical entitlement snapshots.
- Expert group based authorization.
- General chat runtime blocking for plan limits.

## Current Model

Plans define which experts, model tiers, quotas, prices, and product features a tenant can use.
The current implementation intentionally stores plan configuration in a flattened shape:

- `plans` stores display fields plus JSON configuration.
- `subscriptions` points to `plans`.
- A tenant subscription reads the current plan configuration live.

There are no separate `plan_prices`, `plan_entitlements`, `plan_experts`,
`expert_groups`, `plan_expert_groups`, or `subscription_entitlement_snapshots` tables.
Those earlier normalized tables are obsolete and are explicitly dropped by
`infra/sql/009_simplify_tier_access.sql`.

## Database Shape

### `plans`

`plans` is the canonical plan configuration table.

Important fields:

| Field | Purpose |
| --- | --- |
| `id` | Stable plan id, normally `plan_*`. |
| `code` | Backend-maintained unique system code. |
| `name` | User-facing plan name. |
| `level` | Unique tier order, `1` to `99`. Larger values represent higher tiers. |
| `description` | User-facing plan description. |
| `type_label` | Frontend-editable plan type label. |
| `subtitle` | Optional display subtitle. |
| `badge_label` | Optional display badge. |
| `highlight_items` | JSON list of display highlights. |
| `upgrade_rules` | JSON display/config object for allowed upgrade messaging. |
| `prices` | JSON list of price options. |
| `entitlements` | JSON entitlement object. |
| `expert_ids` | JSON list of directly accessible expert ids. |
| `status` | `active` or `disabled`. |
| `is_recommended` | Whether the plan is marked as recommended. |
| `sort_order` | Display order. |

The seeded default plan is:

- `id`: `plan_default`
- `code`: `default`
- `name`: `默认套餐`
- `expert_ids`: `["expert_default"]`
- `billingPeriod`: `free`
- `monthlyQuestionLimit`: `100`
- `monthlyTokenLimit`: `100000`
- `seatLimit`: `1`
- `modelTiers`: `["core"]`

The old seeded `plan_free`, `plan_pro`, `plan_max`, and `plan_business` rows are removed
when they have no subscription history. New deployments should not assume those four plans
exist unless an admin creates them.

### `subscriptions`

`subscriptions` stores tenant subscription records.

Important fields:

| Field | Purpose |
| --- | --- |
| `id` | Subscription id, normally `tenant_subscription_*`. |
| `tenant_id` | Tenant that owns the subscription. |
| `plan_id` | Plan used by the subscription. |
| `status` | `active`, `trialing`, `past_due`, `cancelled`, or `expired`. |
| `billing_period` | `free`, `monthly`, `yearly`, or `sales`. |
| `current_period_start` | Current period start timestamp. |
| `current_period_end` | Optional current period end timestamp. |
| `cancel_at_period_end` | Whether the subscription should stop renewing. |

The current subscription query selects the newest non-expired subscription whose status is
`active`, `trialing`, or `past_due`.

If a signed-in tenant has no current subscription, the backend creates an active `free`
subscription to the `default` plan on demand.

## Entitlements

Plan entitlements are stored as a JSON object on `plans.entitlements`.

Current fields:

| Field | Purpose |
| --- | --- |
| `monthlyQuestionLimit` | Monthly question quota. |
| `monthlyTokenLimit` | Monthly token quota. |
| `seatLimit` | Tenant seat quota. |
| `singleTurnTokenLimit` | Optional per-turn token limit. |
| `modelTiers` | Allowed model tier labels, such as `core` or `enhanced`. |
| `features` | Feature flags such as `teamManagement`, `apiAccess`, and `privateDeployment`. |

Tenant summaries expose these values as an `entitlementsSnapshot` field, but that is a
response-time snapshot built from the current plan configuration. It is not stored as a
separate historical entitlement snapshot.

## Expert Access

Plan expert access is direct:

- Admins replace the full list through `PUT /api/v1/plans/{plan_id}/experts`.
- The backend validates that every provided expert id exists.
- The list is stored as `plans.expert_ids`.

There is no current expert authorization group model. Expert categories are for market
organization and are not used as plan entitlement groups.

## Prices

Plan prices are stored as a JSON list on `plans.prices`.

Each price includes:

- `id`
- `planId`
- `billingPeriod`
- `currency`
- `amountCents`
- `discountLabel`
- `isEnabled`

Admin tenant subscription changes require the selected plan to have an enabled price for
the requested billing period. User-side plan market responses only include enabled prices.

## APIs

### Admin Plans

Base path: `/api/v1/plans`

Permissions:

- Read: `plan:read`
- Write: `plan:write`

Endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/plans` | List all plans, including disabled plans. |
| `POST /api/v1/plans` | Create a plan. |
| `GET /api/v1/plans/{plan_id}` | Get one plan. |
| `PATCH /api/v1/plans/{plan_id}` | Update plan display/config fields. |
| `PUT /api/v1/plans/{plan_id}/prices` | Replace all plan prices. |
| `PUT /api/v1/plans/{plan_id}/entitlements` | Replace plan entitlements. |
| `PUT /api/v1/plans/{plan_id}/experts` | Replace accessible expert ids. |
| `DELETE /api/v1/plans/{plan_id}` | Delete a plan if allowed. |

Rules:

- `code` is unique.
- `level` is unique.
- Only one plan is recommended at a time; setting one plan as recommended clears the flag on others.
- The `default` plan cannot be deleted.
- A plan with subscription history cannot be deleted.

### User Plan Market

Base path: `/api/v1/plan-market`

All endpoints require sign-in but no specific platform permission.

Endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/plan-market/plans` | List active plans with enabled prices. |
| `GET /api/v1/plan-market/current-subscription` | Get or create the active tenant's current subscription. |

### Tenant Subscription Administration

Admin tenant APIs expose subscription management as part of tenant operations.

`PATCH /api/v1/tenants/{tenant_id}/subscription`:

- Cancels current active/trialing/past-due subscriptions for the tenant.
- Inserts a new subscription for the selected plan and billing period.
- Requires the selected plan to have an enabled price for that billing period.
- Returns the hydrated tenant summary.

Tenant reads include:

- `currentSubscription`
- `currentPlan`
- `monthlyUsage`

Monthly question usage is currently counted from non-internal `chat_turns` created since the
start of the current month. Token usage is currently reported as `0`.

## Lifecycle

### New Tenant

When a tenant first asks for the current subscription and has no active subscription:

1. The backend loads the `default` plan.
2. It inserts an active `free` subscription.
3. It returns that subscription and the current `default` plan configuration.

### Plan Edit

When a plan is edited:

1. The row in `plans` is updated.
2. Current subscriptions continue pointing to the same `plan_id`.
3. Future reads use the updated plan configuration.

This is a live configuration model. It does not preserve historical plan entitlements per
subscription period.

### Plan Disable

Disabled plans:

- Are still visible in admin plan lists.
- Are hidden from the user-side plan market.
- Should not be used as new purchase targets by frontend flows.

Existing subscriptions that point to a disabled plan still resolve through the plan id.

### Plan Delete

Plan deletion is intentionally limited:

- The `default` plan cannot be deleted.
- Plans with subscription history cannot be deleted.
- Other plans can be deleted by admins with `plan:write`.

## Frontend Guidance

Management pages should treat `typeLabel`, `name`, `description`, `subtitle`, `badgeLabel`,
`highlightItems`, `upgradeRules`, `prices`, `entitlements`, and `expertIds` as the editable
product configuration.

`code` is a backend-maintained system identifier. The frontend may display it for debugging
or admin visibility, but normal editing flows should prefer `typeLabel`.

The backend supports plans beyond Free, Pro, Max, and Business. Those labels are product
configuration, not hard-coded database requirements.

## Known Gaps

The following items are intentionally outside the current implementation:

- Payment checkout and payment webhooks.
- Orders, invoices, refunds, and renewal records.
- Prorated upgrade or downgrade calculation.
- Stored entitlement snapshots per subscription period.
- Runtime enforcement of expert access in chat invocation.
- Runtime enforcement of question, token, model tier, and seat limits.
- Scheduled subscription expiry, renewal, or downgrade jobs.
- Token usage aggregation.

If these features are added, prefer extending the current flat `plans` and `subscriptions`
model only when the behavior can remain simple. Add normalized tables only when historical
audit, billing reconciliation, or many-to-many authorization requirements make the extra
structure necessary.
