# Amazon Experts Backend

Python 3 + FastAPI backend scaffold for the Amazon experts API.

The new service keeps the existing API shape where useful, but delegates major
capabilities to external systems:

- Knowledge bases, documents, uploads and object storage: PageIndex adapter.
- Chat/session execution: ngent + Codex/ACP adapter.
- Skill management: Codex skills filesystem management.
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

On startup the service applies the shared schema files from the repository root
`infra/sql`. Override the location with `EXPERT_NEXT_DATABASE_SCHEMA_DIR` if the
backend is deployed outside the monorepo checkout.

Auth endpoints are backed by the shared auth tables:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/admin/activate`
- `POST /api/v1/admin/users/{id}/roles`

Register/login use `EXPERT_NEXT_DEFAULT_TENANT_ID`, which defaults to
`tenant_default` to match the current Expert project seed data. Production
deployments must set a strong `EXPERT_NEXT_JWT_SECRET`.

OpenAPI docs:

```text
http://127.0.0.1:15000/docs
```

## Current Status

This is a framework scaffold. It exposes the API modules and dependency
boundaries, but PageIndex/ngent/Codex skill integrations are intentionally thin
adapters for future hardening.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
