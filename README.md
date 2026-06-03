# Amazon Experts Backend

Python 3 + FastAPI backend scaffold for the Amazon experts API.

The new service keeps the existing API shape where useful, but delegates major
capabilities to external systems:

- Knowledge bases, documents, uploads and object storage: PageIndex adapter.
- Chat/session execution: ngent + Codex/ACP adapter.
- Skill management: DB metadata plus local or MinIO-backed skill file storage.
- Multi-tenant auth and common APIs: implemented in this service.

## Run

```bash
cd amazon-experts-backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 15000
```

By default the service uses sqlite for local/test runs:

```text
EXPERT_NEXT_DATABASE_URL=sqlite:///./.data/amazon-experts-backend.sqlite3
```

Set `EXPERT_NEXT_DATABASE_URL` to a PostgreSQL URL for production, for example:

```text
EXPERT_NEXT_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/expert
```

On startup the service applies schema files from `amazon-experts-backend/infra/sql`.
Override the location with `EXPERT_NEXT_DATABASE_SCHEMA_DIR` if needed.

Auth endpoints are backed by the shared auth tables:

- `POST /api/v1/users/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `POST /api/v1/users/platform/activate`
- `POST /api/v1/users/platform`
- `GET /api/v1/rbac/tenant/users`
- `POST /api/v1/rbac/tenant/users/{id}/roles`
- `POST /api/v1/rbac/platform/users/{id}/roles`

Register/login use `EXPERT_NEXT_DEFAULT_TENANT_ID`, which defaults to
`tenant_default` to match the current Expert project seed data. Production
deployments must set a strong `EXPERT_NEXT_JWT_SECRET`.

RBAC permissions are resolved from tenant roles (`admin`, `member`) and platform
roles (`admin`, `expert`, `operator`).

Skill files default to local storage:

```text
EXPERT_NEXT_SKILL_STORAGE_BACKEND=local
EXPERT_NEXT_SKILL_STORAGE_LOCAL_DIR=./.data/skills
EXPERT_NEXT_SKILL_STORAGE_PREFIX=skills
```

Set `EXPERT_NEXT_SKILL_STORAGE_BACKEND=minio` and provide the MinIO settings for
object storage:

```text
EXPERT_NEXT_MINIO_ENDPOINT=127.0.0.1:9000
EXPERT_NEXT_MINIO_ACCESS_KEY=minioadmin
EXPERT_NEXT_MINIO_SECRET_KEY=minioadmin
EXPERT_NEXT_MINIO_BUCKET=expert-skills
EXPERT_NEXT_MINIO_SECURE=false
```

Skill endpoints:

- `POST /api/v1/skills`
- `GET /api/v1/skills`
- `GET /api/v1/skills/{slug}`
- `PUT /api/v1/skills/{slug}`
- `DELETE /api/v1/skills/{slug}?delete_files=true`
- `GET /api/v1/skills/{slug}/file?path=SKILL.md`

OpenAPI docs:

```text
http://127.0.0.1:15000/docs
```

## Current Status

This is a framework scaffold. It exposes the API modules and dependency
boundaries. PageIndex and ngent integrations are intentionally thin adapters for
future hardening.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
