# User, Tenant and RBAC Implementation Plan

## Goal

Refactor `amazon-experts-backend` from the current single-tenant-style auth
model into scoped identity:

- `users` are login identities.
- `tenants` are customer workspaces.
- `tenant_members` grants tenant roles: `admin`, `member`.
- `platform_user_roles` grants platform roles: `admin`, `expert`, `operator`.

## Current State

The current implementation binds `users.tenant_id` directly to a single tenant
and stores mixed roles in `user_roles`:

- `User`
- `Admin`
- `Expert`
- `Ops`

This mixes tenant product permissions and platform management permissions in one
role namespace.

## Target State

### Database

Use these tables:

- `users`
- `tenants`
- `tenant_members`
- `platform_user_roles`
- `refresh_tokens`
- `platform_activation_tokens`

`refresh_tokens` are user scoped. Tenant/platform context is resolved for access
tokens and request authorization.

### Domain Model

Use two role enums:

- `TenantRole`: `admin`, `member`
- `PlatformRole`: `admin`, `expert`, `operator`

Use one principal object containing both optional tenant context and platform
roles.

### Authorization

Provide separate dependencies:

- `require_tenant_principal`
- `require_platform_principal`
- `require_tenant_permission`
- `require_platform_permission`

Tenant product APIs require `x-tenant-id`.
Platform APIs do not require `x-tenant-id`.

## Execution Steps

1. Update auth SQL schema.
2. Split role and permission models.
3. Update JWT claims and refresh token handling.
4. Update auth service registration, login, refresh, logout and platform user activation.
5. Replace mixed permission dependencies with tenant/platform dependencies.
6. Update routers to use the correct permission scope.
7. Add platform user creation and activation-token issuing under user APIs.
8. Update tests.
9. Run full test suite and lint.

## API Mapping

Tenant-scoped APIs:

- knowledge base CRUD
- document APIs
- upload APIs
- chat APIs
- model list APIs
- tenant user/member management

Platform-scoped APIs:

- skill publish/update/delete
- official knowledge base publish
- platform user creation
- platform role grants
- ops metrics
- platform user/role management

Shared authenticated APIs:

- skill browse/read can accept any authenticated user for now.

## Notes

For this pre-production project state, the schema is updated directly in
`001_phase3_auth.sql`. If production data exists later, convert this into an
incremental migration with data backfill from the old `user_roles` table.
