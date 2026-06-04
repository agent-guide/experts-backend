# User, Tenant and RBAC — Architecture Design and Technical Specification

This document defines the identity, tenancy and RBAC model for
`amazon-experts-backend`, and specifies the concrete schema, domain model,
permission matrix and authorization dependencies that implement it. The model
described here is implemented.

## 1. Goal

The system has two user domains:

- Tenant users: customers who use the SaaS product.
- Platform users: internal/provider-side users who manage experts, skills,
  platform knowledge bases, operations and support workflows.

The same person may have both domains, but permissions must always be evaluated
against the active context.

Core principle: platform-provided capabilities (knowledge bases, documents,
skills, and the future `experts` entity) are authored and managed by platform
users. Tenant users only consume them through product workflows (chat).

## 2. Core Concepts

### 2.1 User

A user is a login identity, usually represented by an email, password hash and
account status.

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

A user does not have one global `role` column that mixes tenant and platform
permissions.

### 2.2 Tenant

A tenant is a customer-side workspace and data isolation boundary.

Tenant types:

- `personal`: default workspace for a single-user account.
- `team`: workspace for multiple users.

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

For normal product usage, all customer-owned resources are scoped by
`tenant_id`.

### 2.3 Tenant Membership

Tenant membership connects users to tenants and defines tenant-scoped roles.

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
platform admin. Tenant roles do not hold any `kb:*`, `doc:*` or `skill:*`
permission; tenants consume platform capabilities through product workflows
(chat).

### 2.4 Platform Role

Platform roles grant provider-side permissions. They do not belong to a customer
tenant.

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
  global governance. Superset of `expert` and `operator`.
- `expert`: authors and maintains the platform-provided capabilities — knowledge
  bases, documents and skills. This is the only role that can create, update or
  delete those capabilities.
- `operator`: manages tenant users and capability entitlement — it governs which
  users/tenants may use which platform capabilities. It can read capabilities and
  grant their use (`platform:entitlement_grant`), but cannot author them.

## 3. Permission Matrix

Permissions are derived from role through a static role-to-permission mapping in
`app/domain/auth.py` (`tenant_role_permissions` and `platform_role_permissions`).

| Role | Scope | Permissions |
| --- | --- | --- |
| tenant `member` | tenant | `chat:ask` |
| tenant `admin` | tenant | `chat:ask`, `tenant:user_manage`, `tenant:role_grant`, `tenant:manage` |
| `expert` | platform | `kb:create/read/update/delete`, `doc:upload/delete/reindex`, `skill:write`, `skill:read`, `platform:kb_publish_official` |
| `operator` | platform | `platform:user_manage`, `platform:role_grant`, `system:ops`, `kb:read`, `skill:read`, `platform:entitlement_grant` |
| `admin` | platform | superset of `expert` + `operator` + `platform:tenant_manage` |

Notes:

- Tenant roles hold no `kb:*` or `doc:*` permissions. Tenant consumption is via
  `chat:ask`, which forwards the active tenant to ngent/upstream.
- `platform:entitlement_grant` is the forward-looking permission reserved for the
  entitlement feature (deferred — see §10).

## 4. Identity Context

Permission checks are based on an explicit active context.

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

The API does not infer platform permissions from tenant roles, or tenant
permissions from platform roles.

Implementation:

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

## 5. Token Claims

Access token claims:

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

A single global claim such as `{"role": "admin"}` is avoided because it cannot
distinguish platform admin from tenant admin.

## 6. Registration and Login

Tenant self-registration (`POST /api/v1/users/register`):

1. Create `users` row.
2. Create default `personal` tenant.
3. Insert `tenant_members` row with role `admin`.
4. Issue token with user identity.

Team tenant creation:

1. Existing user creates a `team` tenant.
2. Creator becomes tenant `admin`.
3. Invited users become `member` unless explicitly promoted.

Platform user creation (`POST /api/v1/users/platform`):

1. Platform admin/operator creates a platform user and issues an activation token.
2. Platform roles are assigned during creation or through role-grant APIs.
3. The invited platform user activates the account via
   `POST /api/v1/users/platform/activate` with the token and sets a password.
4. Optional: also create a personal tenant if this user needs product usage.

Platform users are not created through public registration. Login authenticates
only the user identity; the active tenant or platform context is selected after
login or encoded explicitly in request context.

### Platform users using the product

Platform users may also use the product like normal users:

- Keep one login identity in `users`.
- Give the user platform roles through `platform_user_roles`.
- Also create or join a tenant through `tenant_members` for normal product usage.
- For default single-user usage, create a `personal` tenant and add the user as
  tenant `admin`.

This keeps product data isolation and platform administration separate.

## 7. Authorization Rules

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
- Platform resources such as skills and platform expert assets are not owned by
  customer tenants.
- Platform/official endpoints intentionally do not send an upstream tenant id.

Support or impersonation access:

- Platform users do not silently bypass tenant isolation.
- If support access is needed, it must be modeled as an explicit
  support/impersonation flow with audit logs.

## 8. Technical Specification

### 8.1 Database tables

- `users`
- `tenants`
- `tenant_members`
- `platform_user_roles`
- `refresh_tokens` (user-scoped)
- `platform_activation_tokens`

The schema lives in `001_auth.sql`.

### 8.2 Domain model

Two role enums in `app/domain/auth.py`:

- `TenantRole`: `admin`, `member`
- `PlatformRole`: `admin`, `expert`, `operator`

One principal object carries both the optional tenant context and the platform
roles.

### 8.3 Authorization dependencies

- `require_tenant_principal`
- `require_platform_principal`
- `require_tenant_permission`
- `require_platform_permission`

Tenant product APIs require `x-tenant-id`; platform APIs do not.

### 8.4 API scope mapping

Tenant-scoped APIs:

- chat APIs
- model list APIs
- tenant user/member management

Platform-scoped APIs:

- knowledge base CRUD (`/api/v1/knowledge-bases`)
- document APIs (`/api/v1/documents`)
- upload APIs (`/api/v1/uploads`)
- skill publish/update/delete
- official knowledge base publish
- platform user creation and role grants
- ops metrics
- platform user/role management

Shared authenticated APIs:

- skill browse/read accepts any authenticated user for now.

## 9. RBAC Safety Rules

- `DELETE /api/v1/rbac/tenant/users/{user_id}` removes a tenant member.
- `DELETE /api/v1/rbac/platform/users/{user_id}/roles/{role}` revokes a
  platform role.
- Tenant admin demotion/removal is blocked when it would remove the last tenant
  admin (`409 TENANT_LAST_ADMIN`).
- Platform admin revocation is blocked when it would remove the last platform
  admin (`409 PLATFORM_LAST_ADMIN`).
- Last-admin checks run inside write transactions with membership/role locking
  where supported by the database.

## 10. Capability Ownership and Domain Impact

Skills:

- Skills are platform-managed assets.
- Creating, updating and deleting skills requires platform permission
  (`skill:write`).
- Tenant users may browse or use published skills only if the product exposes
  that capability.

Experts:

- Platform experts and their official knowledge/skills are provider-owned.
- Tenant users consume experts through product workflows.
- Tenant-specific experts should be modeled separately if the product later
  supports customer-created expert agents.

Knowledge bases:

- Knowledge bases and their documents are platform-provided capabilities,
  authored and managed by platform `expert`/`admin` through platform-scoped
  endpoints (`/api/v1/knowledge-bases`, `/api/v1/documents`, `/api/v1/uploads`),
  which require `kb:*` / `doc:*` platform permissions and are not tenant-scoped.
- Tenants do not own or author knowledge bases. They consume them through product
  workflows (chat), which forward the active tenant to the upstream runtime.

## 11. Deferred Decisions

Coupled to the `experts` entity (Phase 2):

- Entitlement mechanism. "Which users/tenants may use which capabilities" needs a
  table + endpoints + enforcement. `platform:entitlement_grant` is reserved for
  it. Deferred until the `experts` entity exists (an expert associates one
  knowledge base and a set of skills).
- Tenant consumption path for platform KBs. Today tenants consume via chat.
  Direct, entitlement-scoped read access for tenants (if the product needs it) is
  part of the entitlement work.
- `/official` overlap. With generic KB create now platform-scoped, revisit
  whether `POST /knowledge-bases/official` (forces `visibility=official_public`)
  should remain a separate endpoint or fold into create with an explicit
  visibility field.

Product flows:

- Team tenant creation and email-based tenant invitations are separate product
  flows.
- Tenant disablement is not yet modeled in authorization; add tenant status
  checks when a tenant-disable flow exists.

Open design decisions:

- Whether the API should add an explicit support/impersonation context that can
  access tenant resources with audit logs.
- Whether platform roles should keep using the static role-to-permission mapping
  or move to a database-backed role-permission table.
- Whether tenant `member` needs finer product permissions beyond the initial
  `admin/member` split.
