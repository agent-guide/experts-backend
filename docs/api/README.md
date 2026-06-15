# Amazon Experts Backend API

Base path:

```text
/api/v1
```

Health check:

```text
GET /health
```

Swagger UI is available when the FastAPI app is running:

```text
GET /docs
```

The generated OpenAPI schema is also checked in at:

```text
docs/api/openapi.json
```

## Authentication

Most APIs require:

```text
Authorization: Bearer <accessToken>
```

Tenant-scoped product APIs also require:

```text
x-tenant-id: <tenant_id>
```

Platform-scoped APIs do not require `x-tenant-id`; they require current platform
roles and derived permissions.

For authenticated requests, the API decodes the access token and then reloads
the user, tenant roles and platform roles from the database before checking
permissions. Role changes, tenant membership removal and user disablement
therefore apply immediately even when an existing access token has not expired.

## Permission Scopes

Tenant permissions are resolved from `tenant_members.role`:

- `admin`
- `member`

Platform permissions are resolved from `platform_user_roles.role`:

- `admin`
- `expert`
- `operator`

See [auth.md](./auth.md) for token details and [rbac.md](./rbac.md) for
permission management.

Access tokens contain roles only. Expanded permission lists are never used as
token claims; they are derived server-side from the current role mapping.

## API Groups

- [Auth](./auth.md)
- [Users](./users.md)
- [Tenants](./tenants.md)
- [RBAC](./rbac.md)
- [Knowledge Bases](./knowledge-bases.md) (platform-owned; minimal shape, single `status`)
- [Documents](./documents.md) (nested under a knowledge base; MinIO direct upload)
- [Experts](./experts.md) (platform-owned expert categories and experts)
- [Build](./builds.md) (Phase 2 placeholder)
- [Chat](./chat.md)
- [Skills](./skills.md)
- [Models and Ops](./models-ops.md)

Knowledge base storage, MinIO direct upload, and build decoupling are described
in [Knowledge Base Storage and Build Design](../KNOWLEDGE_BASE_STORAGE_AND_BUILD_DESIGN.md).

## Response Format

Successful responses generally return JSON, except:

- `204` responses have no body.
- `GET /skills/{slug}/file` returns `text/markdown`.
- `POST /chat/sessions/{session_id}/turns` and `GET /chat/turns/{turn_id}/events`
  return `text/event-stream`.

Errors are raised through the project API error handler and include an error
code and message.
