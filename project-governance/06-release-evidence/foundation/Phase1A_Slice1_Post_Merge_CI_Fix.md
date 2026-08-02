# Phase 1A Slice 1 Post-Merge Backend Integration CI Fix

Verification date: 2026-08-02 (Asia/Riyadh)

## Scope and starting point

- Starting `main`: `44974a862c13afbac2703f41fa4b81d72847ed9d`.
- Fix branch: `fix/backend-integration-post-merge-ci`.
- Scope: the single failed post-merge `backend-integration` job; no product query, frontend source, migration, or root Compose behavior was changed.
- Pre-existing untracked `.claude/` was preserved and excluded from all work.

## Hosted history

The branch/PR history and the post-merge failure are deliberately recorded separately:

- Branch push run `30741498513`, commit `42d62581a5454ed0cc6e69c7d389726ff88b2ba4`: overall success.
- Pull-request run `30742083081`, commit `42d62581a5454ed0cc6e69c7d389726ff88b2ba4`: overall success.
- Post-merge `main` push run `30742167212`, commit `44974a862c13afbac2703f41fa4b81d72847ed9d`: overall failure.
  - `backend`: passed.
  - `frontend`: passed.
  - `backend-integration`: failed.
  - Failed step: `Run guarded integration tests`.
  - Failed test: `backend/tests/infrastructure/repositories/test_document_chunk_embedding_repository.py::test_search_returns_only_same_tenant_results_ordered_by_similarity`.
  - Exact assertion: expected the close chunk first, but the first result was the other chunk (`AssertionError` at line 485).
  - Result: 1 failed, 146 passed, 462 deselected in 44.34 seconds; process exit code 2 from the fail-closed integration gate.

Docker initialization and health, the disposable marker, all Alembic migrations, pgvector/head verification, guarded collection, and cleanup all passed. The failure occurred only during test execution.

## Root cause and classification

This was a flaky integration-test fixture caused by nondeterministic ordering of equal cosine distances.

The test helper expands a scalar into every vector coordinate. It used `[0.9] * 1536` for the expected close embedding, `[0.1] * 1536` for the supposed far embedding, and `[0.9] * 1536` for the query. The two stored embeddings are positive scalar multiples, so cosine distance treats them as the same direction. A direct pgvector calculation in the isolated database returned:

```text
close_similarity=1
far_similarity=1
distances_equal=true
```

The production query correctly orders by cosine distance. Because the fixture created a tie and the query has no product requirement to order tied scores, either row could be returned first. The unchanged test passed once locally (1 passed in 3.49 seconds) but failed in the hosted run, consistent with unspecified tied-row order.

Environment comparison found no causal database or dependency mismatch:

- Hosted: Python 3.12.13 on Linux; local: Python 3.14.3 on Windows.
- Both used asyncpg 0.31.0, pgvector Python package 0.5.0, SQLAlchemy 2.0.51, and pytest 9.1.1.
- Both used the digest-pinned pgvector PostgreSQL 16 image `sha256:a36250871de0833b8757561c72f2477ef1ddd1101afa4e617fb552e0de514c6b`.
- Local verification matched hosted PostgreSQL 16.14, pgvector 0.8.6, `en_US.utf8`, and `Etc/UTC`.
- CI was a `push` event, did not use pytest parallelism, and did not configure a dependency cache for this job.
- Both used explicit test mode and the loopback-only isolated `green_hubs_test` database.

## Fix

Only `backend/tests/infrastructure/repositories/test_document_chunk_embedding_repository.py` changed. The synthetic far embedding changed from `_vector(0.1)` to `_vector(-0.1)`, giving it the opposite direction and therefore a distinct cosine score. The production retrieval query was not changed. No retry, sleep, skip, xfail, or tie-breaking behavior was added.

## Local verification

- Isolated database marker: verified.
- Migrations: all eight historical migrations applied; Alembic head `da0298a9c722`.
- Database: PostgreSQL 16.14; pgvector 0.8.6; 12 public tables.
- Affected test after the fix: 20 independent pytest invocations, 20 passed and 0 failed; individual pytest durations ranged from 3.26 to 3.65 seconds.
- Guarded collection: 147 selected, including 144 existing cases and 3 environment probes; 462 deselected; 2.55 seconds.
- Full guarded integration run: 147 collected/selected, 147 executed, 147 passed, 0 failed, 0 errors, 0 skipped, 462 deselected; 281.95 seconds.
- Non-integration regression: 462 passed, 147 deselected; 14.57 seconds.
- Ruff: passed for `backend/app` and `backend/tests`.
- MyPy: passed with no issues in 105 source files.

No frontend file changed, so frontend checks were not rerun locally.

## New hosted verification

Pending push and pull-request creation. This section must be updated from the actual hosted checks; no hosted success is claimed yet.

## Safety and limitations

- `backend/.env` was not read, printed, modified, mounted, or committed; local commands ran from the repository root with explicit safe process variables.
- Only `docker-compose.test.yml` was used. Supabase, Supabase Storage, OpenAI, OpenRouter, production data, and customer data were not used.
- No historical migration or unrelated product feature changed.
- No revert, reset, clean, stash, rebase, force push, direct commit to `main`, or automatic PR merge was performed.
- Known limitation before hosted verification: local Python/OS differed from the runner and the local full suite was slower, but the relevant package, PostgreSQL, pgvector, image digest, locale, timezone, and guarded environment matched.
- Teardown command: `docker compose -f docker-compose.test.yml down`. It is scoped to the Slice 1 container and network and does not remove unrelated Docker resources.
