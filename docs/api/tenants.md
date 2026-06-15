# Tenants API

Base path:

```text
/api/v1/tenants
```

Tenant management is a platform-side workflow for customer workspaces. All
endpoints require:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
platform:tenant_manage
```

## Resource Shape

```json
{
  "id": "tenant_123",
  "type": "team",
  "name": "Acme Team",
  "slug": "acme-team",
  "ownerUserId": "user_123",
  "ownerUserName": "Alice",
  "status": "active",
  "memberCount": 3,
  "createdAt": "2026-06-03T00:00:00+00:00",
  "updatedAt": "2026-06-03T00:00:00+00:00"
}
```

## GET /

List tenants.

Response `200`:

```json
{
  "items": [
    {
      "id": "tenant_123",
      "type": "team",
      "name": "Acme Team",
      "slug": "acme-team",
      "ownerUserId": "user_123",
      "ownerUserName": "Alice",
      "status": "active",
      "memberCount": 3,
      "createdAt": "2026-06-03T00:00:00+00:00",
      "updatedAt": "2026-06-03T00:00:00+00:00"
    }
  ]
}
```

## POST /

Create a `team` tenant. The owner user must already exist and is automatically
added as tenant `admin`.

Request:

```json
{
  "name": "Acme Team",
  "slug": "acme-team",
  "ownerUserId": "user_123"
}
```

`slug` is optional. If omitted, the server generates a slug from `name`.

Response `201`: the resource shape.

Errors:

```text
404 USER_NOT_FOUND
409 TENANT_SLUG_EXISTS
```

## GET /{tenant_id}

Get a tenant.

Response `200`: the resource shape.

Errors:

```text
404 TENANT_NOT_FOUND
```

## PATCH /{tenant_id}

Update tenant name, slug, or owner. When `ownerUserId` changes, the new owner is
automatically added as tenant `admin`.

Request:

```json
{
  "name": "Acme Renamed",
  "slug": "acme-renamed",
  "ownerUserId": "user_456"
}
```

All fields are optional.

Response `200`: the resource shape.

Errors:

```text
404 TENANT_NOT_FOUND
404 USER_NOT_FOUND
409 TENANT_SLUG_EXISTS
```

## PATCH /{tenant_id}/status

Enable or disable a tenant.

Request:

```json
{
  "status": "disabled"
}
```

Allowed values:

- `active`
- `disabled`

Response `200`: the resource shape.

## GET /{tenant_id}/members

List tenant members.

Response `200`:

```json
{
  "items": [
    {
      "userId": "user_123",
      "email": "alice@example.com",
      "name": "Alice",
      "status": "active",
      "role": "admin",
      "joinedAt": "2026-06-03T00:00:00+00:00"
    }
  ]
}
```

## POST /{tenant_id}/members

Add a user to the tenant, or update the role if the membership already exists.
The user must already exist.

Request:

```json
{
  "userId": "user_123",
  "role": "member"
}
```

`role` defaults to `member`.

Response `201`: the member shape.

Errors:

```text
404 TENANT_NOT_FOUND
404 USER_NOT_FOUND
```

## PATCH /{tenant_id}/members/{user_id}

Update a tenant member role.

Request:

```json
{
  "role": "admin"
}
```

Allowed roles:

- `admin`
- `member`

Response `200`: the member shape.

Errors:

```text
404 TENANT_NOT_FOUND
404 MEMBER_NOT_FOUND
409 TENANT_LAST_ADMIN
```

## DELETE /{tenant_id}/members/{user_id}

Remove a tenant member.

Response:

```text
204 No Content
```

Errors:

```text
404 TENANT_NOT_FOUND
404 MEMBER_NOT_FOUND
409 TENANT_LAST_ADMIN
```

`TENANT_LAST_ADMIN` protects a tenant from ending up with no admin member.
