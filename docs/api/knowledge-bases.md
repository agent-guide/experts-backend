# Knowledge Bases API

Base path:

```text
/api/v1/knowledge-bases
```

Knowledge bases are **platform-authored resources**. They have **no tenant relationship**
at all: they carry no `tenant_id`, tenant roles hold no `kb:*` / `doc:*` permissions, and
tenants never own or operate them. Tenants consume knowledge bases only through product
workflows (chat).

All endpoints require a platform role and platform permissions:

```text
Authorization: Bearer <accessToken>
```

No `x-tenant-id` header is used. Metadata is stored in this project's database.
See [Knowledge Base Storage and Build Design](../KNOWLEDGE_BASE_STORAGE_AND_BUILD_DESIGN.md).

## Resource shape

```json
{
  "id": "kb_123",
  "ownerUserId": "user_123",
  "ownerUserName": "Jane Expert",
  "name": "Amazon Reviews",
  "description": "Review analysis corpus",
  "status": "active",
  "metadata": {},
  "createdAt": "2026-06-03T10:00:00Z",
  "updatedAt": "2026-06-03T10:00:00Z"
}
```

The shape is intentionally minimal:

- `status` is the only lifecycle field. `active` means usable, `archived` means retired
  (writes are rejected with `409 KB_ARCHIVED`). Build readiness is **not** modeled yet —
  build is deferred, and a single status avoids the "which status do I check?" problem.
- There is **no** `scope` / `visibility`. All knowledge bases are platform-owned; access is
  decided purely by the platform permission on each route. Any future sharing rules belong in
  a dedicated table, not in this business table.
- `ownerUserId` is **creator attribution only**, not an access-control input.
- `ownerUserName` is the current display name for `ownerUserId`; it may be `null` if the
  owner user is absent.

## Authorization

Who may act is decided entirely by the platform permission on the route (`kb:*` / `doc:*`).
There is no ownership or visibility check: any platform user holding the relevant permission
may operate any knowledge base. The only resource-level rule is the lifecycle one — an
`archived` knowledge base rejects writes (`409 KB_ARCHIVED`).

This is not tenant isolation — tenant principals cannot reach these routes at all.

## POST /

Create a knowledge base. Required permission: `kb:create`.

Request:

```json
{
  "name": "Amazon Reviews",
  "description": "Review analysis corpus",
  "metadata": {}
}
```

Response: `201 Created` with the resource shape above (`status` defaults to `active`).

## GET /

List active knowledge bases. Required permission: `kb:read`.

Response:

```json
{
  "items": [
    {
      "id": "kb_123",
      "ownerUserId": "user_123",
      "ownerUserName": "Jane Expert",
      "...": "..."
    }
  ]
}
```

## GET /{knowledge_base_id}

Get a knowledge base. Required permission: `kb:read`. Response: the resource shape.

## PATCH /{knowledge_base_id}

Update a knowledge base. Required permission: `kb:update`. All fields optional:

```json
{
  "name": "Updated Name",
  "description": "Updated description",
  "metadata": {}
}
```

## DELETE /{knowledge_base_id}

Delete a knowledge base. Required permission: `kb:delete`. Response: `204 No Content`.

## Nested resources

- Documents: [docs API](./documents.md) under `/{knowledge_base_id}/docs/*`.
- Build: [build API](./builds.md) under `/{knowledge_base_id}/build` and `/builds/*`
  (Phase 2 placeholder — returns `501`).
