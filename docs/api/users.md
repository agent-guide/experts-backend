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
      "email": "user@example.com",
      "name": "Test User",
      "status": "active",
      "platformRoles": [],
      "tenantCount": 2,
      "createdAt": "2026-06-03T00:00:00+00:00",
      "updatedAt": "2026-06-03T00:00:00+00:00"
    }
  ]
}
```

## GET /{user_id}

Get a user's profile, platform roles and tenant memberships.

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
