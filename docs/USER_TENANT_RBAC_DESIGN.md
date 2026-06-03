# User, Tenant and RBAC Design

## 1. Goal

This document defines the target identity model for `amazon-experts-backend`.

The system has two user domains:

- Tenant users: customers who use the SaaS product.
- Platform users: internal/provider-side users who manage experts, skills,
  platform knowledge bases, operations and support workflows.

The same person may have both domains, but permissions must always be evaluated
against the active context.

## 2. Core Concepts

### 2.1 User

A user is a login identity, usually represented by an email, password hash and
account status.

Recommended table shape:

```sql
users (
  id,
  email,
  password_hash,
  status,
  created_at,
  updated_at
)
```

A user should not have one global `role` column that mixes tenant and platform
permissions.

### 2.2 Tenant

A tenant is a customer-side workspace and data isolation boundary.

Tenant types:

- `personal`: default workspace for a single-user account.
- `team`: workspace for multiple users.

Recommended table shape:

```sql
tenants (
  id,
  type, -- personal | team
  name,
  owner_user_id,
  created_at,
  updated_at
)
```

For normal product usage, all customer-owned resources should be scoped by
`tenant_id`.

### 2.3 Tenant Membership

Tenant membership connects users to tenants and defines tenant-scoped roles.

Recommended table shape:

```sql
tenant_members (
  tenant_id,
  user_id,
  role, -- admin | member
  created_at,
  updated_at
)
```

Tenant roles:

- `admin`: manages tenant settings, members and tenant-owned resources.
- `member`: uses tenant resources according to product-level permissions.

The role name `admin` only means admin inside that tenant. It is not the same as
platform admin.

### 2.4 Platform Role

Platform roles grant provider-side permissions. They do not belong to a customer
tenant.

Recommended table shape:

```sql
platform_user_roles (
  user_id,
  role, -- admin | expert | operator
  created_at,
  updated_at
)
```

Platform roles:

- `admin`: manages platform-level configuration, users, experts, skills and
  global governance.
- `expert`: creates or maintains platform-managed expert assets, knowledge bases
  and skills.
- `operator`: performs operational tasks, review, troubleshooting and support
  workflows.

## 3. Identity Context

Permission checks must be based on an explicit active context.

Tenant product context:

```text
user_id = current authenticated user
context_type = tenant
tenant_id = selected tenant
role = tenant_members.role
```

Platform management context:

```text
user_id = current authenticated user
context_type = platform
role = platform_user_roles.role
```

The API should not infer platform permissions from tenant roles, or tenant
permissions from platform roles.

Current implementation:

- Login and refresh may encode an `activeTenantId` in the access token.
- Tenant-scoped routes require the request `x-tenant-id` header to match the
  principal's active tenant.
- Platform-scoped routes do not require `x-tenant-id`; they require platform
  roles/permissions.
- Each authenticated request reloads the user, tenant roles and platform roles
  from the database before authorization. This makes role revocation, tenant
  membership removal and user disablement take effect immediately for access
  tokens that have not yet expired.
- If an access token names an active tenant that the user no longer belongs to,
  the stale tenant context is dropped. Tenant-scoped calls still fail through the
  tenant mismatch check, while valid platform-scoped calls can continue.

## 4. Platform Users Using the Product

Platform users may also use the product like normal users.

Recommended approach:

- Keep one login identity in `users`.
- Give the user platform roles through `platform_user_roles`.
- Also create or join a tenant through `tenant_members` when the user needs
  normal product usage.
- For default single-user usage, create a `personal` tenant and add the user as
  tenant `admin`.

Example:

```text
User: alice@example.com

Platform context:
- platform role: expert

Tenant product context:
- tenant type: personal
- tenant role: admin
```

This keeps product data isolation and platform administration separate.

## 5. Registration and Login

Tenant self-registration:

1. Create `users` row.
2. Create default `personal` tenant.
3. Insert `tenant_members` row with role `admin`.
4. Issue token with user identity.

Team tenant creation:

1. Existing user creates a `team` tenant.
2. Creator becomes tenant `admin`.
3. Invited users become `member` unless explicitly promoted.

Platform user creation:

1. Platform admin/operator creates a platform user and issues an activation token.
2. Platform roles are assigned during creation or through role-grant APIs.
3. The invited platform user activates the account with the token and sets a password.
4. Optional: also create a personal tenant if this user needs product usage.

Platform users are not created through public registration.
`POST /api/v1/users/register` is for tenant product users and creates a default
`personal` tenant. Platform users are created through
`POST /api/v1/users/platform` and activated through
`POST /api/v1/users/platform/activate`.

Login should authenticate only the user identity. The active tenant or platform
context should be selected after login or encoded explicitly in request context.

## 6. Authorization Rules

Tenant resource access:

- Request must have a valid tenant context.
- The user must be a member of the tenant.
- Resource `tenant_id` must match the active tenant.
- Required permission is derived from tenant role.
- For delegated PageIndex/ngent resources, Expert Next API forwards the active
  tenant as `X-Tenant-Id` to the upstream service. Upstream services must use
  that value as the resource isolation boundary for read/update/delete calls by
  resource id.

Platform resource access:

- Request must have a valid platform context.
- The user must have the required platform role or permission.
- Platform resources such as skills and platform expert assets should not be
  owned by customer tenants by default.
- Platform/official endpoints intentionally do not send an upstream tenant id.

Support or impersonation access:

- Platform users should not silently bypass tenant isolation.
- If support access is needed, model it as an explicit support/impersonation
  flow with audit logs.

## 7. Token Claims

Current access token claims:

```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "activeTenantId": "tenant_1",
  "tenantRoles": ["admin"],
  "platformRoles": ["expert"],
  "type": "access"
}
```

Access tokens carry roles only, not expanded permission lists. The API derives
permissions from the role-to-permission mapping after decoding and then reloads
the fresh user/role state from the database through request authentication.
Refresh tokens are user-scoped and do not carry tenant roles, platform roles or
permissions.

Avoid a single global claim such as:

```json
{
  "role": "admin"
}
```

because it cannot distinguish platform admin from tenant admin.

## 8. Impact on Current Domains

Skills:

- Skills are platform-managed assets.
- Creating, updating and deleting skills should require platform permission,
  for example `skill:publish`.
- Tenant users may browse or use published skills only if the product exposes
  that capability.

Experts:

- Platform experts and their official knowledge/skills are provider-owned.
- Tenant users consume experts through product workflows.
- Tenant-specific experts should be modeled separately if the product later
  supports customer-created expert agents.

Knowledge bases:

- Platform knowledge bases can power official experts.
- Tenant knowledge bases should be scoped by `tenant_id`.
- Do not mix these two ownership models in one ambiguous field.

## 9. Implementation Notes

Recommended migration order:

1. Normalize user identity into `users`.
2. Add `tenants` and `tenant_members`.
3. Move tenant roles out of any global user role field.
4. Add `platform_user_roles`.
5. Update auth dependencies to resolve either tenant context or platform context.
6. Update RBAC checks to use scoped permissions.
7. Add audit logs for platform role changes, tenant membership changes and
   support/impersonation flows.

Current RBAC safety rules:

- `DELETE /api/v1/rbac/tenant/users/{user_id}` removes a tenant member.
- `DELETE /api/v1/rbac/platform/users/{user_id}/roles/{role}` revokes a
  platform role.
- Tenant admin demotion/removal is blocked when it would remove the last tenant
  admin (`409 TENANT_LAST_ADMIN`).
- Platform admin revocation is blocked when it would remove the last platform
  admin (`409 PLATFORM_LAST_ADMIN`).
- Last-admin checks run inside write transactions with membership/role locking
  where supported by the database.

Deferred product decisions:

- Team tenant creation and email-based tenant invitations are separate product
  flows and are not part of the current RBAC bug-fix scope.
- Tenant disablement is not yet modeled in authorization; add tenant status
  checks when a tenant-disable flow exists.

Follow-up design decisions:

- Whether the API should add an explicit support/impersonation context that can
  access tenant resources with audit logs.
- Whether platform roles should keep using the static role-to-permission mapping
  or move to a database-backed role-permission table.
- Whether tenant `member` needs finer product permissions beyond the initial
  `admin/member` split.
