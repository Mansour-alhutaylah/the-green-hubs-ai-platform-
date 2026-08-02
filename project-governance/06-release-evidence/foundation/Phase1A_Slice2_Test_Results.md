# Phase 1A Slice 2 Test Results

Evidence IDs: **EV-REL-CID-01**, **EV-SEC-LOG-01**, **EV-CI-02**  
Date: 2026-08-02 (Asia/Riyadh)  
Starting commit: `3e54a87b0ba295adb5e0109faafc6b12c30a46b3`

## Focused verification

Command:

```text
.\.venv\Scripts\python.exe -m pytest tests/core/test_request_context.py tests/api/test_correlation_id.py tests/api/test_exception_handling.py -q
```

Result: **28 passed, 0 failed, 0 skipped in 2.82s**.

Verified behavior includes generated and preserved UUIDs, unsafe replacement,
no reflection/logging of invalid values, one response header, 2xx/401/403/404/
422/controlled-error/sanitized-500 coverage, CORS exposure, no fabricated
CORS, matching application/error/completion log correlation, trusted user and
organization enrichment, nullable organization, spoofing resistance,
request-state synchronization, query/header/cookie log safety, outside-request
reset, and deterministic concurrent-request isolation.

The focused command also reran the unchanged Slice 1 direct exception tests for
sanitized 500, CORS on 500, no false CORS without Origin, controlled `AppError`,
and FastAPI 422 behavior.

## Safe backend regression

Command:

```text
.\.venv\Scripts\python.exe -m pytest -m "not integration" --deselect tests/test_health.py::test_health_db_reports_a_status -q
```

Result: **484 passed, 148 deselected, 0 failed, 0 skipped in 12.71s**.

## Static validation

```text
.\.venv\Scripts\python.exe -m ruff check app tests scripts
All checks passed!

.\.venv\Scripts\python.exe -m mypy app
Success: no issues found in 106 source files
```

## Integration regression

Local guarded result: **NOT RUN — Docker unavailable**. The `docker` command
was not installed or available on PATH. No shared database was contacted and
no guard was bypassed. No disposable resource was created.

Hosted `backend-integration`: **PENDING**.

## Hosted CI

- `backend`: **PENDING**
- `backend-integration`: **PENDING**
- `frontend`: **PENDING** (frontend source and shared TypeScript tooling were untouched)
- Run ID/URL: **PENDING**

No hosted success is claimed until all required jobs finish successfully.
