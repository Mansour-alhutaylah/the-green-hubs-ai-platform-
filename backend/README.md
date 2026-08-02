# The Green Hubs — Backend

Practical setup/run instructions for this backend. Project vision, architecture
principles, tech stack, security rules, and sprint workflow are owned by the
top-level `CLAUDE.md` — not repeated here.

**Current status:** foundation skeleton only (Sprint 1). No business logic,
authentication, or AI/RAG features are implemented yet.

## Prerequisites

- Python 3.14 (or 3.12/3.13 — see note below)
- A Supabase project (or any reachable Postgres instance with the `pgvector`
  extension available for later sprints)
- Docker Desktop, optional, only if you want to run the containerized build

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env           # then fill in your real Supabase DATABASE_URL
```

## Run

```bash
python run_backend.py
```

Open http://localhost:8000/api/v1/health and http://localhost:8000/api/v1/health/db.

> **Why not `uvicorn app.main:app --reload`?** On Python 3.14 + Windows,
> `--reload` spawns a subprocess in which `asyncio.run()` hangs — a bug this
> project's Hemaya reference implementation hit and worked around the same
> way. `--reload` is fine inside the Linux-based Docker container; it's just
> not used for local Windows development.

## Correlation IDs and RequestContext

Every HTTP response includes `X-Correlation-ID`. A client-supplied value is
accepted only when it is one canonical UUID; accepted values are normalized to
lowercase. Missing, malformed, duplicated, oversized, whitespace-containing,
or control-character-containing values are silently replaced with a generated
UUID4 and the unsafe value is never reflected or logged. CORS-enabled browser
clients may read the response header.

Application code may call `app.core.request_context.get_request_context()` to
read the immutable request-local `RequestContext`. It contains the correlation
ID and optional user and organization UUIDs. Authentication enriches those
identity fields only after the access-token identity and application profile
have been resolved on the server; client headers, query parameters, and bodies
are never identity sources. A profile without an organization keeps
`organization_id=None`.

Request logs can include `correlation_id`, `user_id`, and `organization_id`.
The request completion event logs only method, path without query string,
status, duration, and those safe identifiers. Authorization values, cookies,
request/response bodies, query strings, credentials, keys, and document
contents must not be logged.

RequestContext is an observability and future audit foundation. It is not an
authorization decision or a permanent audit record, and must never be used as
an authorization input.

## Migrations

```bash
alembic upgrade head
```

No migrations exist yet — `migrations/versions/` is currently empty. The
first migration lands with the first real entity in a later sprint.

## Tests / lint / types

```bash
pytest
ruff check .
mypy app
```

### Isolated integration tests

Integration tests must use the separate disposable PostgreSQL + pgvector
environment. Never use the root `docker-compose.yml`; it starts the API with
the development configuration and does not provide a test database.

From the repository root in PowerShell:

```powershell
$env:DEBUG = "false"
$env:GH_INTEGRATION_TEST_MODE = "true"
$env:ENVIRONMENT = "test"
$env:GH_TEST_DATABASE_URL = "postgresql+asyncpg://gh_test:gh_test_local_only@127.0.0.1:55432/green_hubs_test"
docker compose -f docker-compose.test.yml up -d
backend\.venv\Scripts\python.exe backend\scripts\test_db.py migrate
backend\.venv\Scripts\python.exe backend\scripts\test_db.py verify
backend\.venv\Scripts\python.exe backend\scripts\run_integration_tests.py all
docker compose -f docker-compose.test.yml down -v
```

The official runner rejects missing explicit test mode, unsafe database
names or hosts, absent marker/migration state, zero collected tests, zero
executed tests, and an all-skipped result. It removes external-provider
credentials from the pytest subprocess and uses a loopback-only auth issuer.
The test Compose file never loads `backend/.env`.

## Docker (optional)

```bash
docker compose build
docker compose up
```

The container reads `backend/.env` for its `DATABASE_URL` — there is no
local Postgres container; this connects straight to your Supabase project.

## Folder layout

```
app/
├── core/            cross-cutting: config, logging, exceptions
├── domain/          framework-agnostic entities + repository interfaces
├── infrastructure/   concrete DB/repository implementations + adapters
│   ├── db/           SQLAlchemy async session + ORM base
│   ├── repositories/ generic SQLAlchemy repository implementing domain interfaces
│   ├── security/     placeholder — future auth (see infrastructure/security/__init__.py)
│   ├── ai/           placeholder — future embeddings/RAG (see infrastructure/ai/__init__.py)
│   └── documents/    placeholder — future extraction/chunking (see infrastructure/documents/__init__.py)
├── services/         application/business logic, depends only on domain interfaces
├── api/              routers + FastAPI DI wiring
└── schemas/          Pydantic request/response DTOs
```

Future ESG features plug in by adding: a domain entity → an infrastructure
ORM model + repository → a service → a router, in that order.
