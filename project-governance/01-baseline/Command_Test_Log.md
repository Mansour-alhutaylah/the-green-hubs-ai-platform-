# SIP™ Phase 0 — Command and Test Execution Log

**Audit date:** 2026-08-01
**Auditor role:** Senior architect / backend + frontend reviewer / QA / security-aware technical auditor
**Repository:** `the-green-hubs-ai-platform-`
**Branch:** `feature/frontend-live-integration`
**HEAD:** `079efefda0093c84c04cf578ca57f76b52d47c89`
**Mode:** Read-only audit. No application code, migration, schema, secret, or database was modified.

---

## 1. Safety pre-check performed before any command was run

| Check | Finding | Consequence |
|---|---|---|
| Does `backend/.env` exist locally? | Yes (`backend/.env`, gitignored via `backend/.gitignore:4`). Contents were **never read or printed**. | `get_settings()` will populate `DATABASE_URL` at import time, so any test that resolves the `get_db` dependency would open a connection to the **shared Supabase instance**. |
| Which tests touch a real database? | All tests marked `pytest.mark.integration` (144 tests, every file matching `tests/**/test_*_integration.py` plus **all** of `tests/infrastructure/repositories/*`), plus `tests/test_health.py::test_health_db_reports_a_status`. | All excluded — see §4. |
| Do unit-level API tests touch the DB? | **No.** Each overrides `get_supabase_jwt_verifier`, `get_user_repository`, and the concrete service provider via `app.dependency_overrides`, e.g. `tests/api/test_documents_read.py:114-120`, `tests/api/test_analysis.py:120-126`, `tests/api/test_retrieval.py:64-70`. `get_db` is therefore never resolved and no connection is opened. | Safe to run. |
| Do any tests call a paid/external AI API? | **No.** `tests/infrastructure/ai/test_openai_llm_gateway.py:1-4` and `tests/infrastructure/ai/test_openai_embedding_provider.py` intercept every call via `httpx.MockTransport`. `tests/infrastructure/storage/test_supabase_document_storage.py:1-4` does the same for Supabase Storage. | Safe to run. No API cost incurred. |
| Do any tests upload to external services? | No. | Safe. |
| Frontend tests | `vitest` + `jsdom`, no network configured; `frontend/src/test/setupTests.ts`. | Safe. |
| Is `node_modules` already installed? | `frontend/node_modules` present (127 packages). No `npm install`/`npm ci` was run — dependency installation was explicitly out of scope. | No dependency change. |

---

## 2. Git and environment baseline commands

| # | Working directory | Command | Result |
|---|---|---|---|
| 1 | repo root | `git status --short` | 12 modified files, 2 untracked paths, 1 untracked `node_modules/`. Working tree **dirty** — see audit §2. |
| 2 | repo root | `git branch --show-current` | `feature/frontend-live-integration` |
| 3 | repo root | `git rev-parse HEAD` | `079efefda0093c84c04cf578ca57f76b52d47c89` |
| 4 | repo root | `git log --oneline --decorate -20` | 20 commits returned. `origin/main` = `670bb24`; HEAD is 6 commits ahead of `main`. |
| 5 | repo root | `git remote -v` | `origin  https://github.com/<owner-redacted>/the-green-hubs-ai-platform-.git` (fetch + push). No credentials embedded in the URL. |
| 6 | repo root | `git branch -vv` | 16 local branches. **`feature/frontend-live-integration` has no upstream** — all 6 commits exist only on this machine. |
| 7 | repo root | `git diff --stat main...HEAD` | 60 files changed, 6,306 insertions(+), 188 deletions(-) — all under `frontend/`. |
| 8 | repo root | `git diff --stat` (uncommitted) | 12 files, 491 insertions(+), 21 deletions(-) — OpenRouter credential resolution + document-read embedding scope. |
| 9 | repo root | `python --version` | `Python 3.14.3` |
| 10 | repo root | `node --version` | `v24.13.1` |
| 11 | repo root | `npm --version` | `11.8.0` |
| 12 | repo root | `git --version` | `git version 2.53.0.windows.1` |
| 13 | repo root | `git ls-files` | 385 tracked files (backend 178, frontend 204, `.github` 1, `.gitignore`, `docker-compose.yml`). |

---

## 3. Commands executed — build, lint, type, test

All timings are wall-clock as reported by the tool itself.

### Backend — `C:\...\the-green-hubs-ai-platform-\backend`

| # | Command | Outcome | Passed | Failed | Skipped / Deselected | Warnings |
|---|---|---|---|---|---|---|
| B1 | `.venv\Scripts\python.exe -m pytest --collect-only -q -m "not integration"` | **Collected** in 1.06s | — | 0 | 144 deselected (integration) | 0 |
| B2 | `.venv\Scripts\python.exe -m pytest -m "not integration" --deselect tests/test_health.py::test_health_db_reports_a_status -q` | **PASS** in 14.76s | **442** | **0** | **145 deselected** (144 integration + 1 live-DB health) | 0 |
| B3 | `.venv\Scripts\python.exe -m ruff check app tests` | **PASS** — `All checks passed!` (exit 0) | — | 0 | — | 0 |
| B4 | `.venv\Scripts\python.exe -m mypy app` | **PASS** — `Success: no issues found in 105 source files` (exit 0) | — | 0 | — | 0 |

Total non-integration backend tests collected: **443**. Executed: **442**. One deliberately deselected (see §4).

### Frontend — `C:\...\the-green-hubs-ai-platform-\frontend`

| # | Command | Outcome | Passed | Failed | Skipped | Warnings |
|---|---|---|---|---|---|---|
| F1 | `npm run lint` (`oxlint`) | **PASS** (exit 0), no diagnostics emitted | — | 0 | — | 0 |
| F2 | `npm run typecheck` (`tsc -b --noEmit`) | **PASS** (exit 0), no output | — | 0 | — | 0 |
| F3 | `npm test` (`vitest run`) | **PASS** in 51.82s | **151** tests / **27** files | **0** | **0** | 0 |
| F4 | `npm run build` (`tsc -b && vite build`) | **PASS** (exit 0), 2,091 modules, built in 1.55s | — | 0 | — | 0 |

Build output written to `frontend/dist/` — confirmed gitignored (`frontend/.gitignore`); `git status --short` after the build was byte-identical to before it, so the working tree was not polluted.

**Aggregate: 593 automated tests executed, 593 passed, 0 failed, 0 skipped. 145 backend tests deliberately not executed.**

---

## 4. Commands and tests deliberately NOT run, with reasons

| Item | Why it was not run |
|---|---|
| `pytest -m integration` (**144 tests**) | Every one requires a live `DATABASE_URL`. The only `DATABASE_URL` available on this machine is `backend/.env`, which points at the **shared Supabase Postgres instance**. These tests `INSERT` and `DELETE` real rows in `organizations`, `users`, `engagements`, `documents`, `document_chunks`, `document_chunk_embeddings`, `analysis_runs`, `analysis_source_references` (see the cleanup docstring at `tests/api/test_analysis_integration.py:10-13`). Running them would write to shared infrastructure — explicitly prohibited by the audit mandate. **Their pass/fail state is therefore UNVERIFIED in this audit.** |
| `tests/test_health.py::test_health_db_reports_a_status` (**1 test**) | Resolves the real `get_db` dependency and executes `SELECT 1` against the shared Supabase instance (`app/api/v1/health.py:35`). Read-only, but still contact with shared infrastructure — deselected on the conservative side. |
| `alembic upgrade head` / `alembic current` / any Alembic command | Would connect to, and potentially migrate, the shared remote database. Prohibited. Migration state on the shared instance is **UNVERIFIED**; the repository's own history was read statically instead. |
| `npm install` / `npm ci` / `pip install` | Dependency installation/upgrade explicitly prohibited. `frontend/node_modules` was already present, so no install was needed. |
| `docker compose up` | `docker-compose.yml:8` mounts `./backend/.env` into the container, i.e. would start a service bound to real Supabase credentials and the shared DB. Not run. |
| Any live call to OpenAI / OpenRouter | Prohibited (paid API). No command in this audit issues one; all AI tests use `httpx.MockTransport`. |
| Reading `backend/.env` | Prohibited. Only `backend/.env.example` and `frontend/.env.example` were read. No secret value appears anywhere in these documents. |
| Any `git` write operation (`commit`, `stash`, `reset`, `clean`, `checkout`, `merge`, `rebase`, `push`) | Prohibited. Only read-only plumbing/porcelain queries were issued. |
| Frontend end-to-end / golden-journey run | No E2E harness exists in the repository (no Playwright, Cypress, or equivalent in `frontend/package.json`). Nothing to run. |
| Dependency vulnerability scan (`npm audit`, `pip-audit`) | `pip-audit` is not installed and installing it is prohibited; `npm audit` contacts the public registry and would not have been actionable within a read-only audit. Recorded as a gap instead (see audit §10). |

---

## 5. Working-tree state at audit close

`git status --short` — identical to the state at audit open:

```
 M backend/.env.example
 M backend/app/api/deps.py
 M backend/app/core/config.py
 M backend/app/core/exceptions.py
 M backend/app/domain/repositories/document.py
 M backend/app/infrastructure/ai/openai_embedding_provider.py
 M backend/app/infrastructure/ai/openai_llm_gateway.py
 M backend/app/infrastructure/repositories/document.py
 M backend/app/services/document_read.py
 M backend/tests/infrastructure/ai/test_openai_embedding_provider.py
 M backend/tests/infrastructure/ai/test_openai_llm_gateway.py
 M backend/tests/services/test_document_read_service.py
?? backend/tests/core/
?? backend/tests/infrastructure/repositories/test_document_read_model_embedding_scope.py
?? node_modules/
```

**Confirmed: no tracked application file, migration, schema object, secret, or database row was modified by this audit.** The only filesystem writes made were the five new documents under `project-governance/`, plus the gitignored `frontend/dist/` produced by the sanctioned `npm run build`.
