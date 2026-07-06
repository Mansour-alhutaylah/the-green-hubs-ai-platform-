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
