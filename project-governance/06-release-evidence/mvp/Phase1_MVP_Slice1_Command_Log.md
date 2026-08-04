# Phase 1 MVP Slice 1 Command Log

Evidence IDs: **EV-ARC-CANON-01**, **EV-ARC-CAP-01**, **EV-CI-03**

Date: 2026-08-03 (Asia/Riyadh)

Branch: `feat/mvp-canonical-architecture-registry`

## Reference inputs

Supplied as conversation attachments and read in full: Founder Blueprint
MASTER v3.0.17 (PDF), `canon.mjs`, `slice.test.mjs`, the SIP Release 4 Thin
Slice README, and the Release 4 Port Assessment report.

The Release 4 Node/SQLite material was used as a **behavioural reference only**.
No `.mjs` file was copied, imported, merged or translated into this repository,
and no SQLite-specific detail was preserved. The Founder Blueprint is the
architectural source of truth.

Where the Port Assessment and the repository disagreed, the repository was
treated as authoritative. Two of its statements were re-verified and differ:
the safe backend suite measured **485 passed / 147 deselected** rather than
484 / 148, and the reported flaky frontend timeout did not reproduce.

## Repository gate

```text
git status --short
git branch --show-current
git rev-parse HEAD
git rev-parse origin/main
git rev-list --left-right --count origin/main...main
git log --oneline --decorate -20
git diff --name-status
git diff --cached --name-status
git ls-files -u
```

Result: working tree clean, no untracked file, no staged change, no unresolved
index entry, and no interrupted merge, rebase or cherry-pick (`.git/MERGE_HEAD`,
`REBASE_HEAD` and `CHERRY_PICK_HEAD` all absent). Local `main` and `origin/main`
both at `01c769fe1a1c2b889bb0d4f9cb46a240b0442e8a`, divergence `0 0`.
`backend/.env` was not read or printed.

Synchronization and branch creation:

```text
git fetch --prune origin
git branch --list "feat/mvp-canonical-architecture-registry"
git branch -r --list "origin/feat/mvp-canonical-architecture-registry"
git switch -c feat/mvp-canonical-architecture-registry
```

The target branch existed neither locally nor on the remote, so nothing was
overwritten. `main` was already identical to `origin/main` after fetch, so no
`git pull` was needed and none was run. `git switch main` was not required —
the session started on `main`.

No `reset`, `rebase`, `clean`, `checkout -- .`, `restore .`, `stash` or force
push was used at any point.

## Baseline validation

```text
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pytest -m "not integration" -q
.\.venv\Scripts\python.exe -m ruff --version
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy app
node --version ; npm --version
npm run lint ; npm run typecheck ; npm test ; npm run build
docker version ; docker compose version ; docker info
```

Results are recorded in `Phase1_MVP_Slice1_Test_Results.md`.

MyPy was isolated with three further probes before being classified as an
environment block rather than a code defect:

```text
.\.venv\Scripts\mypy.exe --version
.\.venv\Scripts\python.exe -c "import base64"
.\.venv\Scripts\python.exe -c "import mypy.ipc"
.\.venv\Scripts\python.exe -c "import mypy.build"
```

## Inspection

Read before editing: `backend/app` module tree, `backend/tests` tree,
`app/domain/entities/document.py`, `app/domain/entities/__init__.py`,
`app/core/exceptions.py`, `app/core/request_context.py`,
`app/schemas/document.py`, `backend/CLAUDE.md`, `backend/pytest.ini`,
`backend/requirements-dev.txt`, `backend/tests/conftest.py`,
`.github/workflows/ci.yml`, `frontend/package.json`,
`frontend/src/app/navigation/navConfig.ts`,
`frontend/src/app/navigation/routePaths.ts`,
`frontend/src/features/placeholders/pages/CarbonPage.tsx`, and the existing
Phase 1A evidence records.

Conformance checks run against the repository:

```text
git grep -n -i -E "IH-12|IH12" -- .
git grep -n -E "IH-[0-9]" -- .
git grep -n -i -E "\b(esg|carbon|energy|pmo)\b" -- backend/app
git grep -n "core.exceptions|from app.core" -- backend/app/domain
git grep -n "^from typing import|^from collections.abc import" -- backend/app
```

Findings: no hub code of any kind existed in the repository, so there was no
canonical conflict to remove and no UI change was required in this slice. No
domain-specific ESG, Carbon, Energy or PMO backend exists. The `domain/` layer
imported nothing from `app.core`; `ValidationError` was chosen as the error base
because the repository's own rule in `app/core/exceptions.py` requires domain
and service errors to subclass `AppError`. `typing` is the repository's
convention for `Mapping` and `Sequence`, and the new code follows it.

## Implementation validation

```text
.\.venv\Scripts\python.exe -m pytest tests/domain -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --diff app/domain/architecture tests/domain
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -m "not integration" -q
.\.venv\Scripts\python.exe -c "from app.main import app; ..."
```

`ruff format --check` reports 96 pre-existing files as unformatted, so the
repository is not `ruff format`-managed and CI runs `ruff check` only. Nothing
was reformatted. Two `@pytest.mark.parametrize` decorators in the new tests
were manually collapsed onto one line because they fit; no other file was
touched.

Guard non-vacuity probe:

```text
printf 'HUB_CODES = ["IH-12"]\n' > app/_guard_probe_tmp.py
.\.venv\Scripts\python.exe -m pytest tests/domain/architecture/test_forbidden_hub_code_source_guard.py::test_active_product_source_defines_no_retired_hub_code -q
rm -f app/_guard_probe_tmp.py
git status --short
```

The guard failed with the exact file and line, then the probe was removed and
the tree confirmed clean.

## Guarded integration attempt

```text
docker version
docker compose version
docker info
```

Result: not executed — `docker` is not installed or not on PATH. No container,
network or volume was created, so there was nothing to tear down. The
`docker-compose.test.yml` guard was not bypassed and no shared Supabase or
other shared database was contacted.

## Commits and remote operations

Explicit-path staging with a reviewed cached diff before each commit:

```text
git add backend/app/domain/architecture/
git diff --cached --name-status ; git diff --cached --stat ; git diff --cached --check
git diff --cached | grep -nE "IH[-_ ]?12"      # returned nothing, as required
git commit -F -

git add backend/tests/domain/
git diff --cached --name-status ; git diff --cached --stat ; git diff --cached --check
git commit -F -
```

```text
24432c3e60b076dbb6f1323ca0b747aee5598106 feat(architecture): add canonical SIP hub registry
da400834739aec1f746a504e39e7ae34e5d1ef8e test(architecture): enforce canonical domain rules
```

Push:

```text
git push -u origin feat/mvp-canonical-architecture-registry
```

Result: new remote branch created, upstream set to
`origin/feat/mvp-canonical-architecture-registry`. `main` was not pushed and
was not modified locally by this slice.

## Pull request

**NOT OPENED — tooling unavailable.**

GitHub CLI is not installed (`gh` absent from PATH, Program Files, Program
Files (x86), Chocolatey and Scoop locations), and the repository is private so
the unauthenticated REST API returns HTTP 404. No credential was extracted from
the Git credential helper to work around this, and no pull request URL, run ID
or job ID has been invented.

The branch is pushed and ready. The pull request must be opened manually:

<https://github.com/Mansour-alhutaylah/the-green-hubs-ai-platform-/pull/new/feat/mvp-canonical-architecture-registry>

Title: `feat(architecture): add canonical SIP hub registry`.
Base: `main`. Do not merge and do not enable auto-merge.
