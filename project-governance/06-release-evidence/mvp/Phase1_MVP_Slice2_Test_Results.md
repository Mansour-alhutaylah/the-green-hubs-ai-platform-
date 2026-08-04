# Phase 1 MVP Slice 2 Test Results

Evidence IDs: **EV-SEC-01**, **EV-CI-04**

Date: 2026-08-04 (Asia/Riyadh)

Branch: `feat/mvp-server-side-authorization`

Starting commit: `e45be9eacc9338152843de698268ed15daf0d8a7`

Local interpreter: Python 3.14.3. Hosted CI uses Python 3.12; the gap is why
hosted `backend` remains the controlling static-analysis evidence.

Node v24.13.1, npm 11.8.0. Ruff 0.15.20.

## Slice 1 gate, verified before any edit

| Check | Result |
|---|---|
| `git merge-base --is-ancestor 69b1cc7c... main` | **Ancestor — Slice 1 is merged** |
| Merge commit | `e45be9eacc9338152843de698268ed15daf0d8a7` |
| Merge subject | `Merge pull request #5 from Mansour-alhutaylah/feat/mvp-canonical-architecture-registry` |
| `main` vs `origin/main` | Identical; `0 0` ahead/behind |
| Slice 1 files on `main` | All four `app/domain/architecture/*` and all three architecture test modules present |
| Working tree | Clean; no untracked files; no interrupted Git operation |

Hosted CI for the merge commit was reported by the operator through the GitHub
UI as **3 / 3 successful**. GitHub CLI is not installed and no token is present,
so run IDs and job IDs could not be retrieved. **No run ID has been invented.**

## Baseline before any edit

Measured on unmodified `main` at `e45be9e`.

| Check | Command | Result |
|---|---|---|
| Backend | `python -m pytest -m "not integration" -q` | **604 passed, 147 deselected, 0 failed in 26.32s** |
| Ruff 0.15.20 | `ruff check .` | **All checks passed** |
| MyPy | `mypy app` | **Success: no issues found in 110 source files** |
| App import | `python -c "import app.main"` | **IMPORT OK** |
| Frontend lint | `npm run lint` (oxlint) | **Pass, no findings** |
| Frontend typecheck | `npm run typecheck` | **Pass, no errors** |
| Frontend tests | `npm test` (vitest) | **FLAKY — see below** |
| Frontend build | `npm run build` | **Pass, `dist/` produced in 1.96s** |
| Integration | guarded runner | **NOT RUN — Docker unavailable** |
| Docker | `docker version` | **Not installed / not on PATH** |

**MyPy now executes.** The Windows Application Control block recorded during
Slice 1 is no longer present on this workstation.

### Frontend test flakiness — pre-existing, environmental

Four runs on the **unmodified** tree produced different results:

| Run | Result |
|---|---|
| 1 (`npm test`) | 5 files failed, 9 tests failed, 142 passed |
| 2 (`npm test`) | 1 file failed, 1 test failed, 150 passed |
| 3 (`--testTimeout=30000`) | 1 file failed, 1 test failed, 150 passed |
| 4 (`--testTimeout=30000`) | 4 files failed, 4 tests failed, 147 passed |

The failing set differs on every run and the failures are 5000 ms timeouts and
async render assertions, not deterministic logic failures. Reported vitest
overhead on this workstation is extreme (environment 205–258 s, import 103–146 s).
`git status --short` was empty throughout, so nothing in the tree changed
between runs.

Classification: **pre-existing workstation flakiness, unrelated to Slice 2.**
Slice 2 changes **zero** frontend files. Hosted `frontend` — reported green for
`e45be9e` — is the controlling evidence. This is a recorded limitation, not a
cleared result.

## After implementation

Same commands, on `feat/mvp-server-side-authorization`.

| Check | Command | Result |
|---|---|---|
| Focused — policy | `pytest tests/domain/security/test_permissions.py -q` | **33 passed in 0.25s** |
| Focused — API | `pytest tests/api/test_authorization.py -q` | **34 passed in 3.64s** |
| Full backend | `pytest -m "not integration" -q` | **671 passed, 147 deselected, 0 failed in 35.75s** |
| Ruff 0.15.20 | `ruff check .` | **All checks passed** |
| MyPy | `mypy app` | **Success: no issues found in 112 source files** |
| Diff hygiene | `git diff --check` | **No whitespace errors** |
| Integration | guarded runner | **NOT RUN LOCALLY — Docker unavailable** |

604 baseline + 67 new = **671**. No test was deleted, skipped, weakened or
marked xfail.

## Intermediate failure, and how it was resolved

The first run after binding permissions produced **23 failed, 581 passed**.

Cause: every failing test seeded its user with `role=None` — written when the
backend had no authorization at all — and each exercised a now-protected write
route. Deny-by-default refused them, which is the **correct** new behaviour.

Resolution: those fixtures were given a write-capable role so each test again
reaches the tenant or validation behaviour it exists to assert. **No assertion
was changed, relaxed or removed**, and role denial itself is now covered
explicitly by the new suite. `tests/api/test_organizations.py::test_create_authenticated_returns_403`
still asserts its original service-level detail message and still passes.

Files adjusted: `test_analysis.py`, `test_document_embeddings.py`,
`test_engagements.py`, `test_organizations.py`, and the four integration modules
listed below.

## Integration tests — static verification

Docker is unavailable, so the 147 guarded integration tests could not run
locally. They were inspected statically because four of them seeded `role=None`
and would otherwise have failed hosted `backend-integration`:

| File | Change |
|---|---|
| `test_engagements_integration.py` | `role=None` → `role="admin"` |
| `test_organizations_integration.py` | `role=None` → `role="admin"` |
| `test_analysis_integration.py` | `role=None` → `role="admin"` |
| `test_embedding_and_retrieval_integration.py` | `role=None` → `role="admin"` (two fixtures) |

The remaining integration modules already seeded `role="admin"`.

All 147 integration tests are **collected and imported** successfully during the
non-integration run, which proves the edits are syntactically and structurally
valid. Their runtime behaviour remains **unverified locally** and is delegated to
hosted `backend-integration`.

## Behaviour proven by the new tests

| # | Behaviour | Where |
|---|---|---|
| 1 | Every role has an explicit permission entry | `test_permissions.py` |
| 2 | Backend enum equals the `roles.ts` vocabulary | `test_permissions.py` |
| 3 | Missing role denies every permission | both files |
| 4 | Unknown role (`member`, `superuser`, `""`, `root`) denies | both files |
| 5 | Unknown permission denies even for `owner` | `test_permissions.py` |
| 6 | `viewer` holds nothing at all | `test_permissions.py` |
| 7 | No non-administrative role holds `organization.manage` | `test_permissions.py` |
| 8 | Policy mapping and permission sets are immutable | `test_permissions.py` |
| 9 | Evaluation is deterministic and opens no socket | `test_permissions.py` |
| 10 | Unauthenticated protected call → 401 | `test_authorization.py` |
| 11 | `viewer` upload → 403, service never reached | `test_authorization.py` |
| 12 | `editor`/`approver`/`admin`/`owner` upload → 201 | `test_authorization.py` |
| 13 | Non-administrative roles cannot update an organization | `test_authorization.py` |
| 14 | Body `role`/`permission`/`user_id`/`actor_id`/`organization_id` are inert | `test_authorization.py` |
| 15 | Forged `X-Role`, `X-User-Role`, `Role`, `X-Permission`, `X-Permissions` ignored | `test_authorization.py` |
| 16 | Injected filename and PDF body cannot grant permission | `test_authorization.py` |
| 17 | Denial leaks no role, permission, policy identifier or stack trace | `test_authorization.py` |
| 18 | `X-Correlation-ID` present on 401 and 403, caller value preserved | `test_authorization.py` |
| 19 | Health stays public; `/auth/me` and organization list still work for `viewer` | `test_authorization.py` |
| 20 | No route may require an uncatalogued permission; bindings cannot be dropped | `test_authorization.py` |

Existing correlation-ID, CORS, exception-handling, authentication and
tenant-isolation suites all remain green inside the 671.

## Limitations

1. **Integration tests unverified locally** — Docker absent. Delegated to hosted
   `backend-integration`.
2. **Frontend suite flaky locally** — pre-existing and environmental; Slice 2
   changes no frontend file. Delegated to hosted `frontend`.
3. **Local Python 3.14.3 vs CI 3.12** — hosted `backend` is controlling.
4. **Hosted CI not programmatically verifiable** — GitHub CLI absent, no token.
   Slice 1's 3 / 3 result is operator-verified through the GitHub UI; run IDs are
   unavailable and none has been invented.
