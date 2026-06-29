# Plans API

Plans define which experts, model tiers, quotas, prices, and product features a tenant can use.
Plan prices, entitlements, and expert ids are stored directly on `plans` as JSON configuration.
Tenant subscriptions point to a plan and read the current plan configuration live. This phase does
not yet enforce chat usage, token limits, seat limits, payments, or upgrades.

## Admin Plans

Base path:

```text
/api/v1/plans
```

All endpoints require:

```text
Authorization: Bearer <accessToken>
```

Read permission:

```text
plan:read
```

Write permission:

```text
plan:write
```

## Plan Shape

```json
{
  "id": "plan_default",
  "code": "default",
  "name": "默认套餐",
  "level": 1,
  "description": "系统默认套餐，包含默认专家和基础使用额度。",
  "typeLabel": "默认套餐",
  "subtitle": "基础默认能力",
  "badgeLabel": "默认",
  "highlightItems": [
    "默认专家访问",
    "基础问答额度"
  ],
  "upgradeRules": {
    "fromPlanIds": [],
    "toPlanIds": [],
    "rules": ["默认开通"],
    "selfServiceEnabled": false
  },
  "status": "active",
  "isRecommended": true,
  "sortOrder": 10,
  "prices": [
    {
      "id": "plan_price_default_free_cny",
      "planId": "plan_default",
      "billingPeriod": "free",
      "currency": "CNY",
      "amountCents": 0,
      "discountLabel": null,
      "isEnabled": true,
      "createdAt": "2026-06-12T00:00:00+00:00",
      "updatedAt": "2026-06-12T00:00:00+00:00"
    }
  ],
  "entitlements": {
    "id": "plan_entitlement_default",
    "planId": "plan_default",
    "monthlyQuestionLimit": 100,
    "monthlyTokenLimit": 100000,
    "seatLimit": 1,
    "singleTurnTokenLimit": null,
    "modelTiers": ["core"],
    "features": {
      "teamManagement": false,
      "apiAccess": false,
      "privateDeployment": false
    },
    "createdAt": "2026-06-12T00:00:00+00:00",
    "updatedAt": "2026-06-12T00:00:00+00:00"
  },
  "expertIds": ["expert_default"],
  "createdAt": "2026-06-12T00:00:00+00:00",
  "updatedAt": "2026-06-12T00:00:00+00:00"
}
```

`code` is a backend-maintained system identifier. Frontend management pages should display and
edit `typeLabel`, not `code`.

Field constraints:

- `level`: plan tier / upgrade order. Integer from `1` to `99`, unique. Larger values usually mean higher-tier plans.
- `sortOrder`: display order. Integer from `0` to `9999`. Smaller values are shown first.

Allowed plan statuses:

- `active`
- `disabled`

Allowed billing periods:

- `free`
- `monthly`
- `yearly`
- `sales`

## GET /

List all plans for admins. Disabled plans are included.

Response `200`:

```json
{
  "items": [
    {
      "id": "plan_default",
      "code": "default",
      "name": "默认套餐",
      "level": 1,
      "description": "系统默认套餐，包含默认专家和基础使用额度。",
      "typeLabel": "默认套餐",
      "subtitle": "基础默认能力",
      "badgeLabel": "默认",
      "highlightItems": ["默认专家访问", "基础问答额度"],
      "upgradeRules": {
        "fromPlanIds": [],
        "toPlanIds": [],
        "rules": ["默认开通"],
        "selfServiceEnabled": false
      },
      "status": "active",
      "isRecommended": true,
      "sortOrder": 10,
      "prices": [
        {
          "id": "plan_price_default_free_cny",
          "planId": "plan_default",
          "billingPeriod": "free",
          "currency": "CNY",
          "amountCents": 0,
          "discountLabel": null,
          "isEnabled": true,
          "createdAt": "2026-06-12T00:00:00+00:00",
          "updatedAt": "2026-06-12T00:00:00+00:00"
        }
      ],
      "entitlements": {
        "id": "plan_entitlement_default",
        "planId": "plan_default",
        "monthlyQuestionLimit": 100,
        "monthlyTokenLimit": 100000,
        "seatLimit": 1,
        "singleTurnTokenLimit": null,
        "modelTiers": ["core"],
        "features": {
          "teamManagement": false,
          "apiAccess": false,
          "privateDeployment": false
        },
        "createdAt": "2026-06-12T00:00:00+00:00",
        "updatedAt": "2026-06-12T00:00:00+00:00"
      },
      "expertIds": ["expert_default"],
      "createdAt": "2026-06-12T00:00:00+00:00",
      "updatedAt": "2026-06-12T00:00:00+00:00"
    }
  ]
}
```

## GET /{plan_id}

Get one plan.

Response `200`: the plan shape.

Errors:

```text
404 PLAN_NOT_FOUND
```

## POST /

Create a plan.

Request:

```json
{
  "name": "Team",
  "level": 5,
  "description": "Team plan",
  "typeLabel": "团队",
  "subtitle": "团队协作",
  "badgeLabel": "团队版",
  "highlightItems": ["多人协作", "组织管理"],
  "upgradeRules": {
    "fromPlanIds": ["plan_pro"],
    "toPlanIds": [],
    "rules": ["联系销售"],
    "selfServiceEnabled": false
  },
  "status": "active",
  "isRecommended": false,
  "sortOrder": 50
}
```

`status` defaults to `active`. `isRecommended` defaults to `false`. `sortOrder` defaults to `0`.
When `isRecommended` is true, other plans are automatically unmarked. `code` is optional. When
omitted, the backend generates it from `typeLabel`.
`level` must be an integer from `1` to `99`. `sortOrder` must be an integer from `0` to `9999`.

Supported `typeLabel` values and base codes:

| typeLabel | Base code |
| --- | --- |
| `默认套餐` | `default` |
| `免费版` | `free` |
| `个人付费` | `pro` |
| `团队` / `Business` / `Business 版` | `business` |
| `企业定制` | `enterprise` |

If the base code is already used by another plan, the backend appends a numeric suffix, such as
`pro_2` or `business_2`.

Response `201`: the plan shape.

Errors:

```text
400 PLAN_TYPE_LABEL_REQUIRED
400 PLAN_TYPE_LABEL_UNSUPPORTED
409 PLAN_CONFLICT
422 validation error
```

## PATCH /{plan_id}

Update a plan.

Request:

```json
{
  "name": "Team Plus",
  "description": "Updated description",
  "status": "disabled",
  "isRecommended": true,
  "sortOrder": 60
}
```

All fields are optional. When `isRecommended` is true, other plans are automatically unmarked.
`highlightItems` and `upgradeRules` replace the stored display configuration when provided.
When `typeLabel` changes and `code` is omitted, the backend regenerates `code` from the new
`typeLabel` using the same suffix rule as create. Current subscriptions read the latest plan
configuration.
`level` must be an integer from `1` to `99`. `sortOrder` must be an integer from `0` to `9999`.

Response `200`: the plan shape.

Errors:

```text
400 PLAN_TYPE_LABEL_UNSUPPORTED
404 PLAN_NOT_FOUND
409 PLAN_CONFLICT
422 validation error
```

## PUT /{plan_id}/prices

Replace all prices stored on a plan.

Request:

```json
{
  "items": [
    {
      "billingPeriod": "monthly",
      "currency": "CNY",
      "amountCents": 9900,
      "discountLabel": null,
      "isEnabled": true
    },
    {
      "billingPeriod": "yearly",
      "currency": "CNY",
      "amountCents": 99900,
      "discountLabel": "年付优惠",
      "isEnabled": true
    }
  ]
}
```

Response `200`: the plan shape.

Errors:

```text
404 PLAN_NOT_FOUND
409 PLAN_PRICE_DUPLICATE
422 validation error
```

## PUT /{plan_id}/entitlements

Replace the entitlements stored on a plan.

Request:

```json
{
  "monthlyQuestionLimit": 1000,
  "monthlyTokenLimit": 2000000,
  "seatLimit": 1,
  "singleTurnTokenLimit": null,
  "modelTiers": ["core", "enhanced"],
  "features": {
    "teamManagement": false,
    "apiAccess": false,
    "privateDeployment": false
  }
}
```

Response `200`: the plan shape.

Errors:

```text
404 PLAN_NOT_FOUND
422 validation error
```

## PUT /{plan_id}/experts

Replace the expert ids accessible by a plan.

Request:

```json
{
  "expertIds": ["expert_1", "expert_2"]
}
```

Response `200`: the plan shape.

Errors:

```text
404 PLAN_NOT_FOUND
404 EXPERT_NOT_FOUND
```

## DELETE /{plan_id}

Delete a plan.

Response:

```text
204 No Content
```

Errors:

```text
404 PLAN_NOT_FOUND
409 PLAN_DEFAULT_DELETE_FORBIDDEN
409 PLAN_HAS_SUBSCRIPTIONS
```

The seeded `default` plan cannot be deleted. Plans with subscription history cannot be deleted.

## User Plan Market

Base path:

```text
/api/v1/plan-market
```

All endpoints require sign-in:

```text
Authorization: Bearer <accessToken>
```

No specific platform permission is required.

## GET /plans

List active plans and enabled prices for the signed-in user-side pricing page.

Response `200`:

```json
{
  "items": [
    {
      "id": "plan_default",
      "code": "default",
      "name": "默认套餐",
      "level": 1,
      "description": "系统默认套餐，包含默认专家和基础使用额度。",
      "typeLabel": "默认套餐",
      "subtitle": "基础默认能力",
      "badgeLabel": "默认",
      "highlightItems": [
        "默认专家访问",
        "基础问答额度"
      ],
      "upgradeRules": {
        "fromPlanIds": [],
        "toPlanIds": [],
        "rules": ["默认开通"],
        "selfServiceEnabled": false
      },
      "status": "active",
      "isRecommended": true,
      "sortOrder": 10,
      "prices": [
        {
          "id": "plan_price_default_free_cny",
          "planId": "plan_default",
          "billingPeriod": "free",
          "currency": "CNY",
          "amountCents": 0,
          "discountLabel": null,
          "isEnabled": true,
          "createdAt": "2026-06-12T00:00:00+00:00",
          "updatedAt": "2026-06-12T00:00:00+00:00"
        }
      ],
      "entitlements": {
        "id": "plan_entitlement_default",
        "planId": "plan_default",
        "monthlyQuestionLimit": 100,
        "monthlyTokenLimit": 100000,
        "seatLimit": 1,
        "singleTurnTokenLimit": null,
        "modelTiers": ["core"],
        "features": {
          "teamManagement": false,
          "apiAccess": false,
          "privateDeployment": false
        },
        "createdAt": "2026-06-12T00:00:00+00:00",
        "updatedAt": "2026-06-12T00:00:00+00:00"
      },
      "expertIds": ["expert_default"],
      "createdAt": "2026-06-12T00:00:00+00:00",
      "updatedAt": "2026-06-12T00:00:00+00:00"
    }
  ]
}
```

## GET /current-subscription

Return the active tenant subscription and current plan configuration. If the active tenant has no
subscription, the backend creates a default `default` plan subscription.

Response `200`:

```json
{
  "subscription": {
    "id": "tenant_subscription_123",
    "tenantId": "tenant_123",
    "planId": "plan_default",
    "status": "active",
    "billingPeriod": "free",
    "currentPeriodStart": "2026-06-12T00:00:00+00:00",
    "currentPeriodEnd": null,
    "cancelAtPeriodEnd": false,
    "createdAt": "2026-06-12T00:00:00+00:00",
    "updatedAt": "2026-06-12T00:00:00+00:00"
  },
  "plan": {
    "id": "plan_default",
    "code": "default",
    "name": "默认套餐",
    "level": 1,
    "description": "系统默认套餐，包含默认专家和基础使用额度。",
    "typeLabel": "默认套餐",
    "subtitle": "基础默认能力",
    "badgeLabel": "默认",
    "highlightItems": ["默认专家访问", "基础问答额度"],
    "upgradeRules": {
      "fromPlanIds": [],
      "toPlanIds": [],
      "rules": ["默认开通"],
      "selfServiceEnabled": false
    },
    "status": "active",
    "isRecommended": true,
    "sortOrder": 10,
    "subscriptionCount": 1,
    "prices": [],
    "entitlements": {
      "id": "plan_entitlement_default",
      "planId": "plan_default",
      "monthlyQuestionLimit": 100,
      "monthlyTokenLimit": 100000,
      "seatLimit": 1,
      "singleTurnTokenLimit": null,
      "modelTiers": ["core"],
      "features": {
        "teamManagement": false,
        "apiAccess": false,
        "privateDeployment": false
      },
      "createdAt": "2026-06-12T00:00:00+00:00",
      "updatedAt": "2026-06-12T00:00:00+00:00"
    },
    "expertIds": ["expert_default"],
    "createdAt": "2026-06-12T00:00:00+00:00",
    "updatedAt": "2026-06-12T00:00:00+00:00"
  }
}
```

Errors:

```text
400 TENANT_REQUIRED
500 DEFAULT_PLAN_MISSING
```
