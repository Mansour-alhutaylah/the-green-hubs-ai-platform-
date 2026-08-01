# SIP™ Phase 1A — Foundation Architecture and Implementation Plan

| Field | Value |
|---|---|
| Document ID | GH-SIP-PH1A-PLAN-001 |
| Classification | Confidential — Internal Use |
| Prepared | 2026-08-02 |
| Type | **Planning and design only.** No application code, migration, configuration, test, dependency, secret, database or external service was modified, called or contacted in producing this document. |
| Repository | `the-green-hubs-ai-platform-` |
| Branch / commit basis | `feature/frontend-live-integration` @ `079efef` **plus the uncommitted working-tree changes** listed in `git status` (12 modified tracked files, 2 untracked test paths). Line numbers below are for the **working tree as read on 2026-08-02**, not for the committed tree. |
| Controlling baseline | `GH_Founder_PMO_Knowledge_AI_Foundation_Requirements_Proof_Plan_V1_0_2026-07-29.pdf` (V1.0, 29 July 2026) |
| Predecessor documents | `../01-baseline/SIP_Phase0_Baseline_Audit.md`, `../01-baseline/Command_Test_Log.md`, `../03-current-system/Current_System_Map.mmd`, `../04-p0-assessment/FND_P0_Gap_Matrix.csv`, `./Phase1_Recommended_Backlog.md` |
| Requirements in scope | FND-SEC-01 (partial — framework only), FND-SEC-03 (foundation only), FND-TST-01 (integration-test environment + CI gate) |

> **Baseline-document availability.** The controlling PDF named above is **not present in this repository** — a filesystem search across the repository for `*.pdf` and for `*Founder*` returned zero results. Every reference to the Foundation Plan in this document is therefore taken **second-hand**, from the quotations and requirement text already recorded in `SIP_Phase0_Baseline_Audit.md` and `FND_P0_Gap_Matrix.csv`. Where this document states a Plan requirement, it is quoting those Phase 0 artefacts, not the PDF. This should be corrected by placing the controlling PDF under `project-governance/00-baseline/` before Phase 1A is approved.

**Evidence convention.** **[F]** = *Confirmed fact* — read directly from a repository file in this session; path and line range given. **[R]** = *Recommendation* — a design proposal by this document, not present in the repository. **[U]** = *Unverified* — insufficient evidence; stated as such rather than assumed. No test was executed, no container started, and no database contacted in producing this plan.

---

## 1. Executive Recommendation

### 1.1 The recommendation

**Build Phase 1A as six sequential, independently revertible slices, in this order, and start with the test environment — not with security code.**

| # | Slice | Delivers | Risk to existing behaviour |
|---|---|---|---|
| 1 | Isolated PostgreSQL + pgvector test environment, guard, CI job | Scope A | **Zero** — no application file changes |
| 2 | Correlation ID + `RequestContext` (additive) | Scope B (context) | **Zero** — nothing consumes it yet |
| 3 | `audit_events` table + entity + repository + `AuditService`, no call sites wired | Scope D (spine) | **Zero** — nothing writes yet |
| 4 | `CrossTenantAccessDenied` + centralized denial auditing | Scope B (matrix) + D (denials) | **Low** — status codes and messages provably unchanged |
| 5 | Success-path audit writes on five sensitive operations | Scope D (coverage) | **Low** — transaction-scoped, additive |
| 6 | Permission catalog + resolver + `require_permission` + route-declaration registry, **wired to zero production endpoints** | Scope C | **Zero** — no endpoint changes authorization behaviour |

### 1.2 The three judgements that shape this plan

**(a) The isolated test database is the highest-leverage item in the whole phase, and it costs nothing.** Phase 0 recorded 144 integration tests that were never executed and are excluded from CI (`.github/workflows/ci.yml:25` runs `pytest -m "not integration"`) **[F]**. Every security claim Phase 1A wants to make — tenant isolation at the SQL layer, append-only audit behaviour, migration correctness — is only provable against a real PostgreSQL with pgvector. Management decision **M-11** in the Phase 0 audit assumed this required provisioning a paid environment. **It does not.** A `pgvector/pgvector` container in Docker Compose locally and a GitHub Actions service container in CI provisions the same capability at **zero recurring cost and zero new Python dependency**. This plan therefore recommends closing M-11 with the Docker Compose option rather than escalating it for budget. **[R]**

**(b) Phase 1A must not invent a role matrix, so it must not enforce permissions on any endpoint.** M-4 (the authoritative role model) is still open. Wiring `require_permission` to real endpoints without M-4 forces one of two bad choices: invent an unapproved authority model, or install a permissive default that adds a code path without adding a control. Phase 1A therefore ships the **enforcement seam** — catalog, resolver interface, dependency, deny-by-default semantics, and a structural test that no route can be added without an explicit declaration — and wires it to **zero production endpoints**. The day M-4 is recorded, wiring is one line per endpoint and needs no redesign. This is stated as a deliberate, visible restriction, not a silent gap. **[R]**

**(c) Nothing in Phase 1A may be called tamper-evident.** Phase 1A delivers an **append-only application audit foundation**: a table with no application update or delete path, database-level `UPDATE`/`DELETE` revocation on the application role, and tests proving both. It delivers **no hash chain**. The reason is technical, not schedule-driven, and is set out in §8.6: a per-organization hash chain requires a gap-free, serialised sequence, which under multiple workers means serialising every audit write for that organization behind a lock. That is a design and load-test job in its own right and must be a separate story with its own acceptance test — precisely the failure mode recorded as risk **R-4** in `Phase1_Recommended_Backlog.md` ("the hash chain is decorative"). Phase 1A's `event_schema_version` column is the seam that makes the later chain migration clean. **[R]**

### 1.3 What Phase 1A explicitly does *not* close

| Blocker (Phase 0 §8) | Phase 1A effect |
|---|---|
| BLOCKER-1 — no audit trail | **Foundation laid, not closed.** Append-only, not tamper-evident. Coverage of five operations, not all. |
| BLOCKER-2 — no server-side role enforcement | **Not closed.** Framework only. Blocked on M-4. |
| BLOCKER-3 — no demonstrated restore | Untouched. |
| BLOCKER-4 — no malware scanning / quarantine | Untouched. Deliberately deferred (Epic C of the Phase 1 backlog). |
| BLOCKER-5 — content leaves to external AI provider | Untouched. Management decision M-2. |
| BLOCKER-6 — no human approval gate | Untouched. Sprint 2. |

**Phase 1A does not make the system ready for real client or Aramco data.** It makes the foundation on which that readiness can later be built and, for the first time, continuously verified.

---

## 2. Current Authentication and Tenant Flow

All findings in this section are **[F]**.

### 2.1 The verified chain, step by step

```
Browser
  └─ frontend/src/lib/api/client.ts:39-43  getAccessToken()  — fresh Supabase token per call
       └─ Authorization: Bearer <ES256 JWT>            (client.ts:64)
            │
FastAPI
  └─ app/api/deps.py:67          _bearer_scheme = HTTPBearer(auto_error=False)
  └─ app/api/deps.py:121-127     get_current_auth_identity(credentials, verifier) -> UUID
       └─ app/infrastructure/security/supabase_jwt.py  SupabaseJWTVerifier.verify()
            • ES256-only module constant, JWKS by `kid`, iss/aud/exp/iat/sub required
            • every failure path collapses to one generic message
  └─ app/api/deps.py:130-137     get_current_user(identity, repository) -> User
       └─ SQLAlchemyUserRepository.get(identity)       app/infrastructure/repositories/user.py:40-43
       └─ None -> ProfileNotProvisionedError (403)     deps.py:135-136
            │
Endpoint (7 routers)  current_user: User = Depends(get_current_user)
            │
Service               organization_id re-derived from current_user.organization_id
            │
Repository            some methods org-scoped in SQL, some not (see §6.3)
```

### 2.2 How the backend identifies the user

The **only** identity input is the `sub` claim of a verified Supabase access token, returned as a `UUID` by `get_current_auth_identity` (`app/api/deps.py:121-127`). That UUID is used as the primary key lookup into `public.users` (`app/infrastructure/repositories/user.py:40-43`), under the shared-primary-key design documented at `app/domain/entities/user.py:1-14` (`public.users.id == auth.users.id`).

There is **no** header, query parameter, cookie or body field anywhere in `app/api/v1/` that supplies user identity.

### 2.3 How `organization_id` is resolved

`organization_id` is read from exactly one place: the `User` entity's `organization_id` field (`app/domain/entities/user.py:25`), populated from the `users.organization_id` column (`backend/migrations/versions/12c7b2051fc6_create_organizations_users_engagements.py:38`).

`users.organization_id` is **nullable** (`12c7b2051fc6...py:38`, `sa.Column('organization_id', sa.UUID(), nullable=True)`), and the domain entity types it `UUID | None`. Every tenant-scoped service therefore begins with a null check. Five services implement that check as a *private duplicate method*:

| Service | Method | Lines |
|---|---|---|
| `OrganizationService` | `_require_user_organization` | `app/services/organization.py:62-65` |
| `EngagementService` | `_require_user_organization` | `app/services/engagement.py:62-65` |
| `DocumentReadService` | `_require_user_organization` | `app/services/document_read.py:51-54` |
| `VectorRetrievalService` | inline | `app/services/vector_retrieval.py:56-58` |
| `RagAnalysisService` | inline (×3) | `app/services/analysis/rag_analysis.py:169-171, 193-195, 211-212` |
| `DocumentUploadService` | inline | `app/services/document_upload.py:98-99` |
| `DocumentProcessingService` | inline | `app/services/document_processing.py:137-138` |
| `EmbeddingGenerationService` | inline | `app/services/embedding_generation.py:109-110` |

**Finding (Low, design).** The same three-line null check is written eight times across seven files. All eight are correct today, but there is no single point at which a future service can be *forced* to perform it. This is the specific weakness `RequestContext` (§5) removes: by making `organization_id` a **non-optional** field of a context object that only the authenticated dependency can construct, "did this service remember to check?" stops being a per-service question.

### 2.4 Where a client *can* supply an organization ID — and what happens

Three endpoints accept an `organization_id` from the client. **None of them uses it as an authority.**

| Endpoint | Client input | Handling | Evidence |
|---|---|---|---|
| `POST /api/v1/engagements` | body `organization_id` | Compared to `current_user.organization_id`; mismatch → `AuthorizationError` (403) | `app/services/engagement.py:70-72` |
| `GET /api/v1/engagements` | query `organization_id` | Compared; mismatch → `AuthorizationError` (403). Filtering always uses `own_organization_id` | `app/services/engagement.py:101-107` |
| `PATCH /api/v1/engagements/{id}` | body `organization_id` | Compared; mismatch → `AuthorizationError` (403). The write uses `own_organization_id` regardless | `app/services/engagement.py:126-136` |
| `GET/PATCH /api/v1/organizations/{organization_id}` | path parameter | Compared; mismatch → `NotFoundError` (404), deliberately indistinguishable from a nonexistent id | `app/services/organization.py:67-74` |

**Confirmed:** in every case the value that reaches the repository is `own_organization_id`, derived from `current_user`. A client-supplied organization id can only ever cause a **rejection**, never a widening of scope. Phase 0 §3.2's claim is confirmed by direct re-reading in this session.

### 2.5 The two tenant-check patterns in use, and the difference that matters for auditing

The services split into two structurally different patterns. Both are safe; they differ in what the server *knows* at the moment it denies.

**Pattern A — scoped repository query.** The service asks the repository for the object *within* the caller's organization. A missing row and a foreign row return identically `None`.

| Site | Lines |
|---|---|
| `EngagementService.get` / `.update` → `get_for_organization` | `app/services/engagement.py:86-91`, `121-125` |
| `DocumentReadService.list` / `.get` → `*_for_organization` | `app/services/document_read.py:67-71`, `91-99` |
| `RagAnalysisService.get_run` → `get_by_id(..., organization_id=...)` | `app/services/analysis/rag_analysis.py:213-217` |

> **Consequence for Scope D:** at these sites the server **cannot distinguish** a cross-tenant probe from a genuinely nonexistent id — by design, and that design is correct (it never loads the foreign row). An audit event raised here can therefore only be classified `access_denied_or_not_found`. Classifying it `cross_tenant_denied` would be a fabrication. This is stated here because it directly limits what the Scope E test `EV-SEC-TENANT-02` can assert.

**Pattern B — unscoped fetch, then compare.** The service fetches by primary key, then compares the owning organization to the caller's.

| Site | Lines | Denial raised |
|---|---|---|
| `DocumentUploadService.upload` | `app/services/document_upload.py:96-103` | `AuthorizationError` (403) |
| `DocumentProcessingService.process` | `app/services/document_processing.py:131-142` | `AuthorizationError` (403) |
| `EmbeddingGenerationService.generate_for_document` | `app/services/embedding_generation.py:105-115` | `NotFoundError` (404) |
| `VectorRetrievalService.search` (engagement filter) | `app/services/vector_retrieval.py:67-68` | `NotFoundError` (404) |
| `VectorRetrievalService.search` (document filter) | `app/services/vector_retrieval.py:73-79` | `NotFoundError` (404) |
| `RagAnalysisService.analyze_document` | `app/services/analysis/rag_analysis.py:175-178` | `NotFoundError` (404) |
| `RagAnalysisService.analyze_engagement` | `app/services/analysis/rag_analysis.py:198-199` | `NotFoundError` (404) |
| `OrganizationService._require_own_organization` | `app/services/organization.py:67-74` | `NotFoundError` (404) |
| `EngagementService.create` / `.list` / `.update` | `app/services/engagement.py:71-72`, `102-103`, `126-127` | `AuthorizationError` (403) |

> **Consequence for Scope D:** at these eleven sites the server **provably knows** the access was cross-tenant, because it compared two concrete organization ids. These are the only sites where a `cross_tenant_denied` audit event can be honestly emitted.

**Secondary observation (Medium-Low, not a vulnerability).** Pattern B loads a foreign tenant's row into application memory before rejecting it (e.g. `rag_analysis.py:174-178` calls `self._document_repository.get(document_id)` with no organization predicate). No foreign data is ever returned to the caller — the denial is correct and negatively tested — but a future refactor that logs, caches, or serialises the fetched entity before the comparison would leak. Converging Pattern B onto Pattern A is a **Phase 1B** recommendation, explicitly **out of scope for Phase 1A** because it touches the AI/analysis path this phase must not disturb. **[R]**

### 2.6 The 404-vs-403 discipline

Two distinct denial semantics are in use, deliberately and consistently:

- **404 `NotFoundError`** when the caller is *probing for the existence* of an object they cannot see. Documented at `app/services/organization.py:70-74` ("a cross-tenant id must be indistinguishable from a nonexistent one").
- **403 `AuthorizationError`** when the caller is *attempting an action* whose target they already legitimately identified (create/reassign/list-for-other-org), documented at `app/services/engagement.py:20-25`.

**This discipline is a control and must survive Phase 1A unchanged.** Every design decision in §4–§8 preserves both the status code and the message text.

### 2.7 Request metadata available today

| Datum | Available? | Evidence |
|---|---|---|
| Correlation / request ID | **No** — nothing generates or propagates one | No middleware in `app/main.py:37-45`; no `X-Request-Id` reference anywhere in `backend/app` |
| Authenticated-at timestamp | **No** — `get_current_auth_identity` returns only the `sub` UUID (`deps.py:121-127`); the token's `iat`/`exp` are validated then discarded | `app/api/deps.py:127` |
| Client IP / User-Agent | Present on the Starlette `Request` but **never read** by any application code | grep of `backend/app` for `request.client` / `user-agent`: zero hits |
| Stored role | `users.role` (`12c7b2051fc6...py:39`, `String(50)`, nullable) — read in exactly **one** place, to echo it back | `app/api/v1/auth.py:31` |

---

## 3. Current Integration-Test Constraints

All findings in this section are **[F]** unless marked.

### 3.1 The configuration facts

| Item | Value | Evidence |
|---|---|---|
| Test runner config | `asyncio_mode = auto`; exactly one marker registered | `backend/pytest.ini:1-4` |
| Marker semantics | `integration: requires a live database connection (DATABASE_URL); excluded from the default CI run` | `backend/pytest.ini:4` |
| CI backend test command | `pytest -m "not integration"` | `.github/workflows/ci.yml:25` |
| CI Python | `3.12`; local runtime recorded in Phase 0 as `3.14.3` | `.github/workflows/ci.yml:17` |
| Root `tests/conftest.py` | 12 lines. **One** fixture (`client`, an ASGI `AsyncClient`). No DB fixture, no env guard, no cleanup | `backend/tests/conftest.py:1-12` |
| Compose file | Single `api` service, `env_file: ./backend/.env`. **No database service by design** | `docker-compose.yml:1-11` |
| Alembic URL source | `settings.database_url`, falling back to a hardcoded `localhost:5432/placeholder_db` | `backend/migrations/env.py:27-28` |
| Alembic head | `da0298a9c722` (chain: `eeb31636c877` → `12c7b2051fc6` → `693e23cf7797` → `73688728b480` → `81a7fdde2d19` → `233e7656bf79` → `3f3acc7fc556` → `da0298a9c722`) | `migrations/versions/*.py` `revision`/`down_revision` |
| pgvector enablement | `op.execute('CREATE EXTENSION IF NOT EXISTS vector')` inside migration `3f3acc7fc556` | `3f3acc7fc556_create_document_chunk_embeddings.py:86` |
| Dev dependencies | `pytest`, `pytest-asyncio`, `ruff`, `mypy`, `types-openpyxl`. **No `pytest-cov`, no `testcontainers`, no `pytest-env`, no `docker`** | `backend/requirements-dev.txt:1-6` |

### 3.2 The integration suite as it exists

15 modules carry `pytestmark = pytest.mark.integration`, containing **142 `test_` functions**; Phase 0's executed run recorded **144 collected integration items** after parametrisation, plus one separately deselected health test.

| Module | `test_` functions |
|---|---|
| `tests/api/test_analysis_integration.py` | 8 |
| `tests/api/test_auth_integration.py` | 2 |
| `tests/api/test_document_processing_integration.py` | 4 |
| `tests/api/test_documents_integration.py` | 3 |
| `tests/api/test_documents_read_integration.py` | 17 |
| `tests/api/test_embedding_and_retrieval_integration.py` | 4 |
| `tests/api/test_engagements_integration.py` | 6 |
| `tests/api/test_organizations_integration.py` | 6 |
| `tests/infrastructure/repositories/test_analysis_run_repository.py` | 18 |
| `tests/infrastructure/repositories/test_document_chunk_embedding_repository.py` | 17 |
| `tests/infrastructure/repositories/test_document_read_model_embedding_scope.py` *(untracked)* | 5 |
| `tests/infrastructure/repositories/test_document_repository.py` | 12 |
| `tests/infrastructure/repositories/test_engagement_repository.py` | 12 |
| `tests/infrastructure/repositories/test_organization_repository.py` | 12 |
| `tests/infrastructure/repositories/test_processing_repositories.py` | 16 |
| **Total** | **142** |

### 3.3 The four constraints that must be removed

**C-1 — The suite targets whatever `DATABASE_URL` happens to be, and on a developer machine that is shared Supabase.**
`app/infrastructure/db/session.py:26-37` builds the engine from `get_settings().database_url`; `.env` supplies it. Phase 0 recorded that on the operator's machine that value resolves to the shared Supabase instance, and the integration tests `INSERT`/`DELETE` real rows across eight tables. There is **no code path anywhere in `backend/` that inspects the URL and refuses a shared or production host.**

**C-2 — Absence of configuration causes a silent skip, not a failure.**
Every integration module carries an autouse fixture of this exact shape:

```python
@pytest.fixture(autouse=True)
def _require_database_url() -> None:
    if not get_settings().database_url:
        pytest.skip("integration tests require DATABASE_URL to be set")
```
(`tests/infrastructure/repositories/test_document_repository.py:53-58`; identical at `tests/api/test_documents_read_integration.py:57-60` and in all 15 modules.)

**This is the single most dangerous property for CI adoption.** A CI job that adds `pytest -m integration` but misconfigures the database URL will **skip all 144 tests and report green**. Converting this skip into a hard failure is a prerequisite for the integration suite to be a meaningful gate, not an optional extra.

**C-3 — The engine is constructed at import time, from an `lru_cache`d settings object.**
`app/infrastructure/db/session.py:26` executes `_settings = get_settings()` at module scope, and lines 28-37 build `create_async_engine(...)` immediately. `get_settings` is `@lru_cache`-decorated (`app/core/config.py:126-128`). Consequences the design must respect:
- The test database URL must be in `os.environ` **before** `app.infrastructure.db.session` is first imported. `backend/tests/conftest.py:4` already imports `app.main`, which transitively imports the session module — so any environment selection must execute *above* that import statement.
- Pydantic-settings gives environment variables precedence over `env_file` values, so setting `os.environ["DATABASE_URL"]` does override `.env` — but only if it happens first.
- A defensive `get_settings.cache_clear()` is required if anything reads settings before the override.

**C-4 — There is no schema-lifecycle or isolation mechanism.**
Each integration module hand-rolls its own cleanup: an `Ids` tracker plus a teardown that deletes rows in dependency-safe order through an independent session (`tests/api/test_documents_read_integration.py:91-120`; `tests/infrastructure/repositories/test_document_repository.py:86-89`). This is careful, correct work — but it exists *because* the target database is shared and must survive the run. Against a disposable database it is redundant, and it is the reason the suite is slow and order-sensitive. Phase 1A **must not rewrite it**: the 144 tests must be able to join CI *unchanged*, so their per-test cleanup stays and simply becomes belt-and-braces.

### 3.4 Environment safety facts that constrain the guard design

- `backend/.env.example:11` ships `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/green_hubs`. **A host allow-list of `localhost` alone is therefore insufficient** — the documented example default is itself a localhost URL that is not a test database. The guard needs a database-*name* rule and a positive in-database marker, not just a host rule. **[F] → [R]**
- `docker-compose.yml:7-8` mounts `./backend/.env` — real credentials — into the `api` service. Any test compose file **must not** reuse this file.
- Migration `12c7b2051fc6`'s docstring states the shared instance was reconciled by `alembic stamp` and that "a genuinely fresh database runs this migration for real" (`12c7b2051fc6...py:8-15`). This confirms the full 8-migration chain is designed to execute against an empty database — the exact case the test environment creates.
- `gen_random_uuid()` is used as a server default in `12c7b2051fc6...py:34,37,50`. It is built into PostgreSQL 13+, so no `pgcrypto` extension step is needed on a PG 16 image. **[F] → [R]**

---

## 4. Proposed Phase 1A Architecture

All of §4 is **[R]**.

### 4.1 Design constraints adopted

1. **Additive only.** No existing function signature changes. No existing service method loses or gains a required parameter. All 593 currently-passing tests must pass **unmodified**.
2. **No authentication redesign.** `get_current_auth_identity` and `get_current_user` (`app/api/deps.py:121-137`) are not touched. `RequestContext` is built *from* `get_current_user`, beside it.
3. **Clean-architecture boundaries preserved.** `app/domain/` and `app/services/` gain no FastAPI import. The `RequestContext` dataclass, `Permission` enum and resolver protocol live in `app/domain/`; every FastAPI `Depends` provider lives in `app/api/deps.py`; the exception→HTTP mapping stays in `app/core/exceptions.py`.
4. **Fail-closed where a decision exists; visibly-open where a decision is pending.** Unknown permission → deny. Unmapped policy → deny. Missing organization → deny. But permission enforcement is wired to **zero endpoints**, so nothing silently changes who can do what.
5. **Deny without disclosure.** No new error message, status code, or response field distinguishes "foreign" from "nonexistent" anywhere.

### 4.2 New module layout

```
backend/app/
├── core/
│   ├── correlation.py                    NEW  contextvar + ASGI middleware
│   └── exceptions.py                     MOD  + CrossTenantAccessDenied; audit hook
├── domain/
│   ├── request_context.py                NEW  RequestContext (frozen dataclass)
│   ├── security/
│   │   ├── __init__.py                   NEW
│   │   ├── permissions.py                NEW  Permission (StrEnum) + PERMISSION_CATALOG
│   │   └── policy.py                     NEW  PolicyId, IPermissionResolver (Protocol)
│   ├── entities/audit_event.py           NEW  AuditEvent (frozen dataclass)
│   └── repositories/audit_event.py       NEW  IAuditEventRepository (append + read only)
├── infrastructure/
│   ├── db/models/audit_event.py          NEW  AuditEventModel
│   ├── repositories/audit_event.py       NEW  SQLAlchemyAuditEventRepository
│   └── security/static_policy_resolver.py NEW StaticPolicyResolver (deny-by-default)
├── services/
│   └── audit.py                          NEW  AuditService (two write modes)
└── api/deps.py                           MOD  + 4 providers + require_permission factory
```

### 4.3 The audit write-path architecture (the one non-obvious decision)

Two write modes are required because a denied request has **no transaction that survives**.

```
                 ┌──────────────────────── SUCCESS PATH ────────────────────────┐
  Service ──────▶│ AuditService.record_in_transaction(session, event)           │
                 │  • same AsyncSession as the business write                   │
                 │  • no explicit commit — rides the caller's commit            │
                 │  ⇒ business rollback ⇒ audit event also rolls back           │
                 └──────────────────────────────────────────────────────────────┘

                 ┌──────────────────── DENIED / FAILED PATH ────────────────────┐
  AppError ─────▶│ AuditService.record_out_of_band(event)                        │
  handler        │  • opens its OWN AsyncSessionLocal(), commits, closes         │
                 │  • independent of the request session, which is being torn    │
                 │    down without commit                                        │
                 │  ⇒ denial is recorded even though nothing else is written     │
                 └──────────────────────────────────────────────────────────────┘
```

Why this is necessary, precisely: `get_db()` (`app/infrastructure/db/session.py:46-48`) yields a session inside `async with`. When a service raises, FastAPI unwinds, the context manager closes the session, and **no commit occurs**. An audit row written on that session for the denial is discarded. This is the transaction analysis Scope D requires, and it is the reason `record_out_of_band` exists rather than a single unified writer.

### 4.4 Where denials are captured

`register_exception_handlers` (`app/core/exceptions.py:54-60`) is the **one** place every `AppError` passes through, and its handler already receives the Starlette `Request`. Phase 1A adds the audit emission there rather than at ~11 service call sites. Benefits: one code path, no service signature changes, no possibility of a service forgetting.

The handler cannot know *why* a `NotFoundError` was raised, so §4.5 supplies the discriminator.

### 4.5 `CrossTenantAccessDenied` — the minimal discriminator

```python
class CrossTenantAccessDenied(NotFoundError):
    """A denial the server KNOWS is cross-tenant, because it compared two
    concrete organization ids. Inherits NotFoundError so status_code (404)
    and the response envelope are byte-identical to today — the client can
    never tell the difference. The distinction exists only for auditing."""
```

- `status_code` is **inherited unchanged** (404 from `exceptions.py:26-27`).
- The message text passed at each call site is **left exactly as it is today**.
- `except NotFoundError:` blocks elsewhere continue to catch it (e.g. `app/services/document_upload.py:131`).

It is substituted at only the **Pattern B** sites listed in §2.5 where the comparison provably happened. It is **not** substituted at Pattern A sites, because there the server does not know.

An equivalent `CrossTenantActionDenied(AuthorizationError)` (403) covers the `AuthorizationError` cross-tenant sites.

### 4.6 What is deliberately *not* built in Phase 1A

| Not built | Why | Where it belongs |
|---|---|---|
| Hash chain / tamper evidence | Needs a serialised gap-free sequence; see §8.6 | Phase 1B, own acceptance test |
| RLS policies | Needs the isolated DB (Slice 1) to be verifiable at all; large surface | Phase 1B |
| `require_permission` on production endpoints | Blocked on **M-4** | Phase 1B, one line per endpoint |
| Audit read API / audit UI | "A viewer over an untrustworthy trail is worse than none" (`Phase1_Recommended_Backlog.md:243`) | Phase 1C+ |
| Quarantine state machine (FND-SEC-02) | Independent; not a foundation dependency | Sprint 1 Epic C |
| Migrating services to accept `RequestContext` instead of `User` | ~8 services, ~60 tests — a large refactor with no Phase 1A benefit | Phase 1B |

---

## 5. Proposed `RequestContext` Design

All of §5 is **[R]**.

### 5.1 The entity

`backend/app/domain/request_context.py` — framework-independent, no FastAPI import, consistent with `app/domain/entities/user.py`'s dataclass style.

```python
@dataclass(frozen=True)
class RequestContext:
    """Trusted server-side identity and tenant scope for one request.

    Constructible only by app.api.deps.get_request_context, which builds it
    from a verified token and the persisted public.users profile. No field
    is ever populated from a request body, query parameter or header.
    """
    user_id: UUID                  # == verified JWT `sub`
    organization_id: UUID          # NON-optional: absence is denied before construction
    policy_id: str | None          # stored users.role, VERBATIM, uninterpreted
    correlation_id: str            # per-request; from CorrelationIdMiddleware
    authenticated_at: datetime     # server clock at context construction (UTC)
    client_ip: str | None          # safe metadata; never a header the client controls unchecked
    user_agent: str | None         # truncated to 256 chars

    @property
    def actor_type(self) -> str:
        return "USER"              # SYSTEM / AGENT reserved for later phases
```

### 5.2 The four properties that make it trustworthy

| Property | Mechanism |
|---|---|
| **`organization_id` cannot be client-supplied** | It is only ever assigned from `current_user.organization_id`, which is read from `public.users` by primary key using the verified `sub`. |
| **`organization_id` cannot be `None`** | Typed non-optional. The provider raises `AuthorizationError("User has no organization")` — **the exact message already used at `organization.py:64`, `engagement.py:64`, `document_read.py:53`** — before constructing. Behaviour and message are unchanged. |
| **`policy_id` is inert data** | It is the raw `users.role` string. Nothing in Phase 1A interprets it. Only `IPermissionResolver` (§7) may map it, and only server-side. |
| **It is immutable** | `frozen=True`. No downstream code can widen scope after construction. |

### 5.3 The provider

`backend/app/api/deps.py` — appended after `get_current_user` (currently ends at line 137):

```python
def get_request_context(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> RequestContext:
    if current_user.organization_id is None:
        raise AuthorizationError("User has no organization")   # message unchanged
    return RequestContext(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        policy_id=current_user.role,
        correlation_id=get_correlation_id(),
        authenticated_at=datetime.now(timezone.utc),
        client_ip=_safe_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:256] or None,
    )
```

**`_safe_client_ip` note.** It must read `request.client.host` and **not** trust `X-Forwarded-For` unless a trusted-proxy configuration exists. No such configuration exists in this repository today **[F]** (`app/main.py:28-51` adds only `CORSMiddleware`), so Phase 1A reads `request.client.host` only, and records the limitation.

### 5.4 Correlation ID — how it reaches downstream services without signature changes

Scope E requires "Correlation ID is available to downstream services". Threading a parameter through every service would violate the additive-only constraint. Use a `contextvar`, which is task-local and therefore correct under `asyncio` concurrency.

`backend/app/core/correlation.py`:

```python
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

def get_correlation_id() -> str: ...

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Sets a per-request correlation id, echoes it as X-Request-Id.

    An inbound X-Request-Id is accepted ONLY if it matches a strict
    UUID/opaque-token pattern and a length cap; anything else is replaced
    with a server-generated uuid4. It is a correlation aid, never an
    authorization or identity input, and never reaches a SQL string.
    """
```

Registered in `app/main.py` **inside** `CORSMiddleware` (added after it, per Starlette's reverse-order semantics) so the header survives on error responses — the same reasoning already documented for the exception handler at `app/core/exceptions.py:62-72`.

`app/core/logging.py:6-10` gains a formatter field for the correlation id, so application logs and audit events can be joined.

### 5.5 Adoption strategy — the deliberately conservative part

**Phase 1A does not change a single existing service signature.** `RequestContext` is consumed by exactly two new things:

1. `AuditService` — every audit event is built from a `RequestContext`.
2. `require_permission` — the resolver receives `RequestContext`, never a `User`.

The eight duplicated `_require_user_organization` checks in §2.3 stay exactly where they are. They become redundant for any endpoint that also depends on `get_request_context`, but redundant is not harmful, and removing them is a ~60-test refactor with zero Phase 1A benefit.

**Trade-off, stated plainly.** This leaves two ways to obtain tenant scope in the codebase simultaneously (`current_user.organization_id` and `context.organization_id`) until Phase 1B converges them. That is accepted deliberately: converging now would mean editing every service and every service test in the same phase that introduces auditing, and a regression in tenant isolation is a far worse outcome than a temporary duplication. Phase 1B slice 1 should be "migrate services to `RequestContext`, delete the eight duplicates".

---

## 6. Endpoint Tenant-Control Matrix

All of §6 is **[F]** unless a cell is marked. "Client org input" means the endpoint accepts an organization identifier from the client in any form.

### 6.1 The 14 endpoints

| # | Method + path | Router (file:line) | Auth | Client org input | Tenant scope source | Denial today | Server knows cross-tenant? | Phase 1A change |
|---|---|---|---|---|---|---|---|---|
| 1 | `GET /api/v1/health` | `health.py:23-25` | **None** | — | n/a | n/a | n/a | none |
| 2 | `GET /api/v1/health/db` | `health.py:28-39` | **None** | — | n/a | n/a | n/a | none |
| 3 | `GET /api/v1/auth/me` | `auth.py:20-32` | `get_current_user` | no | own profile only | 401 / 403 no profile | n/a | audit `ProfileNotProvisionedError` |
| 4 | `POST /api/v1/organizations` | `organizations.py:42-55` | `get_current_user` | body `name` only | n/a — **unconditionally 403** (`organization.py:33-34`) | 403 always | n/a | none |
| 5 | `GET /api/v1/organizations` | `organizations.py:58-68` | `get_current_user` | no | `current_user.organization_id` (`organization.py:43`) | 403 null org | n/a | none |
| 6 | `GET /api/v1/organizations/{id}` | `organizations.py:71-83` | `get_current_user` | **path id** | compared, then own id used (`organization.py:37,67-74`) | **404** | **YES** (`organization.py:69`) | → `CrossTenantAccessDenied` |
| 7 | `PATCH /api/v1/organizations/{id}` | `organizations.py:86-99` | `get_current_user` | **path id** | same (`organization.py:50`) | **404** | **YES** | → `CrossTenantAccessDenied` + success audit |
| 8 | `POST /api/v1/engagements` | `engagements.py:52-70` | `get_current_user` | **body `organization_id`** | compared → 403 (`engagement.py:70-72`) | **403** | **YES** | → `CrossTenantActionDenied` |
| 9 | `GET /api/v1/engagements` | `engagements.py:73-88` | `get_current_user` | **query `organization_id`** | compared → 403; filter uses own (`engagement.py:101-108`) | **403** | **YES** | → `CrossTenantActionDenied` |
| 10 | `GET /api/v1/engagements/{id}` | `engagements.py:91-103` | `get_current_user` | no | `get_for_organization` (`engagement.py:86-91`) | **404** | **NO** — Pattern A | audit as `access_denied_or_not_found` |
| 11 | `PATCH /api/v1/engagements/{id}` | `engagements.py:106-128` | `get_current_user` | **body `organization_id`** | scoped fetch, then compare (`engagement.py:121-127`) | 404 then **403** | **404: NO / 403: YES** | 403 → `CrossTenantActionDenied` |
| 12 | `POST /api/v1/documents` | `documents.py:123-148` | `get_current_user` | body `engagement_id` (not an org id) | engagement's org compared (`document_upload.py:96-103`) | 404 missing / **403** foreign | **YES** | → `CrossTenantActionDenied` + success audit |
| 13 | `POST /api/v1/documents/{id}/process` | `documents.py:151-167` | `get_current_user` | no | engagement's org compared (`document_processing.py:131-142`) | 404 / **403** | **YES** | → `CrossTenantActionDenied` + success audit |
| 14 | `POST /api/v1/documents/{id}/embeddings` | `documents.py:170-194` | `get_current_user` | no | compared, denies as 404 (`embedding_generation.py:105-115`) | **404** | **YES** | → `CrossTenantAccessDenied` + success audit |
| 15 | `GET /api/v1/documents` | `documents.py:197-220` | `get_current_user` | query `engagement_id` | scoped repo (`document_read.py:65-87`) | 403 null org / **404** engagement | **NO** — Pattern A | audit as `access_denied_or_not_found` |
| 16 | `GET /api/v1/documents/{id}` | `documents.py:223-235` | `get_current_user` | no | scoped repo (`document_read.py:89-100`) | **404** | **NO** — Pattern A | as above |
| 17 | `POST /api/v1/retrieval/search` | `retrieval.py:23-59` | `get_current_user` | body `engagement_id` / `document_id` | compared (`vector_retrieval.py:56-79`); SQL predicate `WHERE dce.organization_id = :organization_id` (`document_chunk_embedding.py:232`) | **404** | **YES** | → `CrossTenantAccessDenied` |
| 18 | `POST /api/v1/analysis/documents/{id}/analyze` | `analysis.py:54-76` | `get_current_user` | no | compared (`rag_analysis.py:169-178`) | **404** | **YES** | → `CrossTenantAccessDenied` + success audit |
| 19 | `POST /api/v1/analysis/engagements/{id}/analyze` | `analysis.py:79-101` | `get_current_user` | no | compared (`rag_analysis.py:193-199`) | **404** | **YES** | → `CrossTenantAccessDenied` + success audit |
| 20 | `GET /api/v1/analysis/runs/{id}` | `analysis.py:104-119` | `get_current_user` | no | scoped repo (`rag_analysis.py:211-217`) | **404** | **NO** — Pattern A | as above |

*(Numbering runs to 20 because three routers expose more than one operation per path; the router set is the 7 modules aggregated at `app/api/v1/router.py:8-14`.)*

### 6.2 Findings from the matrix

| ID | Finding | Severity | Evidence |
|---|---|---|---|
| **T-1** | **No sensitive endpoint trusts a client-supplied organization identifier.** All four that accept one compare it and reject on mismatch. Phase 0 §3.2 confirmed by re-reading. | — (confirmation) | rows 6-9, 11 |
| **T-2** | `GET /api/v1/health/db` is **unauthenticated and executes SQL** (`SELECT 1`) against the configured database (`health.py:28-39`). Its response is a fixed two-value envelope disclosing only reachability. Not a tenant issue; noted because it is the only unauthenticated DB-touching route. | Low | `health.py:28-39` |
| **T-3** | Denial semantics are **inconsistent between equivalent operations**: `POST /documents/{id}/embeddings` denies cross-tenant with **404** (`embedding_generation.py:115`) while `POST /documents/{id}/process` denies the same condition with **403** (`document_processing.py:142`). Both are safe; the asymmetry is undocumented and makes a uniform client contract impossible. | Low | rows 13, 14 |
| **T-4** | **Nine of twenty endpoints (45 %) cannot honestly report cross-tenant denial** because they use Pattern A. This is a correct design and must not be "fixed"; it is recorded here so audit coverage claims stay truthful. | — (constraint) | rows 10, 11(404), 15, 16, 20 |
| **T-5** | `POST /api/v1/organizations` is published, documented as 201-returning (`organizations.py:44-47`), and **unconditionally raises `AuthorizationError`** for every caller (`organization.py:33-34`). Confirms Phase 0 D-5. No user can be onboarded through the system. | Medium (functional) | row 4 |
| **T-6** | **No endpoint performs any within-tenant authorization.** `current_user.role` is read exactly once, at `auth.py:31`, to echo it. Confirms Phase 0 BLOCKER-2; **not closed by Phase 1A**. | Critical | grep of `backend/app` |

### 6.3 Repository-layer scoping (the layer the 144 tests would prove)

| Repository | Org-scoped methods | Unscoped methods | Protection today |
|---|---|---|---|
| `document.py` | `get_read_model_for_organization` (`:325`), `list_read_models_for_organization` (`:353`), `count_for_organization` (`:386`) | `get` (`:230`), `list` (`:234`), `create` (`:239`), `update` (`:256`), `delete` (`:268`), `get_by_engagement` (`:274`), `update_status` (`:279`), `begin_processing` (`:288`), `complete_processing` (`:310`) | Service layer only |
| `engagement.py` | `get_for_organization` (`:80`), `update_for_organization` (`:90`), `list` (`:57`), `count` (`:71`) | `get` (`:53`), `create` (`:107`), `update` (`:116`), `delete` (`:127`) | Service layer only |
| `analysis_run.py` | 20 `organization_id` references; `get_by_id(..., organization_id=)` (`:181`), `claim_or_get` (`:107`), `add_citations` (`:291`) | — | Repository SQL |
| `document_chunk_embedding.py` | `search` — `WHERE dce.organization_id = :organization_id` (`:232`); tenant lineage derived via `INSERT…SELECT…JOIN` (`:82-96`) | — | Repository SQL |
| `document_chunk.py` | **none** — zero `organization_id` references | all | Service layer only |
| `extracted_text.py` | **none** — zero `organization_id` references | all | Service layer only |
| `organization.py` | n/a — the table *is* the tenant | — | Service layer |
| `user.py` | 3 references | `get`/`list`/`create`/`update`/`delete` unscoped | Identity-keyed only |

**Finding T-7 (High, verification).** Two repositories (`document_chunk.py`, `extracted_text.py`) contain **no tenant predicate at all** and rely entirely on the service layer above them. Combined with the absence of RLS (Phase 0 S-1), a single missed service check on the chunk or extracted-text path has **no second barrier**. This is not a live vulnerability — every reachable path goes through a checked service — but it is exactly the class of defect the 144 integration tests exist to catch, and they have never run. **This is the strongest argument for Slice 1.**

---

## 7. Proposed Permission Catalog and Resolver Interface

All of §7 is **[R]**.

### 7.1 The catalog

`backend/app/domain/security/permissions.py`. A `StrEnum` — aligned with `backend/CLAUDE.md`'s standing instruction that finite business states use an Enum.

```python
class Permission(StrEnum):
    """Capabilities, not roles. A capability names WHAT may be done; it never
    names WHO may do it. The mapping from principal to capability is the
    resolver's job (policy.py) and is a management decision, not a code one."""

    DOCUMENTS_READ        = "documents.read"
    DOCUMENTS_CREATE      = "documents.create"
    DOCUMENTS_PROCESS     = "documents.process"
    DOCUMENTS_MANAGE      = "documents.manage"
    ANALYSIS_RUN          = "analysis.run"
    ANALYSIS_REVIEW       = "analysis.review"
    APPROVALS_SUBMIT      = "approvals.submit"
    APPROVALS_DECIDE      = "approvals.decide"
    AUDIT_READ            = "audit.read"
    ORGANIZATION_MANAGE   = "organization.manage"
    ADMINISTRATION_MANAGE = "administration.manage"
    RELEASE_APPROVE       = "release.approve"
```

Twelve members, exactly as specified in Scope C. Four (`APPROVALS_SUBMIT`, `APPROVALS_DECIDE`, `ANALYSIS_REVIEW`, `RELEASE_APPROVE`) have **no corresponding operation in the system today** — they are declared now so the catalog is stable and later phases add mappings rather than renaming constants. Their presence is not a claim that approval exists.

An accompanying `PERMISSION_CATALOG: Mapping[Permission, str]` supplies a human-readable description per capability, and is the source for the governance evidence artefact.

### 7.2 Intended capability → operation mapping *(reference only — not wired in Phase 1A)*

| Permission | Endpoint(s) it would guard |
|---|---|
| `documents.read` | `GET /documents`, `GET /documents/{id}`, `POST /retrieval/search` |
| `documents.create` | `POST /documents` |
| `documents.process` | `POST /documents/{id}/process`, `POST /documents/{id}/embeddings` |
| `documents.manage` | *(no operation today — deletion/supersession is a later phase)* |
| `analysis.run` | `POST /analysis/documents/{id}/analyze`, `POST /analysis/engagements/{id}/analyze` |
| `analysis.review` | *(no operation today — FND-KC-05 / Sprint 2)* |
| `approvals.submit` / `approvals.decide` | *(no operation today — FND-GOV-02 / Sprint 2)* |
| `audit.read` | *(no operation today — audit read API deliberately deferred)* |
| `organization.manage` | `PATCH /organizations/{id}`, `POST/PATCH /engagements` |
| `administration.manage` | `POST /organizations` (currently disabled) |
| `release.approve` | *(no operation today — governance gate)* |

This table is documentation of intent for the M-4 conversation. **No code in Phase 1A applies it.**

### 7.3 The resolver interface

`backend/app/domain/security/policy.py`:

```python
PolicyId = NewType("PolicyId", str)

class IPermissionResolver(Protocol):
    """Resolves a request context to the capability set it holds.

    Contract:
      • MUST be a pure server-side lookup. It MUST NOT read any value the
        client supplied — not a header, not a body field, not a claim other
        than what the verified profile already stored.
      • MUST return an EMPTY frozenset for an unknown, absent or unmapped
        policy id. It MUST NOT raise for an unknown policy: an unknown
        principal holds no capabilities, which is a resolution result, not
        an error.
      • MUST be deterministic for a given (policy_id, organization_id).
    """
    async def resolve(self, context: RequestContext) -> frozenset[Permission]: ...
```

`organization_id` is part of the contract signature even though Phase 1A's implementation ignores it — a future per-organization policy assignment table then needs no interface change.

### 7.4 The Phase 1A implementation

`backend/app/infrastructure/security/static_policy_resolver.py`:

```python
class StaticPolicyResolver:
    """Deny-by-default resolver backed by an explicit, code-defined map.

    Phase 1A ships this map EMPTY. Every principal therefore resolves to
    the empty capability set, and every require_permission check denies.
    This is safe precisely because Phase 1A wires require_permission to
    ZERO production endpoints — the deny-by-default property is proven by
    test, not by breaking live traffic.

    The map is populated only when management decision M-4 records the
    authoritative role model. No name, email or user id ever appears here.
    """
    _POLICIES: Mapping[PolicyId, frozenset[Permission]] = {}
```

**Why an empty map rather than a permissive default.** A permissive default is a default-allow path, which the Phase 1 backlog's security consideration #2 forbids (`Phase1_Recommended_Backlog.md:151`). An empty map with zero wired endpoints has the same operational effect as today (nothing is enforced) while making the *only* possible future state a deliberate, approved one. There is no configuration flag that could accidentally open it.

### 7.5 The dependency

`backend/app/api/deps.py`:

```python
def require_permission(permission: Permission) -> Callable[..., Awaitable[RequestContext]]:
    """FastAPI dependency factory. Deny-by-default at three levels:
       1. Not a Permission enum member  -> TypeError at import (never at runtime)
       2. Resolver returns empty/absent -> AuthorizationError
       3. Permission not in the set     -> AuthorizationError

    Raises AuthorizationError (403) with a FIXED generic message. It never
    names the required permission, the caller's policy, or the object —
    a denial must not teach a caller what to ask for next.
    """
```

Level 1 matters: because the parameter is typed `Permission`, an unknown permission string is a **static** error caught by `mypy app` in CI (`.github/workflows/ci.yml:23`), not a runtime deny. The runtime deny still exists for a member with no mapping.

### 7.6 The structural guarantee (the part that has real value today)

The one permission control Phase 1A **can** deliver without M-4 is: *no route can be added without a deliberate decision about it.*

`backend/app/domain/security/route_registry.py` **[R]** declares, for every route in `app.routes`, either a required `Permission` or explicit membership of `UNGUARDED_ROUTES` with a one-line justification. A test (`EV-SEC-PERM-04`) walks the live FastAPI route table and fails if any route is in neither. The initial `UNGUARDED_ROUTES` contains today's 20 operations, each annotated — an honest, reviewable inventory rather than an invented matrix.

This gives Phase 1B a checklist that is guaranteed complete, and makes an unguarded new endpoint a **CI failure** from Phase 1A onward.

### 7.7 Implemented now vs extension point

| Element | Phase 1A | Phase 1B+ |
|---|---|---|
| `Permission` catalog (12 members) | **Implemented, frozen** | Additive only |
| `IPermissionResolver` protocol | **Implemented** | Unchanged |
| `StaticPolicyResolver` | **Implemented, empty map** | Map populated from M-4 |
| `require_permission` dependency | **Implemented + unit-tested** | Applied to endpoints |
| Route-declaration registry + CI test | **Implemented** | Entries migrate from unguarded → guarded |
| Policy assignment storage (table) | **Not built** | Extension point: resolver signature already takes `organization_id` |
| Direct per-user grants | **Not built** | Extension point: a second resolver, composed |
| Temporary dev/test policy | **Not built — not technically necessary** | — |

**On the "temporary development/test policy" Scope C permits.** It is **not required** and should **not** be built. Because zero endpoints are wired, no test needs a permissive policy to exercise existing behaviour; the resolver tests construct their own fixtures directly. Introducing an environment-gated permissive policy would create exactly the default-allow path §7.4 avoids, in exchange for nothing. **[R]**

---

## 8. Proposed Audit-Event Schema and Write Flow

All of §8 is **[R]**.

### 8.1 Table `audit_events`

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `UUID` PK, default `gen_random_uuid()` | no | Matches every existing table's convention (`12c7b2051fc6...py:34`) |
| `recorded_seq` | `BIGSERIAL`, `UNIQUE` | no | Insertion order **within one database**. Gaps are expected (see §8.6) |
| `event_schema_version` | `SMALLINT`, default `1` | no | The seam for the Phase 1B chained-event format |
| `organization_id` | `UUID` | **yes** | Nullable **only** for pre-tenant failures (bad token, no profile) where no organization is known. Never nullable for a business event |
| `actor_user_id` | `UUID` | yes | Null for anonymous/unauthenticated failures. **No FK** — see §8.4 |
| `actor_type` | `VARCHAR(20)` | no | `USER` \| `SYSTEM` \| `ANONYMOUS`. CHECK constraint |
| `action` | `VARCHAR(100)` | no | Dotted verb, e.g. `document.upload` |
| `object_type` | `VARCHAR(50)` | yes | e.g. `document`, `engagement` |
| `object_id` | `UUID` | yes | The id **as requested**; see §8.5 on foreign ids |
| `result` | `VARCHAR(20)` | no | `SUCCESS` \| `DENIED` \| `FAILED`. CHECK constraint |
| `previous_state` | `JSONB` | yes | Allow-listed fields only |
| `new_state` | `JSONB` | yes | Allow-listed fields only |
| `reason` | `VARCHAR(500)` | yes | Fixed server-authored summary, never free client text |
| `correlation_id` | `VARCHAR(64)` | no | From `RequestContext` |
| `occurred_at` | `TIMESTAMPTZ`, default `now()` | no | **`TIMESTAMPTZ`**, deliberately unlike the existing `TIMESTAMP` columns (see §8.7) |
| `request_method` | `VARCHAR(10)` | yes | Safe metadata |
| `request_path` | `VARCHAR(255)` | yes | **Route template**, not the raw path (see §8.5) |
| `client_ip` | `INET` | yes | |
| `user_agent` | `VARCHAR(256)` | yes | Truncated |

**Indexes:** `(organization_id, occurred_at DESC)`, `(object_type, object_id)`, `(correlation_id)`, `(action, occurred_at DESC)`.

**Constraints:** `CHECK (actor_type IN (...))`, `CHECK (result IN (...))`, `CHECK (actor_type <> 'USER' OR actor_user_id IS NOT NULL)`.

**Deliberately absent in Phase 1A:** `previous_hash`, `entry_hash`, per-organization `sequence_number`. Not reserved as nullable columns — reserving them invites a half-populated chain, which is the "decorative chain" failure mode (`Phase1_Recommended_Backlog.md:257`, R-4). `event_schema_version` cleanly separates pre-chain from chained events when Phase 1B adds them.

### 8.2 Append-only enforcement — three independent layers

| Layer | Mechanism | Test |
|---|---|---|
| **1. Interface** | `IAuditEventRepository` exposes `append` and `list_for_organization` **only** — no `update`, no `delete`. It does **not** inherit `BaseRepository` (`app/infrastructure/repositories/base.py:32-52`), which supplies `update`/`delete` | `EV-AUD-03a` (static) |
| **2. ORM** | `AuditEventModel` mapped, but the repository never issues `UPDATE`/`DELETE` and the entity is a frozen dataclass | `EV-AUD-03a` |
| **3. Database** | Migration executes `REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM <application_role>` | `EV-AUD-03b` — a raw SQL `UPDATE` through the application session must raise |

> **Explicit caveat, per the mandate.** Layer 3 is the only one that constitutes a real control; layers 1 and 2 are discipline. **Layer 3's effectiveness depends entirely on the application connecting as a role that is not the table owner and not a superuser.** Phase 0 recorded that the backend connects with a role that bypasses RLS (§5.2, TB-5) — which strongly suggests an owner/superuser-class role. **[U]** If that is confirmed, `REVOKE` is ineffective against it and the honest statement becomes *"append-only by application construction, not by database enforcement."* **Determining the application's actual database role and privileges is an explicit Phase 1A investigation task (Slice 3), and its finding is a required part of evidence EV-AUD-03.** Nothing in this design may be described as immutable until that is answered.

### 8.3 The two write modes (see §4.3 for the diagram)

```python
class AuditService:
    async def record_in_transaction(self, session, event) -> None:
        """SUCCESS path. Adds to the caller's session; does NOT commit.
        If the business transaction rolls back, so does the event.
        Guarantees: no 'succeeded' event without the business change."""

    async def record_out_of_band(self, event) -> None:
        """DENIED / FAILED path. Opens its own AsyncSessionLocal, commits,
        closes. Independent of the request session, which is unwinding
        without commit. Guarantees: a denial is recorded even though
        nothing else is written."""
```

**Failure of the audit write itself.** Phase 1A's recommended default is **fail-open with a mandatory `logger.error`** including the correlation id — an audit write failure must never turn a successful, already-committed business operation into a 500. This is a **decision requiring management approval (D-3, §22)**; the Phase 1 backlog recommends fail-closed for admin-class actions (`Phase1_Recommended_Backlog.md:154`), and Phase 1A has no admin-class actions to which that would apply. Whatever is decided must be explicit and tested, never an unnoticed skip.

### 8.4 Why no foreign key on `actor_user_id`

`users` rows may be removed or re-provisioned out-of-band (Phase 0 D-5, M-5: provisioning is entirely external to this codebase). A `NO ACTION` FK would make a user row undeletable; a `CASCADE` FK would **delete audit history** — catastrophic for an audit trail. The column stores the UUID with no referential constraint, and the actor is resolved at read time on a best-effort basis. This is the standard audit-table pattern and it is a deliberate divergence from the FK convention used elsewhere in this schema.

### 8.5 Data-minimisation rules (non-negotiable)

**Never written to `audit_events`, under any circumstances:**

| Forbidden | Why |
|---|---|
| Document content, extracted text, chunk text, `quoted_snippet` | The audit trail must not become a second, unprotected copy of the evidence corpus |
| Embedding vectors | Content-derived |
| LLM prompts or completions | Content-derived; also provider-attributable |
| Access tokens, JWTs, JWKS material, API keys, `DATABASE_URL`, any connection string | Secret |
| Email addresses, full names, phone numbers | Unnecessary PII — `actor_user_id` (a UUID) fully identifies the actor and joins to `users` when authorised |
| Raw request bodies or full query strings | Uncontrolled content; hence `request_path` stores the **route template** (`/api/v1/documents/{document_id}`), not the concrete path |

**How this is enforced (not merely intended):**

1. `previous_state` / `new_state` are built by a per-object-type **allow-list function**, never from `entity.__dict__` or `model.__dict__`. Only these fields may appear: `document` → `{id, engagement_id, filename, processing_status}`; `engagement` → `{id, organization_id, title, status}`; `organization` → `{id, name}`; `analysis_run` → `{id, status, analysis_type, document_id, engagement_id}`.
2. `AuditService` runs a **key denylist** over both JSONB payloads before insert (`token`, `key`, `secret`, `password`, `authorization`, `api_key`, `content`, `text`, `embedding`, `prompt`, `snippet`) and **raises** on a hit — a programming error, caught in test, never silently redacted.
3. Test `EV-AUD-04` asserts (2) fails loudly.

**On foreign object ids in denial events.** When a cross-tenant denial is recorded, `object_id` stores the id **the caller requested** and `organization_id` stores the **caller's own** organization. The foreign organization's id is **never** written — in the Pattern A cases the server never learned it, and in Pattern B cases writing it would move a foreign tenant's identifier into the caller's tenant partition of the audit trail. **This is a design decision that warrants management confirmation (D-7, §22).**

### 8.6 Concurrency, multiple workers, and why hash chaining is deferred

**Phase 1A's concurrency position:** there is none to manage. Events are independent `INSERT`s with a `UUID` PK. No application-level sequence, no lock, no read-modify-write. Multiple `uvicorn` workers and multiple concurrent requests contend only on the ordinary heap/index pages of one table. `record_out_of_band` opens a separate connection, but `app/infrastructure/db/session.py:32` already uses `NullPool`, so every session is a fresh connection — no pool-exhaustion interaction is introduced.

**Why a hash chain cannot simply be added on top of this, and must be its own story:**

1. **`BIGSERIAL` is non-transactional.** `recorded_seq` values are allocated outside the transaction, so a rolled-back transaction leaves a permanent gap. A chain over a gapped sequence cannot distinguish "gap from rollback" from "row deleted".
2. **Allocation order ≠ commit order.** Worker A may take `seq=100` and commit *after* worker B takes `seq=101` and commits. A verifier walking by `recorded_seq` would compute a different order than the one in which rows became visible — the chain would fail verification on a perfectly honest database.
3. **A correct chain needs `previous_hash` = the hash of the immediately preceding *committed* event for that organization.** That is a read-modify-write against a moving target, which under concurrency requires serialising every audit write for an organization behind a `SELECT … FOR UPDATE` on a per-organization counter row or a `pg_advisory_xact_lock`.
4. **That serialisation is a throughput and deadlock decision**, interacting with `record_in_transaction` (which rides a business transaction that may already hold locks — a genuine deadlock-ordering hazard). It needs its own design, its own load test, and its own acceptance test.

**Recommendation on integrity mechanism, in priority order** — for Phase 1B, not Phase 1A:

| Rank | Mechanism | Assessment |
|---|---|---|
| **1** | **Confirm and enforce a least-privilege database role** (`REVOKE UPDATE/DELETE`, non-owner application role) | Cheapest, largest real gain, and a prerequisite for every other option. Addresses §8.2's open question directly. |
| **2** | **Per-organization hash chain** with an advisory-lock-serialised sequence + a `verify_audit_chain` routine + a test that mutates a row via raw SQL and proves detection at that row | The Foundation Plan's FND-SEC-03 acceptance test (`FND_P0_Gap_Matrix.csv`, FND-SEC-03). Must be its own story. |
| **3** | **Periodic signed external export** (append-only object store, WORM or equivalent) | Detects wholesale table replacement, which a chain alone cannot. Depends on unresolved residency decisions M-2/M-3. |
| **4** | Postgres logical-replication audit sink to a separate instance | Strongest, highest operating cost. Not proportionate at current scale. |

### 8.7 `TIMESTAMPTZ` vs the existing convention

Every existing table uses naive `TIMESTAMP` (`12c7b2051fc6...py:36`, `sa.DateTime()` with `CURRENT_TIMESTAMP`). `audit_events.occurred_at` should be `TIMESTAMPTZ`: an audit record whose instant is ambiguous across deployment time zones is materially weaker evidence, and this is a **new** table so no migration of existing data is implied. This is an intentional, documented divergence, not an inconsistency. **[R]**

### 8.8 First operations that must write audit events

| # | Action | `action` | `result` | Write mode | Emission site | Server knows cross-tenant? |
|---|---|---|---|---|---|---|
| 1 | Profile not provisioned | `auth.profile_missing` | `DENIED` | out-of-band | `exceptions.py` handler | n/a |
| 2 | Invalid/absent token | `auth.token_rejected` | `DENIED` | out-of-band | `exceptions.py` handler | n/a |
| 3 | Cross-tenant denial (known) | `access.cross_tenant_denied` | `DENIED` | out-of-band | handler, via `CrossTenantAccessDenied` / `CrossTenantActionDenied` | **yes** |
| 4 | Denial or not-found (indistinguishable) | `access.denied_or_not_found` | `DENIED` | out-of-band | handler, plain `NotFoundError` | **no** |
| 5 | Document upload | `document.upload` | `SUCCESS` / `FAILED` | in-transaction | `document_upload.py` after `create` | — |
| 6 | Document processing | `document.process` | `SUCCESS` / `FAILED` | in-transaction | `document_processing.py` at completion | — |
| 7 | Embedding generation | `document.embeddings_generate` | `SUCCESS` / `FAILED` | in-transaction | `embedding_generation.py` at summary | — |
| 8 | AI analysis execution | `analysis.run` | `SUCCESS` / `FAILED` | in-transaction | `rag_analysis.py` at terminal state | — |
| 9 | Organization update | `organization.update` | `SUCCESS` | in-transaction | `organization.py:49-54` | — |
| 10 | Engagement create/update | `engagement.create` / `engagement.update` | `SUCCESS` | in-transaction | `engagement.py:67-82`, `111-137` | — |

**Note on #7 and #8.** `EmbeddingGenerationService` and `RagAnalysisService` deliberately commit at several points to publish concurrency facts other requests must observe (`document_chunk_embedding.py:69-210`; `rag_analysis.py:11-27` documents that no transaction is held across the LLM call). The audit write for these must be placed at the **terminal state transition** and must not extend any transaction across an external call. **Slice 5 must re-read those two services' transaction boundaries before placing the call — this is the highest-risk placement in Phase 1A.**

---

## 9. Proposed Isolated Test-Database Architecture

All of §9 is **[R]** except where marked.

### 9.1 Option comparison

| Criterion | **A. Docker Compose + pgvector** | B. Testcontainers | C. Dedicated test Supabase project |
|---|---|---|---|
| New Python dependency | **None** | `testcontainers[postgresql]` + `docker` SDK | None |
| Local developer setup | `docker compose -f docker-compose.test.yml up -d` | Docker daemon required, implicitly | Network + credentials required |
| CI implementation | GitHub Actions `services:` block — first-class, no Docker-in-Docker | Requires Docker socket in the runner | Requires secrets in CI |
| Can it reach shared Supabase? | **Physically impossible** — container-local, no credentials | Same | **It is remote infrastructure**; a URL typo reaches the wrong project |
| Per-run isolation | Fresh container or `DROP/CREATE SCHEMA` | Fresh container per session | Manual truncation; state persists between runs |
| Cost | **Zero** | Zero | **Recurring** |
| Speed | Fast; container reused locally | Slower — container start per session | Slowest — network round-trips |
| pgvector | `pgvector/pgvector:pg16` ships it | Same image | Present (0.8.2 per `3f3acc7fc556...py:9`) |
| Fidelity to production | High — same PG major, same extension | High | **Highest** — literally the same platform |
| Secrets in CI | None | None | **Required** |
| Closes M-11 without budget | **Yes** | Yes | No |

### 9.2 Recommendation — **Option A**

**Docker Compose locally + a GitHub Actions service container in CI, sharing one `pgvector/pgvector:pg16` image and one bootstrap SQL file.**

Rationale, in order of weight:
1. **It adds no dependency.** Testcontainers would require installing packages, which the current mandate forbids and which adds a Docker-daemon coupling to every developer's test run.
2. **It cannot reach shared Supabase**, because it has no credentials for it and no network path — a stronger property than any guard code.
3. **GitHub Actions `services:` is the natural CI primitive** and needs no Docker-in-Docker.
4. **It closes management decision M-11 at zero cost**, converting an open budget escalation into a completed engineering task.

Option C should be **rejected for Phase 1A**, and the reason is not cost: a remote test project is remote infrastructure reachable by a misconfigured URL, which is exactly the risk class the phase exists to eliminate. Option B remains a reasonable future migration if per-test database isolation is ever needed.

**Fidelity caveat, recorded as a risk (§18 R-4).** `pgvector/pgvector:pg16` will not necessarily carry pgvector 0.8.2, the version recorded for the Supabase instance (`3f3acc7fc556...py:9`). The image tag must be **pinned by digest**, and the actual `SELECT extversion FROM pg_extension WHERE extname='vector'` output captured as part of evidence `EV-TEST-DB-03`. Any divergence from 0.8.2 is a known, recorded limitation of the test environment, not a defect to be discovered later.

### 9.3 Composition

**`docker-compose.test.yml`** (repository root; **must not** reference `backend/.env`, unlike `docker-compose.yml:7-8`):

```yaml
services:
  test-db:
    image: pgvector/pgvector:pg16@sha256:<pinned-digest>
    environment:
      POSTGRES_USER: gh_test
      POSTGRES_PASSWORD: gh_test_local_only    # throwaway; never a real credential
      POSTGRES_DB: green_hubs_test             # name MUST end in _test (see 9.4)
    ports: ["55432:5432"]                      # non-default host port, so a stray
                                               # localhost:5432 URL cannot reach it
    volumes:
      - ./backend/tests/db/init:/docker-entrypoint-initdb.d:ro
    tmpfs: [/var/lib/postgresql/data]          # ephemeral: nothing survives the container
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U gh_test -d green_hubs_test"]
```

Three deliberate choices: **port 55432** so a mistaken `localhost:5432` never lands here; **`tmpfs`** so no data outlives the container; **no `env_file`** so no real credential is ever mounted.

**`backend/tests/db/init/001_test_marker.sql`** — the primary safety control:

```sql
CREATE TABLE gh_disposable_test_database (
    marker      text PRIMARY KEY,
    created_at  timestamptz NOT NULL DEFAULT now()
);
INSERT INTO gh_disposable_test_database (marker)
VALUES ('GH_SIP_DISPOSABLE_TEST_DB_DO_NOT_CREATE_ELSEWHERE');
```

**This table must never be created by an Alembic migration.** If it were, `alembic upgrade head` against shared Supabase would create the marker there and disarm the guard permanently. It is created only by the container's init hook and by the CI bootstrap step. This is the single most important implementation detail in Scope A.

### 9.4 The guard

`backend/tests/db_guard.py` **[R]** — pure, dependency-free, unit-testable without a database:

```python
ALLOWED_HOSTS   = {"localhost", "127.0.0.1", "::1", "test-db", "postgres"}
REQUIRED_DB_SUFFIX = "_test"
FORBIDDEN_SUBSTRINGS = ("supabase", "pooler", "rds.amazonaws", "neon.tech",
                        "azure", "render.com", "railway", "planetscale")
MARKER = "GH_SIP_DISPOSABLE_TEST_DB_DO_NOT_CREATE_ELSEWHERE"

def assert_isolated_test_database_url(url: str) -> None:
    """Five static checks, ALL of which must pass:
       1. url is non-empty and parses
       2. host in ALLOWED_HOSTS                      (positive allow-list)
       3. database name endswith REQUIRED_DB_SUFFIX  (defeats .env.example:11,
          which is itself a localhost URL — host checking alone is NOT enough)
       4. no FORBIDDEN_SUBSTRINGS anywhere in the url (defence in depth)
       5. url is not equal to settings.database_url  (never the configured
          application database, whatever it is)
    Raises RuntimeError with a message that NEVER echoes the URL — the
    connection string contains a password."""

async def assert_marker_present(session) -> None:
    """Runtime proof: SELECT marker FROM gh_disposable_test_database.
    A missing table or wrong marker raises. A shared or production
    database cannot satisfy this, because the marker is created only by
    the test bootstrap and by NO migration."""
```

**Check 5 and the marker together are what make this safe.** Static string checks can be defeated by a determined misconfiguration; a database that does not contain the marker table cannot be written to at all, regardless of what its URL looks like.

### 9.5 Wiring — respecting the import-time engine constraint (§3.3 C-3)

`backend/tests/conftest.py` currently reads (lines 1-12):

```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app          # ← line 4: transitively imports db.session,
                                  #   which builds the engine at import time
```

The environment selection must execute **above** line 4:

```python
# --- must run BEFORE any `app.*` import (see db/session.py:26-37) -------------
import os
from tests.db_guard import assert_isolated_test_database_url

_TEST_URL = os.environ.get("GH_TEST_DATABASE_URL")
if _TEST_URL:
    assert_isolated_test_database_url(_TEST_URL)
    os.environ["DATABASE_URL"] = _TEST_URL          # env var beats .env in
                                                    # pydantic-settings
# -----------------------------------------------------------------------------
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
```

A dedicated variable name `GH_TEST_DATABASE_URL` is used rather than overloading `DATABASE_URL`, so the intent to target a test database is explicit and a developer's existing `.env` is never consulted for it.

### 9.6 Converting the silent skip into a hard failure (§3.3 C-2)

A session-scoped autouse fixture in `backend/tests/conftest.py`:

```python
@pytest.fixture(scope="session", autouse=True)
def _integration_environment(request):
    """If the run selects integration tests, an isolated database is
    MANDATORY — never optional. This replaces the per-module
    `pytest.skip(...)` (test_document_repository.py:53-58 and 14 others),
    which silently reports green on a misconfigured CI job."""
    if not _integration_selected(request.config):
        return
    if not os.environ.get("GH_TEST_DATABASE_URL"):
        pytest.exit("Integration tests selected but GH_TEST_DATABASE_URL "
                    "is not set. Refusing to run against the configured "
                    "application database.", returncode=3)
```

The 15 existing per-module `_require_database_url` fixtures are **left in place**, unmodified. They become unreachable no-ops when the session fixture has already passed, which keeps the 144 tests literally unchanged — a hard requirement (§16 AC-13). Removing them is a Phase 1B cleanup.

### 9.7 Schema lifecycle and per-test isolation

**Schema creation: Alembic, once per session, never `create_all`.**

```python
@pytest.fixture(scope="session", autouse=True)
async def _migrated_schema(_integration_environment):
    """Runs the real chain eeb31636c877 → da0298a9c722 (8 migrations)
    against the isolated database. Using Alembic rather than
    Base.metadata.create_all is the entire point: it proves the migrations
    themselves are correct — including
    3f3acc7fc556:86 `CREATE EXTENSION IF NOT EXISTS vector`."""
```

Invoked in-process via `alembic.config.Config` + `command.upgrade(cfg, "head")`, with `sqlalchemy.url` set from the guarded test URL. Note `migrations/env.py:27` calls `get_settings()` at module import, so `DATABASE_URL` must already be the test URL — which §9.5 guarantees.

**Per-test isolation.** The 144 existing tests already clean up after themselves. The new mechanism must therefore be a *net* rather than a replacement:

- Recommended: a session-scoped `TRUNCATE … RESTART IDENTITY CASCADE` across all application tables **between test modules**, plus a **final** assertion that every table is empty at session end.
- **Not** recommended for Phase 1A: wrapping each test in an outer transaction and rolling back. Several repositories commit deliberately mid-operation (`document_chunk_embedding.py:69-210`; `rag_analysis.py` claim/retry paths), so an outer-transaction harness would change the behaviour those tests exist to verify.

New Phase 1A tests get a function-scoped `clean_database` fixture that truncates before *and* after, giving true per-test isolation for new work without touching old work.

### 9.8 CI integration

`.github/workflows/ci.yml` — the existing `backend` job (lines 8-25) is **left unchanged** so the fast gate stays fast; a **new parallel job** is added:

```yaml
  backend-integration:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: backend } }
    services:
      test-db:
        image: pgvector/pgvector:pg16@sha256:<pinned-digest>
        env:
          POSTGRES_USER: gh_test
          POSTGRES_PASSWORD: gh_test_ci_only     # throwaway; NOT a secret,
                                                 # and never from backend/.env
          POSTGRES_DB: green_hubs_test
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U gh_test -d green_hubs_test"
          --health-interval 5s --health-timeout 5s --health-retries 10
    env:
      GH_TEST_DATABASE_URL: postgresql+asyncpg://gh_test:gh_test_ci_only@localhost:5432/green_hubs_test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Create disposable-database marker
        run: psql "$PG_SYNC_URL" -f tests/db/init/001_test_marker.sql
      - name: Record pgvector version (evidence EV-TEST-DB-03)
        run: psql "$PG_SYNC_URL" -c "SELECT extname, extversion FROM pg_extension;"
      - name: Integration tests
        run: pytest -m integration -v
```

**Constraints this design satisfies:**
- No secret is used. `gh_test_ci_only` is a throwaway credential for a container that is destroyed with the job — it must **not** be stored in GitHub Secrets, because doing so would imply it is one.
- `backend/.env` is never read (Phase 1 backlog security consideration #8).
- The marker is created by an explicit CI step, **never** by a migration.
- Job failure blocks the PR — the 144 tests become a real gate.

**Python-version note.** This job pins 3.12 to match the existing gate. The local/CI drift (3.14.3 vs 3.12, Phase 0 S-8) is **not** resolved by Phase 1A and remains open.

---

## 10. Exact Migrations Expected

**Exactly one new Alembic migration.** No existing migration is edited. No existing table is altered.

| Item | Value |
|---|---|
| File | `backend/migrations/versions/<rev>_create_audit_events.py` |
| `down_revision` | `'da0298a9c722'` **[F]** — current head (`da0298a9c722_create_analysis_runs_and_source_.py:59-60`) |
| `upgrade()` | `op.create_table('audit_events', …)` per §8.1; 4 indexes; 3 CHECK constraints; then `op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM CURRENT_USER")` **guarded by an existence check on the role** |
| `downgrade()` | `op.drop_table('audit_events')` — self-contained; touches nothing else |

**Not in this migration, deliberately:**

| Excluded | Reason |
|---|---|
| Any change to `organizations`, `users`, `engagements`, `documents`, `extracted_text`, `document_chunks`, `document_chunk_embeddings`, `analysis_runs`, `analysis_source_references`, `ai_analysis_results` | Phase 1A is purely additive |
| `documents.processing_status` new values (`PENDING_SCAN`, `QUARANTINED`) | FND-SEC-02, out of scope |
| RLS policies / `ENABLE ROW LEVEL SECURITY` | Phase 1B; needs the isolated DB to be verifiable |
| Hash-chain columns | §8.6 |
| `gh_disposable_test_database` marker table | **Must never be a migration** — §9.3 |
| A permission/policy assignment table | Blocked on M-4 |

**Migration risk to state explicitly.** The `REVOKE` statement's effect depends on the application's actual database role (§8.2). If the application connects as the table owner or a superuser, the `REVOKE` is a no-op against it. The migration must therefore be written so that a no-op `REVOKE` does not fail the migration, and the **investigation of the actual role is a required Slice 3 deliverable** whose answer determines what the evidence pack may claim.

---

## 11. Exact Backend Files Expected to Change

### 11.1 New files (14)

| # | Path | Contents |
|---|---|---|
| 1 | `backend/app/core/correlation.py` | `_correlation_id` ContextVar, `get_correlation_id()`, `CorrelationIdMiddleware` |
| 2 | `backend/app/domain/request_context.py` | `RequestContext` frozen dataclass (§5.1) |
| 3 | `backend/app/domain/security/__init__.py` | package marker |
| 4 | `backend/app/domain/security/permissions.py` | `Permission` StrEnum (12), `PERMISSION_CATALOG` |
| 5 | `backend/app/domain/security/policy.py` | `PolicyId`, `IPermissionResolver` Protocol |
| 6 | `backend/app/domain/security/route_registry.py` | `ROUTE_PERMISSIONS`, `UNGUARDED_ROUTES` (§7.6) |
| 7 | `backend/app/domain/entities/audit_event.py` | `AuditEvent` frozen dataclass |
| 8 | `backend/app/domain/repositories/audit_event.py` | `IAuditEventRepository` — `append`, `list_for_organization` **only** |
| 9 | `backend/app/infrastructure/db/models/audit_event.py` | `AuditEventModel` |
| 10 | `backend/app/infrastructure/repositories/audit_event.py` | `SQLAlchemyAuditEventRepository` — **does not** extend `base.py:32-52` |
| 11 | `backend/app/infrastructure/security/static_policy_resolver.py` | `StaticPolicyResolver`, empty map (§7.4) |
| 12 | `backend/app/services/audit.py` | `AuditService` — two write modes, allow-list builders, denylist check |
| 13 | `backend/app/services/audit_payloads.py` | Per-object-type state allow-lists (§8.5) |
| 14 | `backend/migrations/versions/<rev>_create_audit_events.py` | §10 |

### 11.2 Modified files (12)

| # | Path | Change | Anchor |
|---|---|---|---|
| 1 | `backend/app/core/exceptions.py` | Add `CrossTenantAccessDenied(NotFoundError)` and `CrossTenantActionDenied(AuthorizationError)`; emit denial audit inside `handle_app_error` | after `:50-51`; handler `:54-60` |
| 2 | `backend/app/core/config.py` | Add `audit_enabled: bool = True`, `audit_failure_mode: str = "log"` (pending D-3). **No credential or URL field added.** | after `:123` |
| 3 | `backend/app/core/logging.py` | Add correlation id to the format string | `:6-10` |
| 4 | `backend/app/main.py` | Register `CorrelationIdMiddleware` after `CORSMiddleware` | `:37-45` |
| 5 | `backend/app/api/deps.py` | Add `get_request_context`, `get_permission_resolver`, `get_audit_event_repository`, `get_audit_service`, `require_permission` | append after `:137` |
| 6 | `backend/app/infrastructure/db/models/__init__.py` | Export `AuditEventModel` so Alembic autogenerate sees it | — |
| 7 | `backend/app/services/organization.py` | `NotFoundError` → `CrossTenantAccessDenied` at the known-cross-tenant raise; success audit on `update` | `:74`; `:49-54` |
| 8 | `backend/app/services/engagement.py` | `AuthorizationError` → `CrossTenantActionDenied` ×3; success audit on create/update | `:72`, `:103`, `:127`; `:67-82`, `:111-137` |
| 9 | `backend/app/services/document_upload.py` | `AuthorizationError` → `CrossTenantActionDenied`; success audit after create | `:103`; `:90-153` |
| 10 | `backend/app/services/document_processing.py` | Same; success audit at completion | `:142`; `:128-…` |
| 11 | `backend/app/services/embedding_generation.py` | `NotFoundError` → `CrossTenantAccessDenied`; success audit at summary | `:115`; `:101-…` |
| 12 | `backend/app/services/vector_retrieval.py` + `backend/app/services/analysis/rag_analysis.py` | `NotFoundError` → `CrossTenantAccessDenied` at known-cross-tenant raises; success audit at analysis terminal state | `vector_retrieval.py:68,79`; `rag_analysis.py:178,199` |

### 11.3 Configuration / infrastructure files

| Path | Change |
|---|---|
| `backend/pytest.ini` | Register new markers (`audit`, `security`); no change to `integration`'s meaning |
| `backend/requirements-dev.txt` | **Optionally** add `pytest-cov` (Phase 1 backlog D-2). Not required for Phase 1A acceptance; call it out for approval rather than adding silently |
| `.github/workflows/ci.yml` | Add the `backend-integration` job (§9.8). Existing jobs untouched |
| `docker-compose.test.yml` | **New** (root). `docker-compose.yml` untouched |
| `backend/tests/db/init/001_test_marker.sql` | **New** |
| `backend/.env.example` | Add a **commented** `# GH_TEST_DATABASE_URL=postgresql+asyncpg://gh_test:gh_test_local_only@localhost:55432/green_hubs_test` line and a warning that `DATABASE_URL` must never point at a test database. **No value in `.env` is read or changed.** |
| `backend/README.md`, `backend/CLAUDE.md` | Correct the stale statements recorded as Phase 0 D-1/D-2; add the test-environment runbook |

### 11.4 Explicitly NOT modified

`app/infrastructure/security/supabase_jwt.py` · `app/api/deps.py:121-137` (existing auth dependencies) · `app/infrastructure/db/session.py` · `app/infrastructure/ai/*` · `app/infrastructure/documents/*` · `app/infrastructure/storage/*` · `app/services/analysis/prompts.py`, `structured_output.py`, `request_hash.py` · `app/domain/repositories/*` (existing) · every existing migration · `app/schemas/*` (no response shape changes) · `backend/.env` · `frontend/.env*`

---

## 12. Exact Frontend Files Expected to Change

**None. [F]**

Justification, from direct reading:

1. **No new status code or response shape is introduced.** `CrossTenantAccessDenied` inherits `status_code = 404` (`app/core/exceptions.py:26-27`) and `CrossTenantActionDenied` inherits `403` (`:42-43`). The `{"detail": "<message>"}` envelope (`:58-60`) and message texts are unchanged.
2. **403 is already handled distinctly and actionably.** `frontend/src/lib/api/errors.ts:26-31` defines `ForbiddenError`; `:69` maps 403 to `"You don't have permission to do this."`; `:99-111` routes status → typed error. The Phase 1 backlog's frontend item (`Phase1_Recommended_Backlog.md:141`) is therefore **already satisfied** by existing code.
3. **No permission is enforced on any endpoint in Phase 1A** (§7), so no UI affordance changes.
4. **`X-Request-Id` is response-only.** The client need not send or read it; surfacing it in error UI is a Phase 1B nicety, not a requirement.

**Not to be touched in Phase 1A:** `frontend/src/features/rbac/roles.ts` — reconciling the five UI tiers with the server model is blocked on M-4 and is a Phase 1B task. Changing it now would embed an unapproved authority model in the UI.

---

## 13. Exact Test Files Expected to Change or Be Created

### 13.1 New test files (11)

| # | Path | Type | Fixtures required | Evidence ID |
|---|---|---|---|---|
| 1 | `backend/tests/test_db_guard.py` | unit (no DB) | none | **EV-TEST-DB-01** |
| 2 | `backend/tests/integration/test_isolated_environment.py` | integration | `_integration_environment`, `_migrated_schema`, `db_session` | **EV-TEST-DB-02**, **EV-TEST-DB-03** |
| 3 | `backend/tests/api/test_request_context.py` | unit/API | `client`, `override_current_user`, `fake_verifier` | **EV-SEC-CTX-01** |
| 4 | `backend/tests/core/test_correlation.py` | unit | `client` | **EV-SEC-CTX-02** |
| 5 | `backend/tests/api/test_tenant_isolation_matrix.py` | API (fakes) | `client`, `two_tenant_users`, `fake_repositories` | **EV-SEC-TENANT-01** |
| 6 | `backend/tests/api/test_tenant_isolation_matrix_integration.py` | integration | isolated DB, two real tenants | **EV-SEC-TENANT-02** |
| 7 | `backend/tests/services/test_audit_service.py` | unit | `fake_audit_repository`, `frozen_clock` | **EV-AUD-01** |
| 8 | `backend/tests/infrastructure/repositories/test_audit_event_repository.py` | integration | isolated DB, `clean_database` | **EV-AUD-01**, **EV-AUD-03** |
| 9 | `backend/tests/api/test_audit_denials_integration.py` | integration | isolated DB, two tenants, `clean_database` | **EV-AUD-02** |
| 10 | `backend/tests/security/test_permission_framework.py` | unit | none | **EV-SEC-PERM-01/02/03** |
| 11 | `backend/tests/security/test_route_permission_registry.py` | unit (structural) | live `app` route table | **EV-SEC-PERM-04** |

Plus package markers: `backend/tests/integration/__init__.py`, `backend/tests/security/__init__.py`, `backend/tests/db/__init__.py`.

### 13.2 Modified test files (1, plus a hard constraint on 15)

| Path | Change |
|---|---|
| `backend/tests/conftest.py` | **The only existing test file that changes.** Adds the pre-import env selection (§9.5), the session guard (§9.6), `_migrated_schema` (§9.7), `db_session`, `clean_database`, `two_tenant_users`. The existing `client` fixture (`:8-12`) is preserved verbatim. |

**Hard constraint (acceptance criterion AC-13).** The **15 existing integration modules and 142 test functions must not be edited at all** — including their 15 per-module `_require_database_url` skip fixtures. Their unmodified passage against the isolated database *is* the evidence that Phase 1A changed no behaviour. Any edit to them invalidates that evidence.

### 13.3 Test specifications

#### Tenant tests — **EV-SEC-TENANT-01** (API, fakes) / **EV-SEC-TENANT-02** (integration, real DB)

| ID | Test | Type | File | Fixtures | Asserts |
|---|---|---|---|---|---|
| TN-1 | Authenticated user reads own-organization document | integration | `test_tenant_isolation_matrix_integration.py` | isolated DB, `two_tenant_users` | 200, correct body |
| TN-2 | User A `GET /documents/{B's id}` | both | both matrix files | as above | **404**, `detail` identical to a nonexistent id |
| TN-3 | User A `POST /documents/{B's id}/process` | both | as above | **403** (`document_processing.py:142`), no state change on B's row |
| TN-4 | Client-supplied `organization_id` cannot widen: `POST /engagements` with B's org | both | as above | **403**; no row created in either tenant |
| TN-5 | Client-supplied `organization_id` in `GET /engagements?organization_id=<B>` | both | as above | **403**; **and** no B row ever appears in any response |
| TN-6 | Foreign existence not disclosed: response to TN-2 is byte-identical to a random UUID request | both | as above | equal status **and** equal `detail` string |
| TN-7 | Null-organization profile denied safely | API | `test_tenant_isolation_matrix.py` | `user_without_organization` | **403**, message exactly `"User has no organization"` (unchanged from `organization.py:64`) |
| TN-8 | User A cannot modify B's organization via `PATCH /organizations/{B}` | both | as above | **404**; B's row unchanged (verified by direct read) |
| TN-9 | Cross-tenant retrieval returns zero of B's chunks | integration | integration matrix file | seeded embeddings both tenants | empty/own-only; exercises `document_chunk_embedding.py:232` |
| TN-10 | Repository-layer scope: `list_read_models_for_organization` never returns foreign rows | integration | integration matrix file | isolated DB | direct repository assertion — covers finding **T-7** |

#### Request-context tests — **EV-SEC-CTX-01 / 02**

| ID | Test | Type | File | Fixtures | Asserts |
|---|---|---|---|---|---|
| RC-1 | Valid context resolved | unit | `test_request_context.py` | `override_current_user` | all fields populated; `organization_id` matches profile |
| RC-2 | Missing user profile | unit | same | repo returns `None` | `ProfileNotProvisionedError` → **403** (unchanged, `deps.py:135-136`) |
| RC-3 | Missing organization | unit | same | user with `organization_id=None` | `AuthorizationError` **403**, message unchanged |
| RC-4 | Invalid/absent token | unit | same | no/garbage bearer | **401**, generic message (unchanged) |
| RC-5 | Context is immutable | unit | same | none | assignment raises `FrozenInstanceError` |
| RC-6 | `organization_id` cannot come from the client | unit | same | request with `X-Organization-Id` header **and** body field | context still equals the profile's value |
| RC-7 | Correlation id reaches downstream code | unit | `test_correlation.py` | `client` | value read inside a fake service equals response `X-Request-Id` |
| RC-8 | Correlation id unique per request, and concurrent requests do not bleed | unit | same | `client`, `asyncio.gather` | N distinct ids; each task reads its own |
| RC-9 | Hostile inbound `X-Request-Id` rejected | unit | same | header with 5 KB / CRLF / SQL payload | replaced with a server uuid4; never echoed raw |

#### Audit tests — **EV-AUD-01 / 02 / 03 / 04**

| ID | Test | Type | File | Fixtures | Asserts |
|---|---|---|---|---|---|
| AU-1 | Successful upload writes exactly one `document.upload` `SUCCESS` event | integration | `test_audit_denials_integration.py` | isolated DB, `clean_database` | count == 1; actor, org, object, correlation all correct |
| AU-2 | Cross-tenant denial writes `access.cross_tenant_denied` `DENIED` **and no business row** | integration | same | as above | event present; target row unchanged |
| AU-3 | **Denial event survives the request rollback** | integration | same | as above | proves `record_out_of_band` (§4.3); this is the test that would fail on a naive single-session design |
| AU-4 | **Failed business op writes no `SUCCESS` event** | integration | same | forced repository failure | zero `SUCCESS` events for that correlation id; proves `record_in_transaction` |
| AU-5 | `UPDATE audit_events` via the app session raises | integration | `test_audit_event_repository.py` | isolated DB | `ProgrammingError`/`InsufficientPrivilege`. **Records the actual DB role as evidence (§8.2)** |
| AU-6 | `DELETE FROM audit_events` raises | integration | same | as above | same |
| AU-7 | Repository exposes no mutation method | unit | `test_audit_service.py` | none | `not hasattr(repo,'update')`, `not hasattr(repo,'delete')`; asserts `IAuditEventRepository` does not inherit `BaseRepository` |
| AU-8 | No public API can modify an audit event | integration | `test_audit_denials_integration.py` | isolated DB | walk `app.routes`: no route path contains `audit`; no `PUT`/`PATCH`/`DELETE` reaches the table |
| AU-9 | Secret-shaped payload is **rejected loudly** | unit | `test_audit_service.py` | none | `ValueError` for each denylisted key |
| AU-10 | Document content never enters a payload | integration | `test_audit_denials_integration.py` | real PDF fixture | a known phrase from the PDF appears **nowhere** in any event row |
| AU-11 | Email/full name never appear | unit | `test_audit_service.py` | user with known email | email absent from every field |
| AU-12 | Concurrent writes from independent sessions all persist | integration | `test_audit_event_repository.py` | isolated DB, `asyncio.gather(20)` | 20 rows; 20 distinct `recorded_seq`; no deadlock |
| AU-13 | `request_path` stores the route template, not the concrete path | integration | same | as above | `"/api/v1/documents/{document_id}"`, no UUID in the string |

#### Permission-framework tests — **EV-SEC-PERM-01 … 04**

| ID | Test | Type | File | Asserts |
|---|---|---|---|---|
| PM-1 | Unmapped policy resolves to empty set | unit | `test_permission_framework.py` | `resolve() == frozenset()`; **no exception** |
| PM-2 | `None` policy id resolves to empty set | unit | same | as above |
| PM-3 | Empty resolution → `require_permission` denies | unit | same | `AuthorizationError`, **403** |
| PM-4 | Resolver returning `None` (contract violation) → deny, not crash | unit | same | `AuthorizationError`, not `TypeError` |
| PM-5 | Client-supplied role/permission is ignored | unit | same | request carrying `X-Role: owner`, body `role`, `permissions[]`, **and a forged JWT `role` claim** → still denied |
| PM-6 | Denial message leaks nothing | unit | same | message contains no permission name, no policy id, no object id |
| PM-7 | Unknown permission is a **static** error | unit | same | catalog membership asserted; mypy gate (`ci.yml:23`) covers the type case |
| PM-8 | Every route is declared | unit (structural) | `test_route_permission_registry.py` | every `app.routes` entry is in `ROUTE_PERMISSIONS` **or** `UNGUARDED_ROUTES`; a new undeclared route **fails CI** |
| PM-9 | The Phase 1A policy map is empty | unit | `test_permission_framework.py` | `StaticPolicyResolver._POLICIES == {}` — makes any accidental population a deliberate, reviewed change |
| PM-10 | No temporary/test policy exists | unit | same | no environment variable or flag can populate the map (§7.7) |

#### Integration-environment tests — **EV-TEST-DB-01 / 02 / 03 / EV-CI-01**

| ID | Test | Type | File | Asserts |
|---|---|---|---|---|
| DB-1 | Guard rejects a Supabase-shaped URL | unit | `test_db_guard.py` | `RuntimeError`; **synthetic URL only, never a real host** |
| DB-2 | Guard rejects a localhost URL without the `_test` suffix — i.e. `.env.example:11`'s own default | unit | same | `RuntimeError` |
| DB-3 | Guard rejects a URL equal to `settings.database_url` | unit | same | `RuntimeError` |
| DB-4 | Guard error message never echoes the URL | unit | same | password substring absent from the message |
| DB-5 | Guard accepts the canonical test URL | unit | same | returns `None` |
| DB-6 | Marker check fails on a database without the marker table | integration | `test_isolated_environment.py` | raises |
| DB-7 | Marker check passes on the isolated database | integration | same | passes; **EV-TEST-DB-01** |
| DB-8 | All 8 migrations applied; `alembic_version` == `da0298a9c722` (or the new head) | integration | same | **EV-TEST-DB-02** |
| DB-9 | pgvector present; version recorded | integration | same | `SELECT extversion …` non-null; value captured in evidence; **EV-TEST-DB-03** |
| DB-10 | A `vector(1536)` insert + cosine query works | integration | same | proves the extension is functional, not merely installed |
| DB-11 | State isolated between tests (part A writes, part B sees nothing) | integration | same | two ordered tests with `clean_database` |
| DB-12 | Session ends with every application table empty | integration | same (session teardown) | no residue |
| DB-13 | All 142 existing integration functions pass **unmodified** | integration | existing 15 modules | **EV-CI-01** — the acceptance test of Slice 1 |

### 13.4 Regression gate (the hard one)

| ID | Test | Asserts |
|---|---|---|
| RG-1 | All 442 existing non-integration backend tests pass **unmodified** | zero edits to any existing test file except `conftest.py` |
| RG-2 | All 151 frontend tests pass unmodified | no frontend change (§12) |
| RG-3 | `ruff check .`, `mypy app` clean | matches `ci.yml:21,23` |
| RG-4 | Status code + `detail` string for every existing error path unchanged | snapshot comparison before/after the `CrossTenant*` substitution |

---

## 14. Implementation Slices in the Safest Order

Each slice is independently mergeable, independently revertible, and ends with a green full suite.

### Slice 1 — Isolated test environment *(no application file changes)*

**Files:** `docker-compose.test.yml`, `backend/tests/db/init/001_test_marker.sql`, `backend/tests/db_guard.py`, `backend/tests/conftest.py`, `backend/tests/test_db_guard.py`, `backend/tests/integration/test_isolated_environment.py`, `.github/workflows/ci.yml`, `backend/README.md`
**Exit:** DB-1…DB-13 pass; the 142 existing integration tests pass **unmodified** in CI; RG-1…RG-3 green.
**Evidence:** EV-TEST-DB-01, EV-TEST-DB-02, EV-TEST-DB-03, EV-CI-01
**Why first:** every later slice's acceptance test needs a real database. Ordering anything before this means writing security code that cannot be verified. It also closes M-11 at zero cost.

### Slice 2 — Correlation ID + `RequestContext` *(additive; nothing consumes it)*

**Files:** `app/core/correlation.py`, `app/core/logging.py`, `app/main.py`, `app/domain/request_context.py`, `app/api/deps.py`, `tests/core/test_correlation.py`, `tests/api/test_request_context.py`
**Exit:** RC-1…RC-9 pass; RG-1…RG-4 green.
**Evidence:** EV-SEC-CTX-01, EV-SEC-CTX-02
**Why second:** the audit spine needs a correlation id and a trusted actor/tenant object. Zero behavioural risk — no existing code path reads either.

### Slice 3 — Audit spine *(table, entity, repository, service — no call sites)*

**Files:** the migration, `app/domain/entities/audit_event.py`, `app/domain/repositories/audit_event.py`, `app/infrastructure/db/models/audit_event.py` (+ `models/__init__.py`), `app/infrastructure/repositories/audit_event.py`, `app/services/audit.py`, `app/services/audit_payloads.py`, `app/api/deps.py`, `app/core/config.py`, `tests/services/test_audit_service.py`, `tests/infrastructure/repositories/test_audit_event_repository.py`
**Also:** **investigate and record the application's actual database role and privileges** (§8.2) — a required written finding, not an optional note.
**Exit:** AU-5…AU-7, AU-9, AU-11…AU-13 pass; migration up **and down** verified on the isolated DB.
**Evidence:** EV-AUD-03 (including the DB-role finding)
**Why third:** the highest-risk artefact (a migration) lands with nothing depending on it, so a rollback is a single `downgrade()`.

### Slice 4 — Denial auditing *(the first behavioural change)*

**Files:** `app/core/exceptions.py`, the 7 services listed in §11.2 rows 7-12, `tests/api/test_tenant_isolation_matrix.py`, `tests/api/test_tenant_isolation_matrix_integration.py`, `tests/api/test_audit_denials_integration.py`
**Exit:** TN-1…TN-10, AU-2, AU-3, AU-8 pass; **RG-4 is the gate** — every status code and `detail` string byte-identical to pre-slice.
**Evidence:** EV-SEC-TENANT-01, EV-SEC-TENANT-02, EV-AUD-02
**Why fourth:** it changes exception *types* on live paths. It must land alone, after the spine is proven, with the regression snapshot as the gate.

### Slice 5 — Success-path auditing

**Files:** `app/services/document_upload.py`, `document_processing.py`, `embedding_generation.py`, `analysis/rag_analysis.py`, `organization.py`, `engagement.py`; `tests/api/test_audit_denials_integration.py` (extended)
**Exit:** AU-1, AU-4, AU-10 pass; existing service tests unmodified and green.
**Evidence:** EV-AUD-01
**Why fifth:** it touches the embedding and analysis services, whose transaction boundaries are deliberate and delicate (`document_chunk_embedding.py:69-210`; `rag_analysis.py:11-27`). **Re-read both before writing a line.** Highest placement risk in the phase.

### Slice 6 — Permission framework *(zero endpoints wired)*

**Files:** `app/domain/security/*`, `app/infrastructure/security/static_policy_resolver.py`, `app/api/deps.py`, `tests/security/test_permission_framework.py`, `tests/security/test_route_permission_registry.py`
**Exit:** PM-1…PM-10 pass; the route registry enumerates all 20 operations; RG-1…RG-4 green.
**Evidence:** EV-SEC-PERM-01…04
**Why last:** it is the only slice with **no** behavioural effect, so it carries the least urgency and the least risk. It also produces the artefact the M-4 conversation needs.

---

## 15. Acceptance Criteria

Phase 1A is complete when **all** of the following hold and are evidenced.

### Scope A

- **AC-1** `pytest -m integration` against the isolated database runs **142 existing test functions with zero source edits** to those 15 modules, and reports pass/fail — never "skipped".
- **AC-2** A run with `GH_TEST_DATABASE_URL` unset and integration selected **exits non-zero** with an explicit refusal. Demonstrated.
- **AC-3** The guard rejects, in unit tests using synthetic URLs only: a Supabase-shaped host; a localhost URL without the `_test` suffix; a URL equal to `settings.database_url`. No real host is contacted.
- **AC-4** Against a database lacking `gh_disposable_test_database`, the marker check raises before any DDL or DML.
- **AC-5** The full 8-migration chain applies to an empty database; `alembic_version` matches head; `downgrade` of the new migration is verified.
- **AC-6** pgvector is present and **functional** — a `vector(1536)` insert and a cosine query succeed. The installed version is recorded.
- **AC-7** CI runs the integration job on every push and PR; the job **fails the build** on any integration-test failure.
- **AC-8** No secret, and no value from `backend/.env`, is referenced by any test-environment file. Verified by reading `docker-compose.test.yml` and the CI job.

### Scope B

- **AC-9** `RequestContext` is constructible **only** via `get_request_context`; `organization_id` is non-optional and provably sourced from `public.users`.
- **AC-10** A request carrying an organization id in a header, a body field, **and** a forged JWT claim still yields a context whose `organization_id` equals the stored profile's.
- **AC-11** A correlation id exists for every request, is readable by downstream code without a signature change, is unique per request, does not bleed across concurrent requests, and is returned as `X-Request-Id`.
- **AC-12** The endpoint tenant-control matrix (§6.1) is re-verified post-change: all 20 rows behave as documented.
- **AC-13** **All 593 existing tests pass with zero edits** to any test file other than `backend/tests/conftest.py`. Status codes and `detail` strings are byte-identical on every existing error path.

### Scope C

- **AC-14** The catalog contains exactly the 12 named capabilities; no role name, person, email or user id appears anywhere in `app/domain/security/`.
- **AC-15** An unmapped or `None` policy resolves to the empty set **without raising**, and `require_permission` denies with 403 and a message naming nothing.
- **AC-16** `require_permission` is applied to **zero** production endpoints, and this is asserted by test — the restriction is enforced, not just documented.
- **AC-17** Every route in `app.routes` is declared in `ROUTE_PERMISSIONS` or `UNGUARDED_ROUTES`; adding an undeclared route fails CI.
- **AC-18** No environment variable, setting, or flag can populate the policy map.

### Scope D

- **AC-19** `audit_events` exists with every column in §8.1; `IAuditEventRepository` exposes no update or delete; it does not inherit `BaseRepository`.
- **AC-20** A raw `UPDATE` and a raw `DELETE` through the application session both fail — **or**, if the application's database role makes `REVOKE` ineffective, that fact is recorded in EV-AUD-03 and the claim is downgraded to "append-only by application construction" everywhere it appears.
- **AC-21** Each of the ten operations in §8.8 writes exactly one event with the correct actor, organization, object, result and correlation id.
- **AC-22** A denied cross-tenant attempt writes a `DENIED` event **and** no business row (AU-3).
- **AC-23** A failed business operation writes **no** `SUCCESS` event (AU-4).
- **AC-24** No document content, token, secret, email or full name appears in any event, proven by a positive-control test (AU-10: a known phrase from a real test PDF is absent from every row).
- **AC-25** 20 concurrent audit writes from independent sessions all persist, with no deadlock and no lost row.
- **AC-26** **No document, comment, commit message, or evidence artefact describes Phase 1A's audit trail as tamper-evident, immutable, or tamper-proof.** Verified by grep across `backend/` and `project-governance/` before sign-off.

### Scope E

- **AC-27** Every test in §13.3 exists at the stated path, passes, and is mapped to its evidence ID.
- **AC-28** The evidence pack (§17) is complete, with the raw command output retained for EV-TEST-DB-01, EV-SEC-TENANT-02, EV-AUD-02, EV-AUD-03 and EV-CI-01.
- **AC-29** `ruff check .` and `mypy app` clean; frontend gates untouched and green.

---

## 16. Test Plan

### 16.1 Layers and what each proves

| Layer | Count (new) | Marker | Runtime | Proves |
|---|---|---|---|---|
| Unit — pure logic (guard, permissions, audit payloads, correlation) | ~40 | none | < 1 s | Fail-closed semantics, redaction, immutability |
| API — fakes, no DB (tenant matrix, request context) | ~20 | none | < 2 s | Router→service→context wiring; 404/403 discipline |
| Integration — isolated PostgreSQL + pgvector | ~35 | `integration` | ~30-90 s | SQL-layer tenant isolation; append-only; migrations; pgvector |
| Structural — route registry | 1 | none | < 1 s | No endpoint can be added unguarded |
| Regression — existing 593 | 0 new | mixed | ~15 s + integration | Nothing changed |

### 16.2 Execution matrix

| Command | Where | Gate |
|---|---|---|
| `pytest -m "not integration"` | CI job `backend` (`ci.yml:25`, unchanged) | **Blocking** |
| `pytest -m integration` | CI job `backend-integration` (**new**) | **Blocking** |
| `ruff check .` / `mypy app` | CI job `backend` (unchanged) | **Blocking** |
| `npm run lint/typecheck/test/build` | CI job `frontend` (unchanged) | **Blocking** |
| `docker compose -f docker-compose.test.yml up -d` then `GH_TEST_DATABASE_URL=… pytest -m integration` | Local | Developer loop |

### 16.3 Test-data policy

- **Synthetic only.** Every fixture generates `uuid4()` identifiers, `example.test` email domains, and lorem-style document text.
- **No real client, Aramco, or personal data — ever.** Restated because the audit-content tests (AU-10) deliberately search event rows for document text, and the fixture PDF must therefore be one this document authorises: a generated PDF containing a known nonsense phrase.
- **No external service is called.** LLM and embedding calls stay intercepted via `httpx.MockTransport`, as the existing suite already does (`tests/infrastructure/ai/test_openai_llm_gateway.py`). **No integration test may call OpenAI or OpenRouter.** Supabase Storage and JWKS stay faked, following the existing pattern at `tests/api/test_documents_read_integration.py:73-88`.

### 16.4 Negative-test emphasis

Of the ~96 new tests, **roughly 60 are negative** — denial, rejection, absence, and non-disclosure. That ratio is deliberate: for a security foundation, the assertion that something *cannot* happen is the deliverable. Two specific negative tests are the phase's most valuable and must not be dropped under schedule pressure:

- **AU-3** — a denial event survives the request rollback. A naive single-session audit design passes every other audit test and fails this one.
- **TN-6** — the response to a foreign object is *byte-identical* to the response for a nonexistent one. Any future refactor that differentiates them re-introduces existence disclosure.

---

## 17. Evidence Plan

| Evidence ID | Artefact | Produced by | Retained | Owner |
|---|---|---|---|---|
| **EV-TEST-DB-01** | Isolated-database refusal demonstration: full output of (a) an integration run with `GH_TEST_DATABASE_URL` unset → non-zero exit; (b) the guard rejecting three synthetic hostile URLs; (c) the marker check failing on a marker-less DB | DB-1…DB-7, AC-2/AC-3/AC-4 | Console output + test report | Technical Lead |
| **EV-TEST-DB-02** | Migration record: `alembic upgrade head` output on an empty DB, `alembic_version` query result, `\dt` table list, verified `downgrade` of the new migration | DB-8, AC-5 | Console output | Technical Lead |
| **EV-TEST-DB-03** | pgvector record: `SELECT extname, extversion FROM pg_extension` plus a functional `vector(1536)` insert + cosine query, **with the version divergence from Supabase's 0.8.2 explicitly stated** | DB-9, DB-10, AC-6 | Console output | Technical Lead |
| **EV-SEC-TENANT-01** | Tenant-control matrix (§6.1) re-verified at the API layer, all 20 rows, with per-row status codes | TN-1…TN-8 (fakes) | Test report + matrix | Security Reviewer |
| **EV-SEC-TENANT-02** | The same matrix verified **at the SQL layer** against the isolated database, including the repository-level assertions covering finding T-7, **plus the 142 pre-existing integration tests passing unmodified** | TN-1…TN-10 (integration), DB-13 | Test report | Security Reviewer |
| **EV-SEC-CTX-01** | Request-context resolution record: the nine RC cases, including the client-supplied-organization-id rejection with header + body + forged claim | RC-1…RC-6 | Test report | Technical Lead |
| **EV-SEC-CTX-02** | Correlation-id propagation record, including concurrency non-bleed and hostile-header handling | RC-7…RC-9 | Test report | Technical Lead |
| **EV-AUD-01** | Audit coverage record: one row per operation in §8.8, showing the recorded event with actor, org, object, result, correlation id — **and the redaction positive control (AU-10)** | AU-1, AU-4, AU-10…AU-13 | Test report + sample rows (synthetic) | Security Reviewer |
| **EV-AUD-02** | Denial-audit record: cross-tenant denial writes an event while writing no business row, **and survives the request rollback** | AU-2, AU-3, AU-8 | Test report | Security Reviewer |
| **EV-AUD-03** | **Append-only statement**: the `UPDATE`/`DELETE` failure output, the repository-interface assertion, **and the written finding on the application's actual database role and privileges**, with an explicit statement of what may and may not be claimed | AU-5…AU-7, AC-20 | Test output + written finding | Security Reviewer |
| **EV-SEC-PERM-01** | Permission catalog + resolver contract, with the deny-by-default demonstrations | PM-1…PM-4, PM-6 | Test report + catalog | Technical Lead |
| **EV-SEC-PERM-02** | Client-supplied role/permission rejection record | PM-5 | Test report | Security Reviewer |
| **EV-SEC-PERM-03** | Statement that the policy map is empty and that no endpoint is guarded, with the tests that enforce both | PM-9, PM-10, AC-16 | Test report | Technical Lead |
| **EV-SEC-PERM-04** | Route-declaration inventory: all 20 operations, each guarded or explicitly unguarded with a justification — **the input artefact for the M-4 decision** | PM-8 | Registry file + test report | Technical Lead → Founder |
| **EV-CI-01** | CI gate record: a PR run showing both backend jobs green, the integration job executing 142+ tests, and a deliberately-failing integration test blocking the merge | AC-1, AC-7, DB-13 | CI run URL + logs | Technical Lead |
| **EV-ARC-01** | This document, approved, plus the audit transaction-semantics decision (§8.3 / D-3) as recorded | — | Governance record | Technical Lead |

**Evidence integrity rules.** Every artefact records the command, working directory, commit SHA, and full output. No evidence may contain a real credential, a real connection string, a token, or any real document content. Any test output containing a connection string is redacted at the host portion before retention.

---

## 18. Risks and Mitigations

| # | Risk | L / I | Mitigation | Owner |
|---|---|---|---|---|
| **R-1** | **The 142 integration tests fail on first execution against a fresh database.** Phase 0 named this "the single largest unquantified risk." They have only ever been designed against a Supabase instance whose schema was `alembic stamp`-ed rather than migrated (`12c7b2051fc6...py:8-15`) — so a genuine drift between the migrations and the live schema would surface here for the first time. | **H** / High | This is a *feature* of Slice 1, not a failure of it: discovering drift is the point. Slice 1 is deliberately first and independent, so failures are diagnosed before any Phase 1A code exists to be blamed. Budget explicit time for triage. **Do not "fix" a failing test by editing it** — a failure here is either a real schema drift or a real defect, and both are findings. | Technical |
| **R-2** | **`REVOKE` is ineffective** because the application connects as owner/superuser, so "append-only" is application discipline only. | **M** / High | Investigate in Slice 3 as a required deliverable. If confirmed, EV-AUD-03 states it plainly and AC-26's language check enforces honest wording. Recommend a least-privilege application role as the **first** Phase 1B story. | Technical + Security |
| **R-3** | **Audit writes in Slice 5 disturb the embedding/analysis transaction boundaries**, which are deliberate and documented (`document_chunk_embedding.py:69-210`; `rag_analysis.py:11-27`) — causing lost idempotency, a held transaction across the LLM call, or a deadlock. | **M** / High | Slice 5 is last and isolated. Re-read both services before editing. Place audit writes **only** at terminal state transitions. AU-4 and AU-12 pin both directions. Revert Slice 5 alone if it destabilises. | Technical |
| **R-4** | **pgvector version divergence** between `pgvector/pgvector:pg16` and Supabase's 0.8.2 masks or invents a behaviour difference. | M / Medium | Pin the image by digest; capture the actual version in EV-TEST-DB-03; state the divergence as a known limitation rather than discovering it later. | Technical |
| **R-5** | **The import-time engine (§3.3 C-3) is not respected**, so tests silently run against `.env`'s `DATABASE_URL` — i.e. shared Supabase — while appearing configured. | M / **Critical** | Three independent controls: env selection above the `app.main` import; the URL guard; and the in-database marker, which no shared database can satisfy. DB-6 proves the marker path. | Technical |
| **R-6** | **`CrossTenant*` substitution changes an observable status code or message**, breaking the 404/403 discipline or a frontend expectation. | L / High | Subclassing inherits `status_code` unchanged; message strings are not edited. RG-4 snapshots every error path before and after. Slice 4 lands alone. | Technical + Security |
| **R-7** | **Scope creep** — "while we're in there, let's wire permissions / add the hash chain / add RLS." | **H** / High | §21's out-of-scope list is frozen for the phase. AC-16 makes "zero endpoints guarded" a *tested* property, so wiring one silently fails CI. | Founder |
| **R-8** | **Phase 1A is reported as closing BLOCKER-1 or BLOCKER-2.** | M / **High** | §1.3 states plainly that it closes neither. AC-26 greps for forbidden claims before sign-off. Evidence titles say "foundation", never "complete". | Founder + Technical |
| **R-9** | **The correlation-id middleware breaks the CORS-on-error behaviour** deliberately engineered at `exceptions.py:62-72`. | L / Medium | Register inside `CORSMiddleware`; add a test asserting CORS headers survive a 500 with the middleware active. | Technical |
| **R-10** | **The audit table grows without bound** — no retention policy exists. | M / Medium | Not solved in Phase 1A. Indexes are designed for time-bounded queries. Retention is raised as decision **D-5**. Monitor row count in the evidence pack. | Founder |
| **R-11** | **Local Python 3.14 vs CI 3.12 drift** (Phase 0 S-8) masks a defect in new code. | L / Medium | Unresolved by Phase 1A; carried forward explicitly rather than assumed away. | Technical |
| **R-12** | **Work again exists only locally** — Phase 0 D-13 recorded 6 commits and ~500 uncommitted lines with no upstream. | **M** / High | Push-to-origin is a Definition-of-Done item for every slice, not an afterthought. Management decision **M-9**. | Technical + Founder |

---

## 19. Backward-Compatibility Considerations

| Surface | Compatibility | Basis |
|---|---|---|
| **HTTP status codes** | **Unchanged on every path.** `CrossTenantAccessDenied` inherits 404; `CrossTenantActionDenied` inherits 403 (`exceptions.py:26-27, 42-43`) | RG-4, AC-13 |
| **Error message text** | **Unchanged.** No message string is edited; `"User has no organization"` and all `f"X {id} not found"` forms are preserved verbatim | RG-4 |
| **Response bodies** | **Unchanged.** No schema in `app/schemas/` is modified; no field added or removed | §11.4 |
| **Response headers** | **One addition:** `X-Request-Id`. Additive; no client reads it today (`frontend/src/lib/api/client.ts:74-90`) | §5.4 |
| **Request contract** | **Unchanged.** No new required header, parameter or field on any endpoint | §11.4 |
| **Authorization behaviour** | **Unchanged.** Permission enforcement is wired to zero endpoints; every caller who can do something today can still do it | AC-16 |
| **Service signatures** | **Unchanged.** No existing method gains or loses a parameter | §5.5 |
| **`except NotFoundError` / `except AuthorizationError` blocks** | **Still catch.** Subclassing preserves every existing handler, e.g. `document_upload.py:131` | Python semantics + RG-1 |
| **Database schema** | **Purely additive.** One new table; no existing table altered; no data migrated | §10 |
| **Alembic chain** | Linear extension of `da0298a9c722`. `downgrade` is a clean `drop_table` | §10 |
| **Existing tests** | **Zero edits** to 593 tests; `backend/tests/conftest.py` gains fixtures and preserves `client` (`:8-12`) verbatim | AC-13, §13.2 |
| **Frontend** | **No change required.** 403 already handled (`errors.ts:26-31, 69`) | §12 |
| **`docker-compose.yml`** | **Untouched.** The test compose file is separate and never mounts `backend/.env` | §11.3 |
| **`.env` / `.env.local`** | **Never read or modified.** Only `.env.example` gains a commented line | §11.3 |
| **CI** | Existing jobs unchanged; one job added | §9.8 |

**The one accepted incompatibility.** A run that selects integration tests without `GH_TEST_DATABASE_URL` now **fails** where it previously **skipped**. This is intentional and is the point of C-2: a silent skip in a security gate is worse than a loud failure. It affects only deliberate `-m integration` invocations; the default `pytest -m "not integration"` path is unchanged.

---

## 20. Rollback Approach

### 20.1 Per-slice rollback

| Slice | Rollback | Data impact | Difficulty |
|---|---|---|---|
| 1 — Test environment | `git revert`; delete the compose file; drop the CI job | **None** — no application file touched, no production DB touched | Trivial |
| 2 — Context + correlation | `git revert`; remove the middleware registration | None — nothing consumed it | Trivial |
| 3 — Audit spine | `git revert` **plus** `alembic downgrade -1` (drops `audit_events`) | Audit rows lost. Zero business impact — nothing depends on them | Low |
| 4 — Denial auditing | `git revert` the slice. Exception classes revert to `NotFoundError`/`AuthorizationError`; behaviour returns exactly to today | Denial events stop; existing rows remain readable | Low |
| 5 — Success auditing | `git revert` the slice **only**; slices 1-4 remain | Success events stop | Low |
| 6 — Permission framework | `git revert` | **None** — nothing was enforced | Trivial |

### 20.2 Emergency runtime kill-switch (no deploy required)

`app/core/config.py` gains `audit_enabled: bool = True`. Setting `AUDIT_ENABLED=false` makes `AuditService` a no-op on both write paths. This exists for one scenario: audit writes are degrading production and a code rollback is not immediately available.

**Constraints on its use:** it must be logged at `WARNING` on startup when false; it must never be false in an evidence-producing run; and disabling it is itself a governance event that must be recorded outside the system (because, by definition, the system cannot record it). This limitation is stated deliberately rather than engineered around.

### 20.3 Full-phase rollback

Because every slice is additive and independently revertible, a full rollback is: revert slices 6→1 in reverse order, then `alembic downgrade` to `da0298a9c722`. The system returns to commit-`079efef` behaviour with **no data loss in any business table** — Phase 1A never writes to one.

### 20.4 What cannot be rolled back

- **Knowledge.** If Slice 1 reveals that the 142 integration tests fail against a fresh database, that finding stands regardless of any revert. It is a finding about the system, not about Phase 1A.
- **The database-role finding** (§8.2). Same.

Both are outcomes worth having even if every line of Phase 1A code were reverted — which is a further argument for Slice 1 going first.

---

## 21. Explicit Out-of-Scope Items

| Out of scope | Why | Where it belongs |
|---|---|---|
| Final business role matrix / role hierarchy | Management decision **M-4** | Phase 1B, after M-4 |
| Applying `require_permission` to any endpoint | Requires M-4 | Phase 1B (one line per endpoint) |
| Any policy assignment table or admin UI | Requires M-4 | Phase 1B+ |
| **Hash chaining / tamper evidence** | §8.6 — needs a serialised gap-free sequence, its own design and load test | Phase 1B, own acceptance test |
| External immutable audit export | Depends on M-2 / M-3 residency decisions | Phase 1C+ |
| Audit read API, audit viewer UI, admin console | Integrity before visibility (`Phase1_Recommended_Backlog.md:243`) | Phase 1C+ |
| RLS policies / `ENABLE ROW LEVEL SECURITY` | Large surface; needs Slice 1 first to be verifiable | Phase 1B |
| Approval workflow, evidence review states, reviewer, disposition | FND-KC-05 / FND-AI-03 | Sprint 2 |
| Malware scanning, `PENDING_SCAN` / `QUARANTINED` states | FND-SEC-02; independent of the foundation | Sprint 1 Epic C |
| Decision Register, Authority Matrix, CEO brief | FND-GOV-01/02/03 — must be built **on** the spine | Sprint 4+ |
| Master Portfolio, six-gate lifecycle, PMO registers | FND-PMO-01/02/03 | Sprint 4+ |
| Requirement/deliverable/RFI registers | FND-PRJ-01/02/03 | Sprint 7 |
| Agent registry, kill switch, evaluation set | FND-AI-01/02 | Sprint 5 |
| Checksums, duplicate detection, versioning, page numbers | FND-KC-02 / FND-KC-04 | Sprint 3 |
| Deterministic calculation engine | FND-MTH-01 | Sprint 7 |
| Backup and tested restore | FND-REL-01 | Sprint 6 |
| OneDrive integration, PMO, Founder Office, agents, file scanning, new UI pages | Explicitly excluded by the Phase 1A mandate; several blocked on M-1 | Later phases / management decisions |
| Migrating services from `User` to `RequestContext`; converging Pattern B onto Pattern A | Large refactor; must not share a phase with the audit introduction | Phase 1B slice 1 |
| Removing the 15 per-module `_require_database_url` skip fixtures | Editing them would invalidate the "unmodified tests pass" evidence | Phase 1B cleanup |
| Resolving the local 3.14 vs CI 3.12 drift | Independent of this phase | Sprint 1 Epic D |
| Dependency scanning (`pip-audit`, `npm audit`), coverage thresholds | Sprint 1 Epic D-2/D-3 | Sprint 1 |
| Correcting `backend/README.md`, `backend/CLAUDE.md`, `frontend/README.md` beyond the test-environment runbook | Phase 0 D-1/D-2/D-3 | Sprint 1 Definition of Done |
| Any real client, Aramco, confidential or regulated data | Forbidden until the §8 blockers close and M-2/M-3/M-8 resolve | — |
| Any external, funding or government material | Plan §13 — no measured result exists to support a claim | — |

---

## 22. Decisions That Still Require Management Approval

| # | Decision | Why engineering cannot decide it | Blocks | Urgency | Relation to Phase 0 |
|---|---|---|---|---|---|
| **D-1** | **The authoritative role model and which capability each role holds.** Phase 1A delivers the catalog and the resolver; the mapping is a business authority statement. | Defining who may do what is a Founder authority, not a technical choice | Wiring `require_permission`; FND-SEC-01 completion; every approval requirement | **Immediate** — Phase 1B cannot start | **= M-4**, still open. Phase 1A is deliberately structured so this does **not** block Phase 1A. |
| **D-2** | **What does a user with a NULL or unrecognised `users.role` receive?** `users.role` is nullable (`12c7b2051fc6...py:39`). Phase 1A's answer is "nothing, and nothing is enforced, so nothing breaks." Phase 1B must give a real answer. | An onboarding/provisioning policy decision | Phase 1B wiring; interacts with M-5 | High | New — surfaced by this plan |
| **D-3** | **Audit-write failure behaviour: fail-open with a logged error (recommended for Phase 1A) or fail-closed?** The Phase 1 backlog recommends fail-closed for admin-class actions; Phase 1A has none. | A risk-acceptance decision: lose an audit record, or fail a business operation | AC-20 wording; Slice 3 | High | Refines `Phase1_Recommended_Backlog.md:154` |
| **D-4** | **Accept Docker Compose + CI service containers as the resolution of M-11**, closing it as an engineering task rather than a budget item. | Accepting a lower-fidelity environment than a real Supabase project is a risk-acceptance call | Slice 1 sign-off | **Immediate** — but the recommendation is to accept, and it costs nothing | **Closes M-11** at zero cost |
| **D-5** | **Audit retention: how long are `audit_events` rows kept, and may any be deleted?** A retention rule that deletes rows is in tension with append-only. | Legal/regulatory, and it interacts with M-3 residency | Phase 1B integrity design; R-10 | Medium-High | New |
| **D-6** | **Confirm hash chaining as a Phase 1B story with its own acceptance test**, and accept that Phase 1A's trail is append-only but **not** tamper-evident. | Accepting an interim state of the FND-SEC-03 acceptance test | FND-SEC-03 completion | **Immediate** — it governs what may be claimed about Phase 1A | Refines the Phase 0 BLOCKER-1 remediation |
| **D-7** | **May a cross-tenant denial event record the foreign object's id?** Phase 1A records the *requested* id and the *caller's own* organization, never the foreign organization's id. | A data-minimisation vs forensic-completeness trade-off | §8.5; EV-AUD-02 | Medium | New |
| **D-8** | **Confirm that Phase 1A closes no Phase 0 blocker**, and that no external, funding or gate material may cite it as doing so. | A reporting-integrity decision | All Phase 1A reporting | **Immediate** | Enforces Phase 0 §12 |
| **D-9** | **Locate and place the controlling requirements PDF** (`GH_Founder_PMO_Knowledge_AI_Foundation_Requirements_Proof_Plan_V1_0_2026-07-29.pdf`) under version control. It is not in this repository, so every Plan reference here is second-hand via the Phase 0 artefacts. | A controlled-document custody question | Traceability of every requirement claim | **Immediate** — low effort | New — surfaced by this plan |
| **D-10** | **Approve adding `pytest-cov`** to `requirements-dev.txt`, or defer coverage measurement to Sprint 1 Epic D-2. | Dependency additions are controlled | Coverage evidence | Low | Refines Phase 0 D-16 |

**Still open from Phase 0 and unaffected by this plan:** M-1 (OneDrive), M-2 (AI provider / DPA), M-3 (data residency), M-5 (provisioning), M-6 (malware scanner), M-7 (multi-organization), M-8 (proof-case data boundary), M-9 (push local commits / IP position), M-10 (completion baseline), M-12 (page-level citation).

---

## Statement of Non-Modification

In producing this document:

- **No application source file was created, modified or deleted.** Only files under `backend/app/`, `backend/tests/`, `backend/migrations/`, `frontend/src/`, `.github/`, `docker-compose.yml`, `backend/pytest.ini`, `backend/alembic.ini`, `backend/requirements*.txt` and `backend/.env.example` were **read**.
- **No migration was created, modified or executed.** No Alembic command was run.
- **No `.env` or `.env.local` file was read, printed or modified.** `backend/.env.example` was read; `backend/.env` was **not** opened.
- **No secret, token, key or credential value was read, printed or inferred.**
- **No database was contacted** — not shared Supabase, not any local instance. No connection was opened.
- **No container was started.** `docker`, `docker compose` and `psql` were not invoked.
- **No external service was called.** No OpenAI, OpenRouter, Supabase, JWKS or any other network request was made. No paid API was used.
- **No test was executed.** No `pytest`, `ruff`, `mypy`, `npm` or `alembic` command was run.
- **No dependency was installed, upgraded or removed.**
- **No git write operation was performed** — no commit, branch, tag, stash, checkout or push.
- **No real client, Saudi Aramco, or personal data was accessed or used.**
- **Exactly one file was created:** `project-governance/05-delivery/Phase1A_Foundation_Implementation_Plan.md` (this document).

*Prepared 2026-08-02 against the working tree at commit `079efef` plus its uncommitted changes. Line references are valid for that state only. This is a planning document; Phase 1A is not implemented.*
