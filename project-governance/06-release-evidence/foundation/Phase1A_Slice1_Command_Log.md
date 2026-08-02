# Phase 1A Slice 1 Command Log

Evidence IDs: **EV-TEST-DB-01**, **EV-TEST-DB-02**, **EV-TEST-DB-03**, **EV-CI-01**

Execution date: 2026-08-02 (Asia/Riyadh)

Repository: `C:\Users\ABOALI\Desktop\the-green-hubs-ai-platform-`

## Starting state

- Branch: `chore/fnd-phase1a-isolated-test-db`
- Starting commit: `80dee2badd1e1f190d6fd66881729f4e3bb3c809`
- Tracked working tree: clean; unrelated untracked `.claude/` was present and left untouched.
- Conflict/index checks: no unmerged entries and no merge, rebase, or cherry-pick operation.
- Docker: client/server 29.6.2, Docker Desktop 4.84.0, Compose 5.3.1.
- Containers at preflight: only a stopped `hello-world` container; no root API Compose container existed.

The required governance files were read before editing. `backend/.env` was not opened, displayed, modified, mounted, or staged. The root `docker-compose.yml` was inspected only to confirm that it is unsafe for this task; it was not changed or run.

## Commands and results

Unless another directory is stated, commands ran from the repository root. The synthetic URL assignment is intentionally credential-redacted in this record; the database, host, and port remain recorded.

### Preflight

```powershell
$env:DEBUG = "false"
git status --short
git branch --show-current
git rev-parse HEAD
git branch -vv
git diff --stat
git diff --check
git diff --cached --name-status
git ls-files -u
docker version
docker compose version
docker info
docker ps -a
```

Result: expected branch, clean tracked tree, no operation/conflict, Docker Engine healthy, and old API container stopped/absent.

### Image and isolated service

Docker CLI discovery required adding `C:\Program Files\Docker\Docker\resources\bin` to `PATH` for the current PowerShell process only.

```powershell
docker pull pgvector/pgvector:pg16
docker image inspect pgvector/pgvector:pg16 --format '{{index .RepoDigests 0}}'
docker compose -f docker-compose.test.yml config --quiet
docker compose -f docker-compose.test.yml up -d
docker compose -f docker-compose.test.yml ps
```

Result: `green-hubs-slice1-test-postgres` became `healthy` on `127.0.0.1:55432` using the pinned digest recorded in the safety evidence.

### Marker, migrations, and database proof

The following process-only variables were set: `DEBUG=false`, `GH_INTEGRATION_TEST_MODE=true`, `ENVIRONMENT=test`, and `GH_TEST_DATABASE_URL=<synthetic local credentials redacted>@127.0.0.1:55432/green_hubs_test`.

```powershell
backend\.venv\Scripts\python.exe backend\scripts\test_db.py migrate
backend\.venv\Scripts\python.exe backend\scripts\test_db.py verify
backend\.venv\Scripts\python.exe backend\scripts\test_db.py bootstrap-marker
```

Result: all eight historical migrations applied in order; marker verified; PostgreSQL 16.14; pgvector 0.8.6; Alembic head `da0298a9c722`; 12 public tables including marker and Alembic metadata. The later bootstrap command verified CI-style marker creation is idempotent.

### Collection and integration execution

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_integration_tests.py collect
backend\.venv\Scripts\python.exe backend\scripts\run_integration_tests.py run
```

Collection result: 147 integration cases selected from 609 total, 462 deselected; exactly 144 were the pre-existing integration cases and three were new environment proofs.

First execution result: 146 passed and one new pgvector proof failed because cosine distance for an all-zero vector is mathematically `NaN`. No historical test failed. The proof input was corrected to a nonzero 1536-dimensional vector and verified alone:

```powershell
backend\.venv\Scripts\python.exe -m pytest -c backend\pytest.ini backend\tests\integration\test_isolated_environment.py::test_pgvector_accepts_expected_embedding_dimension -m integration -q
```

Result: 1 passed. The complete official run was then repeated and produced 147 passed, zero failed/errors/skipped, 462 deselected, in 201.46 seconds.

### Negative and guard verification

```powershell
backend\.venv\Scripts\python.exe -m pytest tests\test_db_guard.py -q
```

Result: 14 passed. A direct integration collection with explicit mode but with `GH_TEST_DATABASE_URL` removed failed before collection with the redacted error `GH_TEST_DATABASE_URL is required; configured application databases are never used.` The unit suite also directly proved that zero collection and an all-skipped outcome are fatal.

### Regression and static analysis

Working directory: `...\backend`.

```powershell
$env:DEBUG = "false"
.\.venv\Scripts\python.exe -m pytest -m "not integration" --deselect tests/test_health.py::test_health_db_reports_a_status -q
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m ruff check scripts
.\.venv\Scripts\python.exe -m mypy app
```

An initial regression attempt inherited stale `DEBUG=release` in its new PowerShell process and stopped during Pydantic collection. No test executed. Setting `DEBUG=false` for that process, as required by the preflight, produced the final result: 461 passed and 148 deselected in 12.33 seconds. Ruff passed for app, tests, and scripts. MyPy passed for 105 source files.

### Commits before evidence

```text
42ba0197d7cfa939a387c8200d74386c8d0b2707  test(infra): add isolated PostgreSQL pgvector test environment
090ae91bb4dda50dc558a69cf1e09d4396daa844  ci(backend): run integration tests against isolated database
```

## Hosted status at evidence creation

Hosted CI had not started because the branch had not yet been pushed. This is not recorded as a pass. Push and hosted-run status must be appended after the remote operation.

## Safe teardown

```powershell
docker compose -f docker-compose.test.yml down -v
```

This command is scoped by the test Compose project and removes only the Slice 1 container, network, and disposable volume. It does not remove unrelated Docker resources or the pinned image.

Final result: completed successfully. Follow-up project-scoped container, volume-label, and network-label listings were empty. The unrelated stopped `hello-world` container remained untouched.
