# Auth API

Base path:

```text
/api/v1/auth
```

Auth endpoints do not require bearer authentication unless explicitly stated.

## POST /login

Login by email and password.

Request:

```json
{
  "email": "user@example.com",
  "password": "secret123",
  "tenantId": "tenant_x"
}
```

`tenantId` is optional. If omitted, the service uses the first tenant membership
as active tenant. Platform-only users may login without an active tenant.

Response `200`:

```json
{
  "accessToken": "...",
  "refreshToken": "...",
  "expiresInSeconds": 900
}
```

## POST /refresh

Rotate a refresh token and issue a new token pair.

Request:

```json
{
  "refreshToken": "...",
  "tenantId": "tenant_x"
}
```

`tenantId` is optional and selects the active tenant for the new access token.

Response `200`:

```json
{
  "accessToken": "...",
  "refreshToken": "...",
  "expiresInSeconds": 900
}
```

## POST /logout

Revoke a refresh token.

Request:

```json
{
  "refreshToken": "..."
}
```

Response:

```text
204 No Content
```

## Access Token Claims

Access tokens carry only scoped identity and roles. Permissions are derived from
roles on the server, so the role-to-permission mapping stays the single source
of truth and is not duplicated into the token:

```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "activeTenantId": "tenant_x",
  "tenantRoles": ["admin"],
  "platformRoles": ["expert"],
  "type": "access"
}
```

Refresh tokens are user-scoped and do not carry tenant roles or permissions.

During authenticated request handling, the API treats these token roles as a
snapshot only. It reloads the user and current roles from the database before
authorization, rejects disabled users with `401 AUTH_USER_DISABLED`, and rebuilds
permissions from the fresh roles. If the token's `activeTenantId` no longer
belongs to the user, the tenant context is dropped; tenant-scoped APIs then fail
on the required `x-tenant-id` match, while platform-scoped APIs can still be
authorized from current platform roles.
