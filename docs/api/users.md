# Users API

Base path:

```text
/api/v1/users
```

This group owns account lifecycle APIs: tenant user registration, platform user
invitation and platform user activation. Session APIs stay under
`/api/v1/auth`.

## POST /register

Register a tenant product user.

Current behavior:

1. Creates a `users` row.
2. Creates a default `personal` tenant.
3. Adds the user to that tenant as tenant `admin`.
4. Issues access and refresh tokens.

Request:

```json
{
  "email": "user@example.com",
  "password": "secret123",
  "name": "Test User"
}
```

Response `201`:

```json
{
  "accessToken": "...",
  "refreshToken": "...",
  "expiresInSeconds": 900
}
```

## GET /

List ordinary users for platform-side user management. This list excludes users
that currently have platform roles; use `GET /platform` for platform personnel.
The response also includes the user's current subscription summary, monthly usage
summary, order summary and lifetime usage summary for the ordinary-user
management page.

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
platform:user_manage
```

Query parameters:

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `search` | string | no | Searches user name, email, current plan name and tenant count. |
| `subscriptionStatus` | string | no | Filters by `active`, `expiring_soon`, `expired`, or Chinese labels `订阅中`, `即将到期`, `已过期`. |
| `subscriptionType` | string | no | Filters by current plan plus billing period, for example `专业版 · 月付`, `专业版 monthly`, `免费版 免费`. |
| `sort` | string | no | `expiresAt`, `monthlyUsage`, or `subscriptionStart`. |
| `page` | integer | no | Page number, starts at `1`. Default `1`. |
| `pageSize` | integer | no | Page size, `1-100`. Default `50`. |

Response `200`:

```json
{
  "total": 1,
  "page": 1,
  "pageSize": 50,
  "items": [
    {
      "id": "user_123",
      "email": "user@example.com",
      "name": "Test User",
      "status": "active",
      "platformRoles": [],
      "tenantCount": 2,
      "currentSubscription": {
        "subscriptionId": "sub_123",
        "planId": "plan_pro",
        "planCode": "pro",
        "planName": "专业版",
        "billingPeriod": "monthly",
        "status": "expiring_soon",
        "statusLabel": "即将到期",
        "currentPeriodStart": "2026-06-01T00:00:00+00:00",
        "currentPeriodEnd": "2026-06-21T00:00:00+00:00",
        "daysUntilExpiry": 9,
        "cancelAtPeriodEnd": false,
        "autoRenew": true,
        "priceLabel": "¥99 / 月",
        "currentOrderNo": null,
        "paymentMethod": null,
        "tenantId": "tenant_1",
        "tenantName": "A Company"
      },
      "monthlyUsage": {
        "questionUsed": 20,
        "questionLimit": 100,
        "tokenUsed": 0,
        "tokenLimit": 50000,
        "questionUsagePercent": 20,
        "tokenUsagePercent": 0,
        "status": "expiring_soon",
        "isServicePaused": false
      },
      "orderSummary": {
        "totalAmountCents": 0,
        "orderCount": 0,
        "recentOrders": []
      },
      "usageLifetime": {
        "startDate": "2026-06-03T00:00:00+00:00",
        "usageDays": 10,
        "stopped": false
      },
      "createdAt": "2026-06-03T00:00:00+00:00",
      "updatedAt": "2026-06-03T00:00:00+00:00"
    }
  ]
}
```

Notes:

- `currentSubscription` is `null` when none of the user's tenants has a tenant
  subscription.
- `monthlyUsage.questionUsed` is counted from this month's non-internal
  `chat_turns` for the selected subscription tenant.
- `monthlyUsage.tokenUsed` is currently `0` because persisted token usage is not
  available yet. `tokenLimit` comes from the subscription entitlement snapshot.
- `orderSummary` is a real empty summary until order/payment tables are added.
- Current tenant membership roles are `admin` and `member`; the database does not
  yet model `owner` or `viewer` tenant roles.

## GET /{user_id}

Get a user's profile, platform roles, tenant memberships, current subscription,
monthly usage, order summary and lifetime usage summary.

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
platform:user_manage
```

Response `200`:

```json
{
  "id": "user_123",
  "email": "user@example.com",
  "name": "Test User",
  "status": "active",
  "platformRoles": [],
  "platformPermissions": [],
  "tenants": [
    {
      "id": "tenant_1",
      "name": "A Company",
      "type": "team",
      "slug": "a-company",
      "status": "active",
      "role": "admin",
      "joinedAt": "2026-06-03T00:00:00+00:00"
    }
  ],
  "currentSubscription": {
    "subscriptionId": "sub_123",
    "planId": "plan_pro",
    "planCode": "pro",
    "planName": "专业版",
    "billingPeriod": "monthly",
    "status": "expiring_soon",
    "statusLabel": "即将到期",
    "currentPeriodStart": "2026-06-01T00:00:00+00:00",
    "currentPeriodEnd": "2026-06-21T00:00:00+00:00",
    "daysUntilExpiry": 9,
    "cancelAtPeriodEnd": false,
    "autoRenew": true,
    "priceLabel": "¥99 / 月",
    "currentOrderNo": null,
    "paymentMethod": null,
    "tenantId": "tenant_1",
    "tenantName": "A Company"
  },
  "monthlyUsage": {
    "questionUsed": 20,
    "questionLimit": 100,
    "tokenUsed": 0,
    "tokenLimit": 50000,
    "questionUsagePercent": 20,
    "tokenUsagePercent": 0,
    "status": "expiring_soon",
    "isServicePaused": false
  },
  "orderSummary": {
    "totalAmountCents": 0,
    "orderCount": 0,
    "recentOrders": []
  },
  "usageLifetime": {
    "startDate": "2026-06-03T00:00:00+00:00",
    "usageDays": 10,
    "stopped": false
  },
  "createdAt": "2026-06-03T00:00:00+00:00",
  "updatedAt": "2026-06-03T00:00:00+00:00"
}
```

Missing users return `404 USER_NOT_FOUND`.

## PATCH /{user_id}

Update a user's basic profile.

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
platform:user_manage
```

Request:

```json
{
  "name": "Updated User"
}
```

Response `200`: the user detail shape from `GET /{user_id}`.

## PATCH /{user_id}/status

Enable or disable a user.

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
platform:user_manage
```

Request:

```json
{
  "status": "disabled"
}
```

Allowed status values:

- `active`
- `disabled`

Response `200`: the user detail shape from `GET /{user_id}`.

Disabling the last remaining platform `admin` is rejected with
`409 PLATFORM_LAST_ADMIN`.

## GET /{user_id}/tenants

List the tenants a user belongs to.

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
platform:user_manage
```

Response `200`:

```json
{
  "items": [
    {
      "id": "tenant_1",
      "name": "A Company",
      "type": "team",
      "slug": "a-company",
      "status": "active",
      "role": "member",
      "joinedAt": "2026-06-03T00:00:00+00:00"
    }
  ]
}
```

## POST /platform/activate

Activate a pre-created platform user by activation token.

This endpoint does not require bearer authentication. The activation token is
the credential for this one-time action. Platform admins/operators create
platform users and issue activation tokens through `POST /api/v1/users/platform`.

Request:

```json
{
  "token": "activation-token",
  "newPassword": "new-secret",
  "name": "Platform User"
}
```

`name` is optional and updates the user's display name when provided. Activation
only sets the password and activates the account; it does not create tenant
membership. If the platform user needs product usage, grant tenant membership
separately.

Response `200`:

```json
{
  "message": "Platform user activated",
  "userId": "platform_user",
  "email": "platform@example.com"
}
```

## GET /platform

List platform users. The response includes users that currently have at least
one platform role, including pending invitation users.

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
platform:user_manage
```

Response `200`:

```json
{
  "items": [
    {
      "id": "user_123",
      "email": "expert@example.com",
      "name": "Expert User",
      "status": "pending_activation",
      "activeTenantId": null,
      "tenantRoles": [],
      "tenantPermissions": [],
      "platformRoles": ["expert"],
      "platformPermissions": ["doc:create", "doc:read", "kb:create"],
      "createdAt": "2026-06-03T00:00:00+00:00",
      "updatedAt": "2026-06-03T00:00:00+00:00"
    }
  ]
}
```

## POST /platform

Create a platform user and issue a one-time activation token.

This endpoint is for platform-side user lifecycle management. It does not create
a tenant and it is not part of public user registration.

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
platform:user_manage
```

Role assignment is checked against the caller's platform roles. For example,
`operator` may create non-admin platform users, but cannot create a platform
`admin`.

Request:

```json
{
  "email": "expert@example.com",
  "name": "Expert User",
  "roles": ["expert"]
}
```

`roles` defaults to `["expert"]` when omitted.

Response `201`:

```json
{
  "id": "user_123",
  "email": "expert@example.com",
  "name": "Expert User",
  "status": "pending_activation",
  "platformRoles": ["expert"],
  "activationToken": "one-time-token",
  "activationExpiresAt": "2026-06-10T00:00:00+00:00"
}
```

The caller should deliver `activationToken` to the invited platform user through
the product's invitation channel. The user then completes activation through
`POST /api/v1/users/platform/activate`.
