# Phase 1A Slice 1 Test Results

Evidence ID: **EV-TEST-DB-03**

Local verification date: 2026-08-02 (Asia/Riyadh)

## Integration architecture reconciliation

Static inspection and pytest collection reconciled the earlier 142/144 reports:

- 142 pre-existing integration test functions.
- 144 pre-existing collected cases.
- The two-case difference comes from one function in `test_processing_repositories.py` parameterized across `PROCESSING`, `PROCESSED`, and `FAILED`: one function becomes three cases, adding two.
- Three new isolated-environment proof functions bring the official Slice 1 selection to 147 cases.

Pre-existing case counts by module:

| Module area | Cases |
| --- | ---: |
| Analysis API | 8 |
| Auth API | 2 |
| Document processing API | 4 |
| Document upload API | 3 |
| Document read API | 17 |
| Embedding/retrieval API | 4 |
| Engagement API | 6 |
| Organization API | 6 |
| Analysis-run repository | 18 |
| Embedding repository | 17 |
| Embedding read-model scope | 5 |
| Document repository | 12 |
| Engagement repository | 12 |
| Organization repository | 12 |
| Processing repositories | 18 cases / 16 functions |
| **Total** | **144 cases / 142 functions** |

All 15 historical integration modules were left unchanged. They write synthetic rows and clean them through suite fixtures using independent sessions. API integration tests replace JWKS, Storage, embedding, and LLM boundaries with local fakes; repository tests use only PostgreSQL.

## Final results

| Gate | Collected/selected | Passed | Failed | Errors | Skipped | Deselected | Duration |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Guard unit tests | 14 | 14 | 0 | 0 | 0 | 0 | 0.15 s |
| Integration collection | 147 | n/a | n/a | n/a | n/a | 462 | 2.79 s |
| Historical integration subset | 144 | 144 | 0 | 0 | 0 | n/a | included below |
| New DB proof tests | 3 | 3 | 0 | 0 | 0 | n/a | included below |
| **Official integration final** | **147** | **147** | **0** | **0** | **0** | **462** | **201.46 s** |
| Non-integration regression | 461 | 461 | 0 | 0 | 0 | 148 | 12.33 s |

The first full integration attempt produced 146 passed and one failure in the newly written pgvector proof. The test used a zero vector, whose cosine distance to itself is `NaN`. It was corrected to use a nonzero 1536-dimensional vector; the focused proof and the full 147-case rerun then passed. This was a test-proof correction only, with no product behavior change.

## Static quality gates

- Ruff `app tests`: passed.
- Ruff `scripts`: passed.
- MyPy `app`: passed, 105 source files checked.
- `git diff --check`: passed.
- Frontend source changes: none.

Frontend commands were not rerun because no frontend or shared frontend tooling changed. The previously verified state supplied for this slice remains: 27 test files passed, 151 tests passed, lint passed, typecheck passed, and build passed. This is prior evidence, not a new local execution claim.

## Explicit fail-closed results

- Missing `GH_TEST_DATABASE_URL`: direct official collection failed before test collection.
- Missing explicit integration mode: unit guard passed.
- Unsupported scheme, non-test name, Supabase host, production/staging, and unapproved remote host: unit guards passed.
- Missing marker and missing Alembic state: unit guards passed.
- Credential/query redaction: unit guard passed.
- Zero collection: unit guard proved fatal.
- All skipped/zero executed: unit guard proved fatal.

## Hosted CI

The first hosted run (`30741152175`, commit `56e26e34ed47402b134bd724f628d0ac8049d40f`) produced:

- `backend-integration`: passed every step.
- `frontend`: passed every step.
- `backend`: failed at lint because its unbounded dev requirement installed Ruff 0.16.1 instead of the locally verified 0.15.20 and surfaced 266 historical findings.

The existing job steps remain unchanged. The Ruff development dependency was pinned to the locally and repository-verified version 0.15.20. In follow-up run `30741341196`, backend and frontend passed, while backend-integration reported 146 passed and one failure in the unchanged historical similarity-order test.

The test constructs two positive constant vectors, `[0.9] * 1536` and `[0.1] * 1536`. They are collinear and have equal cosine distance, while the production query intentionally orders only by cosine distance. Their tied order is therefore undefined. The test passed locally and in the first hosted integration job, then failed in the second hosted job. No test retry, skip, product tie-breaker, or historical-test edit was introduced to mask it. Overall hosted CI remains failed with this documented limitation.
