# Phase 1 MVP Slice 1 Test Results

Evidence IDs: **EV-ARC-CANON-01**, **EV-ARC-CAP-01**, **EV-CI-03**

Date: 2026-08-03 (Asia/Riyadh)

Starting commit: `01c769fe1a1c2b889bb0d4f9cb46a240b0442e8a`

Branch head at time of writing: `da400834739aec1f746a504e39e7ae34e5d1ef8e`

Local interpreter: Python 3.14.3 (`backend\.venv\Scripts\python.exe`).
Hosted CI uses Python 3.12; the version gap is why hosted `backend` is the
controlling static-analysis evidence for this slice.

## Baseline before any edit

| Check | Command | Result |
|---|---|---|
| Backend | `python -m pytest -m "not integration" -q` | **485 passed, 147 deselected, 0 failed in 18.34s** |
| Ruff 0.15.20 | `python -m ruff check .` | **All checks passed** |
| MyPy | `python -m mypy app` | **NOT EXECUTED** — environment block, see below |
| Frontend lint | `npm run lint` (oxlint) | **Pass, no findings** |
| Frontend typecheck | `npm run typecheck` (`tsc -b --noEmit`) | **Pass, no errors** |
| Frontend tests | `npm test` (vitest) | **27 files passed (27), 151 tests passed (151)** |
| Frontend build | `npm run build` | **Pass, `dist/` produced in 1.66s** |
| Docker | `docker version` / `docker compose version` / `docker info` | **Not installed / not on PATH** |

Node v24.13.1, npm 11.8.0.

No pre-existing failure was found. The frontend timeout in
`RoutedPageContent.test.tsx` reported by the Release 4 Port Assessment **did
not reproduce** in either full-suite run performed for this slice. No test file
was modified, no timeout was raised, and nothing was skipped.

## Focused verification

Command:

```text
.\.venv\Scripts\python.exe -m pytest tests/domain -q
```

Result: **119 passed, 0 failed, 0 skipped in 2.64s**.

Per file:

| File | Result |
|---|---|
| `tests/domain/architecture/test_registry.py` | 43 passed in 1.14s |
| `tests/domain/architecture/test_capability.py` | 52 passed in 1.11s |
| `tests/domain/architecture/test_forbidden_hub_code_source_guard.py` | 24 passed in 3.05s |

Verified behaviour includes: exactly twelve Intelligence Hubs; the code range
running IH-00 to IH-11; the exact canonical code set; exactly nineteen
operating hubs; no duplicate hub code; no operating hub owned by two hubs;
exactly six reported business lines with no silent seventh; IH-00 carrying no
reported line; every other hub mapping to a known line; the full hub-to-line
mapping matching the Blueprint; rejection of the retired twelfth-hub family
with the specific error type; rejection of unknown, empty, lower-case and
near-miss codes; forbidden and canonical sets being disjoint; frozen dataclass
instances and mutation-protected registry collections.

Capability behaviour verified: the four approved MVP domains recognised and
mapped to IH-02, IH-03, IH-04 and IH-07; case- and whitespace-insensitive
lookup; an approved MVP domain **not** treated as production; unbuilt and
unregistered domains reported unavailable with the not-yet-built message; no
action of any kind advertised for an unavailable domain; a Reference domain
declaring every action still offering none; an In Build or Production domain
offering exactly what it declares and nothing more; commercial activation not
implying technical readiness; results immutable.

Guard behaviour verified: repository roots resolve to real directories; more
than one hundred product files from both `backend` and `frontend` are actually
read; no retired code exists in active product source; forbidden registry
entries, navigation items and seed records are detected; every forbidden code
and the `IH12` / `ih-12` / `IH_12` / `IH 12` spelling variants are detected;
canonical and unrelated codes such as `IH-11`, `IH-1`, `IH-120` and
`BUILD-1234` are not flagged; test-only rejection literals in `__tests__`,
`tests/`, `*.test.*`, `*.spec.*`, `test_*` and `conftest.py` do not fail the
guard; generated, vendored and build directories and binary assets are not
scanned; a missing root is skipped rather than failing.

### Non-vacuity check

A temporary file `backend/app/_guard_probe_tmp.py` containing the forbidden
literal was created, the guard was run, and it failed with:

```text
AssertionError: backend\app\_guard_probe_tmp.py:1: HUB_CODES = ["IH-12"]
```

The probe file was deleted immediately. `git status --short` confirmed it left
no trace. It was never committed.

## Safe backend regression

Command:

```text
.\.venv\Scripts\python.exe -m pytest -m "not integration" -q
```

Result: **604 passed, 147 deselected, 0 failed, 0 skipped in 16.87s**
(485 pre-existing + 119 new; no pre-existing test changed behaviour).

Application import was additionally confirmed with
`from app.main import app`, proving the new domain package introduces no
import cycle into the FastAPI application.

## Static validation

```text
.\.venv\Scripts\python.exe -m ruff check .
All checks passed!
```

MyPy: **NOT EXECUTED — environment block, not a code defect.**

```text
.\.venv\Scripts\python.exe -m mypy app
ImportError: DLL load failed while importing base64:
An Application Control policy has blocked this file.
```

Isolated with three probes: `import base64` from the standard library succeeds;
`import mypy.ipc` and `import mypy.build` both fail identically. A Windows
Application Control policy blocks the mypyc-compiled `mypy.ipc` extension in
this workstation image. Invocation via `python -m mypy` and via the console
script both fail. Nothing was installed, downgraded or reconfigured to work
around it. Hosted `backend` on Python 3.12/Linux is the required MyPy evidence.

## Integration regression

Local guarded result: **NOT RUN — Docker unavailable.** `docker`, `docker
compose` and `docker info` are not installed or not on PATH. No shared
Supabase or other shared database was contacted, no guard was bypassed, and no
disposable container, network or volume was created, so there was nothing to
tear down.

Slice 1 adds no database, repository, session or migration code path, so it
carries no integration surface of its own. Hosted `backend-integration` remains
the required evidence.

## Frontend regression

Re-run after the backend change, on the same commit as the backend results:

| Check | Result |
|---|---|
| `npm run lint` | Pass, no findings |
| `npm run typecheck` | Pass, no errors |
| `npm test` | **27 files passed (27), 151 tests passed (151)** in 64.37s |
| `npm run build` | Pass, `dist/` produced in 1.72s |

No frontend file was modified in this slice.

## Hosted CI

**NOT VERIFIED — requires manual confirmation.**

GitHub CLI is not installed on this workstation (`gh` is absent from PATH and
from the standard Program Files, Chocolatey and Scoop locations), and the
repository is private, so the unauthenticated REST API returns HTTP 404 for
both the repository and its workflow runs. No run ID, job ID or conclusion can
therefore be recorded here.

The branch `feat/mvp-canonical-architecture-registry` was pushed successfully
at `da400834739aec1f746a504e39e7ae34e5d1ef8e`, which triggers the `push`
workflow. The three required jobs — `backend`, `backend-integration` and
`frontend` — must be confirmed manually before this slice is treated as
verified:

<https://github.com/Mansour-alhutaylah/the-green-hubs-ai-platform-/actions>

No run ID or conclusion has been assumed or invented. A pending check is not a
passed check.
