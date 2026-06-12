# RBAC API

Base path:

```text
/api/v1/rbac
```

This group owns account permission management. Tenant RBAC is scoped by
`x-tenant-id`; platform RBAC is scoped by platform roles. Access tokens carry
role snapshots only; each request reloads current roles from the database before
authorization, so grants, revokes, tenant member removal and user disablement
take effect immediately for subsequent requests.

## GET /tenant/users

List users in the active tenant.

Auth:

```text
Authorization: Bearer <accessToken>
x-tenant-id: <tenant_id>
```

Required tenant permission:

```text
tenant:user_manage
```

Response `200`:

```json
{
  "items": [
    {
      "id": "user_1",
      "email": "user@example.com",
      "name": "Test User",
      "status": "active",
      "activeTenantId": "tenant_1",
      "tenantRoles": ["admin"],
      "tenantPermissions": ["tenant:user_manage"],
      "platformRoles": [],
      "platformPermissions": [],
      "createdAt": "2026-06-03T00:00:00+00:00",
      "updatedAt": "2026-06-03T00:00:00+00:00"
    }
  ]
}
```

## POST /tenant/users/{user_id}/roles

Grant or update a user's tenant role in the active tenant.

Auth:

```text
Authorization: Bearer <accessToken>
x-tenant-id: <tenant_id>
```

Required tenant permission:

```text
tenant:role_grant
```

Request:

```json
{
  "role": "admin"
}
```

Allowed tenant roles:

- `admin`
- `member`

Demoting the last remaining tenant admin is rejected with `409 TENANT_LAST_ADMIN`.
The last-admin check is performed inside a write transaction to avoid concurrent
updates removing all admins.

Response:

```text
204 No Content
```

## DELETE /tenant/users/{user_id}

Remove a user's membership from the active tenant.

Auth:

```text
Authorization: Bearer <accessToken>
x-tenant-id: <tenant_id>
```

Required tenant permission:

```text
tenant:user_manage
```

Responses:

```text
204 No Content        membership removed
404 MEMBER_NOT_FOUND  user is not a member of this tenant
409 TENANT_LAST_ADMIN attempted to remove the last tenant admin
```

## GET /platform/roles

List available platform roles and their derived permissions.

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
platform:role_grant
```

Response `200`:

```json
{
  "items": [
    {
      "role": "admin",
      "name": "admin",
      "permissions": [
        "doc:create",
        "doc:delete",
        "doc:read",
        "doc:update",
        "kb:build",
        "kb:create",
        "kb:delete",
        "kb:read",
        "kb:update",
        "plan:read",
        "plan:write",
        "platform:entitlement_grant",
        "platform:role_grant",
        "platform:tenant_manage",
        "platform:user_manage",
        "skill:read",
        "skill:write",
        "system:ops"
      ]
    }
  ]
}
```

Plan permissions:

- `plan:read` is granted to `admin` and `operator`.
- `plan:write` is granted to `admin`.

## POST /platform/users/{user_id}/roles

Grant a platform role.

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
platform:role_grant
```

Request:

```json
{
  "role": "expert"
}
```

Allowed platform roles:

- `admin`
- `expert`
- `operator`

A non-admin actor (e.g. `operator`) cannot grant the `admin` role.

Response:

```text
204 No Content
```

## DELETE /platform/users/{user_id}/roles/{role}

Revoke a platform role from a user. Idempotent: revoking a role the user does not
have still returns `204`.

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
platform:role_grant
```

Missing target users return `404 USER_NOT_FOUND`. A non-admin actor (e.g.
`operator`) cannot revoke the `admin` role. Revoking the last remaining platform
admin is rejected with `409 PLATFORM_LAST_ADMIN`. The last-admin check is
performed inside a write transaction to avoid concurrent updates removing all
platform admins.

Responses:

```text
204 No Content             role revoked, or role was already absent
404 USER_NOT_FOUND         target user does not exist
409 PLATFORM_LAST_ADMIN    attempted to revoke the last platform admin
```
