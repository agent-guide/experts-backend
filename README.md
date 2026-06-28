# Amazon Experts Backend

Python 3 + FastAPI backend scaffold for the Amazon experts API.

The new service keeps the existing API shape where useful, while owning the
control-plane data model locally:

- Knowledge bases, documents, uploads and object storage: implemented in this service.
- Chat/session execution: agent-gateway ACP data plane.
- Skill management: DB metadata plus local or MinIO-backed skill file storage.
- Multi-tenant auth and common APIs: implemented in this service.

## Run

```bash
cd amazon-experts-backend
python3 -m venv .venv
. .venv/bin/activate    
.\.venv\Scripts\Activate
pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 15000
```

OpenAPI docs are then served at `http://127.0.0.1:15000/docs`.

All runtime configuration is read from environment variables prefixed with `EXPERT_`,
or from the project root `.env` file (see `app/core/config.py`). Copy `.env.example` to
`.env` to get started. Files such as `.env.local` and `.env.remote` are configuration
copies only and are not loaded automatically.

## Configuration

### Choosing the database: SQLite vs PostgreSQL

The backend is selected automatically from the **URL scheme** of
`EXPERT_DATABASE_URL` — there is no separate toggle (see `app/db.py`).

- SQLite (default, local/tests) — the URL starts with `sqlite:///`:

  ```text
  EXPERT_DATABASE_URL=sqlite:///./.data/amazon-experts-backend.sqlite3
  ```

  Use `sqlite:///:memory:` for an in-memory database.

- PostgreSQL (production) — the URL starts with `postgresql://` (or `postgres://`):

  ```text
  EXPERT_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/expert
  ```

  PostgreSQL requires the `psycopg` dependency; without it the service fails at
  startup with `PostgreSQL requires the psycopg dependency.`

Both backends share the same schema files. On startup (when
`EXPERT_DATABASE_AUTO_MIGRATE=true`) the service applies every
`*.sql` file under `amazon-experts-backend/infra/sql`; override the location with
`EXPERT_DATABASE_SCHEMA_DIR`. The runner re-runs all SQL on each boot and
relies on `if not exists` idempotency. The SQL files are written in PostgreSQL
syntax; for SQLite, `app/db.py` rewrites Postgres-only constructs (`jsonb`,
`timestamptz`, `now()`, ...) into SQLite-compatible forms on the fly.

### Choosing object storage: local filesystem vs MinIO

Documents, library files and skill packages use the same object storage backend.
The backend is selected by `EXPERT_OBJECT_STORAGE_BACKEND` (default `local`).

- Local filesystem (default):

  ```text
  EXPERT_OBJECT_STORAGE_BACKEND=local
  EXPERT_OBJECT_STORAGE_LOCAL_DIR=./.data/objects
  EXPERT_OBJECT_STORAGE_MAX_UPLOAD_BYTES=104857600
  ```

- MinIO object storage — recommended for production. Set the backend to `minio`
  and provide the connection settings:

  ```text
  EXPERT_OBJECT_STORAGE_BACKEND=minio
  EXPERT_MINIO_ENDPOINT=127.0.0.1:9000
  EXPERT_MINIO_ACCESS_KEY=minioadmin
  EXPERT_MINIO_SECRET_KEY=minioadmin
  EXPERT_MINIO_BUCKET=expert-files
  EXPERT_MINIO_SECURE=false
  ```

Skills always use the `skills/{slug}/...` object-key prefix inside the shared
object storage backend. The old `EXPERT_SKILL_STORAGE_*` settings are no
longer read. Existing deployments that stored skill objects in a separate bucket
such as `expert-skills` should manually copy the old `skills/...` objects into
the configured shared bucket before switching production to `minio`.

## Auth

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

Register/login use `EXPERT_DEFAULT_TENANT_ID`, which defaults to
`tenant_default` to match the current Expert project seed data. Production
deployments must set a strong `EXPERT_JWT_SECRET`.

RBAC permissions are resolved from tenant roles (`admin`, `member`) and platform
roles (`admin`, `expert`, `operator`).

Skill endpoints (file storage backend is configured above):

- `POST /api/v1/skills`
- `GET /api/v1/skills`
- `GET /api/v1/skills/{slug}`
- `PUT /api/v1/skills/{slug}`
- `DELETE /api/v1/skills/{slug}?delete_files=true`
- `GET /api/v1/skills/{slug}/file?path=SKILL.md`

## Current Status

This is a framework scaffold. It exposes the API modules and dependency
boundaries. ACP integration is intentionally a thin adapter for future hardening.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
## Windows Quick Start

Run the following commands from the project root:

```bat
cd /d D:\my_python\maiyun\amazon-experts-backend
py -m venv .venv
```

Activate the virtual environment in `cmd`:

```bat
.venv\Scripts\activate
```

Activate the virtual environment in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation because of the execution policy, allow scripts for
the current shell session only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

After activation, the prompt should start with `(.venv)`.

Install the project dependencies:

```bat
python -m pip install --upgrade pip
python -m pip install -e .
```

Install development dependencies when running tests or lint locally:

```bat
python -m pip install -e ".[dev]"
```

Create a local environment file:

```bat
copy .env.example .env
```

Start the FastAPI development server:

```bat
python -m uvicorn app.main:app --reload
```

Run the test suite:

```bat
python -m pytest tests/test_app.py -q
```
