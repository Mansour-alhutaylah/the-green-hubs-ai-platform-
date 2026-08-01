# SIP™ Phase 0 — Evidence-Based Repository Baseline and P0 Gap Audit

| Field | Value |
|---|---|
| Document ID | GH-SIP-PH0-BASELINE-001 |
| Classification | Confidential — Internal Use |
| Audit date | 2026-08-01 |
| Controlling baseline | `GH_Founder_PMO_Knowledge_AI_Foundation_Requirements_Proof_Plan_V1_0_2026-07-29.pdf` (V1.0, 29 July 2026) |
| Repository | `the-green-hubs-ai-platform-` |
| Branch / commit audited | `feature/frontend-live-integration` @ `079efefda0093c84c04cf578ca57f76b52d47c89` |
| Type | Read-only audit and planning. No application code, migration, schema, secret or database was modified. |
| Companion documents | `Command_Test_Log.md`, `../03-current-system/Current_System_Map.mmd`, `../04-p0-assessment/FND_P0_Gap_Matrix.csv`, `../05-delivery/Phase1_Recommended_Backlog.md` |

**Evidence convention used throughout.** *Observation* = read directly from a repository file or produced by a command executed in this audit; a file path and, where useful, a line range is given. *Inference* = a conclusion drawn from observations; labelled as such. *Unverified* = insufficient evidence; stated as Unverified rather than assumed either way. No screenshot, historical report, prior plan, or commit message is treated as proof of behaviour.

---

## 1. Executive Verdict

### What the system genuinely is today

The repository contains **a competently engineered, tenant-scoped document-intelligence vertical slice** — upload a PDF, extract and chunk it, embed the chunks in pgvector, retrieve semantically, run a citation-grounded LLM analysis, and read the result back in a bilingual React interface. That slice is real, wired end-to-end, and covered by 593 automated tests that all pass. The code quality is materially above what the 29 July 2026 audit's 36/100 characterisation would suggest: clean architecture is genuinely observed (domain / services / infrastructure separation with no FastAPI import in `domain/` or `services/`), authentication is implemented to a high standard, and the anti-fabrication controls in the RAG layer are unusually thoughtful.

**It is not, however, the Foundation described in the approved plan.** Of the 23 P0 requirements in the Foundation Plan, **zero are Implemented and Verified**. The system is a *Knowledge Center pipeline prototype*. The Founder Office, the Enterprise PMO, the Project Workspace, the AIOS agent governance layer and the SIP™ Control Tower — five of the six components in Plan §1 — have **no implementation at all**, not partial implementations. The Aramco proof case has nowhere to live.

Three structural absences define the gap, and all three are governance primitives rather than features:

1. **There is no audit trail.** Not a weak one — none. No table, no actor capture, no previous-state capture. (`backend/migrations/versions/` — no migration creates one.)
2. **There is no server-side authorization beyond the organization boundary.** The five-tier role model exists only in the browser. (`frontend/src/features/rbac/roles.ts` vs. zero uses of `current_user.role` in `backend/app`.)
3. **There is no human approval step.** No evidence review states, no reviewer, no disposition — so the Plan's Non-Negotiable Principle 2 ("No AI-generated statement becomes official without an evidence citation *and human approval*") is currently unenforceable, because nothing can be approved.

### What is working (evidence-backed)

- Supabase JWT verification: ES256-only allow-list, JWKS with `kid` selection, issuer/audience/expiry enforcement, uniform error messages. Tested, including algorithm-confusion cases.
- Organization-level tenant isolation across **every** sensitive endpoint, with the tenant identifier never accepted from the client and always re-derived from `current_user`. Covered by cross-tenant negative tests at unit level.
- The document pipeline: bounded upload with magic-byte validation → Supabase Storage → PDF extraction → conservative normalization → chunking with character offsets → idempotent embedding generation → pgvector cosine retrieval.
- RAG with server-controlled citation mapping: the model never sees a real database UUID, and a response citing a source outside the assembled context is rejected and the run marked FAILED.
- A production-quality CI gate: ruff + mypy (105 files clean) + 442 backend tests, and oxlint + tsc + 151 frontend tests + build, on every push and PR.

### What is not proven

- **The 144 backend integration tests were not executed in this audit** and their current pass state is Unverified — they require a live `DATABASE_URL`, which on this machine resolves to the shared Supabase instance. They are also excluded from the CI gate, so database-layer tenant isolation is not continuously verified anywhere.
- No feature has ever been measured against the Foundation Plan's own acceptance tests. No extraction benchmark, no citation-precision measurement, no AI evaluation set, no golden journey, no restore test, no KPI baseline.
- Managed backup of the Supabase instance may exist but is **Unverified** — there is no repository evidence and no restore has been demonstrated.

### Is it safe for internal synthetic / sanitized testing?

**Yes, with two conditions.** The authentication and tenant-isolation controls are strong enough for internal use with synthetic or sanitized data. Conditions: (a) every user in the test organization must be treated as holding full permissions, because the server does not enforce roles; (b) document content is transmitted to an external AI provider (OpenAI or OpenRouter) on every embedding and analysis call, so only content cleared for that transmission may be used.

### Is it ready for real project / client data?

**No. Categorically not.** Real Aramco or client data must not be loaded. Four independent blockers, any one of which is sufficient:

1. No audit trail — the Plan's traceability principle cannot be met, and a data-handling incident could not be reconstructed.
2. No server-side role enforcement — every organization member has effective Owner-level API access.
3. No malware scanning or quarantine — a structurally valid but malicious PDF enters the evidence pipeline unchecked.
4. No demonstrated restore — data-loss exposure is unquantified.

A fifth, non-engineering blocker: the approved principle that **OneDrive stores controlled originals** is not implemented; originals live in Supabase Storage, whose data residency is Unverified in this repository. That is a Founder/Legal decision, not a defect an engineer may resolve.

### Evidence-based completion range

Derived from the requirement-level matrix in §7, never from impression. Two separate figures, because conflating them is exactly how a 36/100 system gets described as 60% done:

| Measure | Range | Meaning |
|---|---|---|
| **Technical implementation completion** | **20 – 28 %** | Code exists that performs some of the work, scored across the Plan §2 architecture layers. |
| **Verification / acceptance readiness** | **9 – 14 %** | Requirements that pass, or partially pass, the Plan's own documented acceptance test. |
| **Requirements fully accepted** | **0 %** | 0 of 23 P0 requirements are Implemented and Verified. |

Full method, inputs and sensitivity are in §7.3. **The historical 30 % / 36 % figures were not reused and did not inform these numbers.**

### Recommended next gate decision

## → **NO-GO** for G2 (Build) sign-off, and **NO-GO** for loading any real project or client data.
## → **CONDITIONAL GO** to continue engineering, on the milestone-released Sprint 1 defined in §10.

Mapping to the Plan's own §12 No-Go triggers, three fire simultaneously:

| §12 Category | Threshold | Actual | Trigger |
|---|---|---|---|
| Security | 0 critical access failures; file controls pass | No server-side roles; no quarantine | **Unauthorized access class exists; unsafe file accepted** |
| Evidence | 100 % accepted requirements cited; 0 unsupported approved claims | No requirement register; no approval concept | **Official output cannot be traced** |
| Reliability | Backup and restore successful | Neither evidenced | **Restore not demonstrated** |

This is a NO-GO on the *Foundation gate*, not a judgement on the engineering. The build quality is good; it has been pointed at the document-intelligence slice rather than at the governance spine the Foundation is actually defined by.

---

## 2. Git and Environment Baseline

| Item | Value |
|---|---|
| Repository name | `the-green-hubs-ai-platform-` |
| Remote owner | GitHub — `<owner redacted>` (remote URL contains no embedded credentials) |
| Remote | `origin  https://github.com/<owner-redacted>/the-green-hubs-ai-platform-.git` (fetch + push) |
| Current branch | `feature/frontend-live-integration` |
| Current commit | `079efefda0093c84c04cf578ca57f76b52d47c89` |
| Relationship to `main` | 6 commits ahead. `main` = `670bb24` = `origin/main`. `git diff --stat main...HEAD`: 60 files, +6,306 / −188, entirely under `frontend/`. |
| **Push status** | **The audited branch has NO upstream.** `git branch -vv` shows no `[origin/...]` for it. All 6 commits exist only on this workstation. |
| Working tree | **Dirty** — 12 modified tracked files, 2 untracked paths of source/test code, 1 stray untracked `node_modules/`. Reported, not altered. |
| Local branches | 16 (13 tracked to origin, 3 not) |

### Tool versions (recorded, not changed)

| Tool | Version | Note |
|---|---|---|
| Python | 3.14.3 | CI targets **3.12** (`.github/workflows/ci.yml:17`) — a two-minor-version drift between local and CI. |
| Node | v24.13.1 | CI targets 24. Aligned. |
| npm | 11.8.0 | |
| Git | 2.53.0.windows.1 | |

### Uncommitted work in flight

`git diff --stat`: 12 files, +491 / −21. Content: OpenRouter credential resolution (`backend/app/core/config.py`, `resolve_ai_credentials`), an embedding-scope fix in the document read model, and their tests. Untracked: `backend/tests/core/test_config.py`, `backend/tests/infrastructure/repositories/test_document_read_model_embedding_scope.py`.

**Finding (governance, High).** Six commits of frontend live-integration work plus roughly 500 lines of uncommitted backend work exist **only on one local machine**. Nothing is pushed. Combined with the Plan's own risk *"Vendor dependency / IP leakage — repository control, code handover"* (§13), this is a single-point-of-failure for the project's entire recent output. It is also a governance inconsistency: work that is not in the remote history cannot be evidenced, reviewed, or handed over.

### Untracked `node_modules/` at repository root

`node_modules/` exists at the repository root containing only a `.vite` cache directory, and the root `.gitignore` contains exactly one line (`project-config/scheduled_tasks.lock`) — so root-level `node_modules` is **not ignored** and shows as untracked. There is no root `package.json`. *Inference: a stray artefact from running a Vite command from the repository root.* Low severity; noted because it pollutes `git status` and could be accidentally committed.

---

## 3. Verified Current Capabilities

Only capabilities supported by **both** code and executed, passing tests appear here.

### 3.1 Authentication — Supabase JWT verification

**Implementation:** `backend/app/infrastructure/security/supabase_jwt.py:49-157`, wired at `backend/app/api/deps.py:121-137`.

Verified properties, each with a specific mechanism:
- Algorithm allow-list is `["ES256"]` as a **module constant, not a `Settings` field** (`supabase_jwt.py:49`) — it cannot be weakened by environment misconfiguration. The token's own `alg` header is never trusted to select the verification method.
- Public keys are fetched from the project's JWKS endpoint and selected by `kid` (`supabase_jwt.py:122-131`). No shared secret is used for verification; no private key material is stored.
- Issuer and JWKS URI are **derived** from `settings.supabase_url` (`supabase_jwt.py:149-157`), not hardcoded.
- `exp`, `iat`, `sub`, `aud`, `iss` are all required (`supabase_jwt.py:50`, passed as `options={"require": ...}`).
- Forced JWKS refresh is throttled to once per 5 minutes (`JWKSCache._maybe_refresh`, `supabase_jwt.py:98-112`) — prevents a burst of forged `kid` values from hammering the JWKS endpoint.
- Every failure path collapses to one generic message (`_GENERIC_ERROR`) — expired, bad-signature and wrong-audience are indistinguishable to a caller.

**Tests:** `backend/tests/infrastructure/security/test_supabase_jwt.py`, `backend/tests/api/test_auth.py` — executed, passing.

### 3.2 Organization-level tenant isolation

**The single strongest control in the repository.** `organization_id` is never accepted from the client in any form — not query, not header, not body — on any tenant-scoped endpoint. It is always re-derived from `current_user` inside the service layer.

| Service | Enforcement | File |
|---|---|---|
| `OrganizationService` | Own-organization only; mismatched id raises `NotFoundError`, not `AuthorizationError`, so a cross-tenant probe is indistinguishable from a nonexistent id | `backend/app/services/organization.py:36-75` |
| `EngagementService` | Re-derives org from `current_user`; client-supplied `organization_id` in body/query is not trusted as authority | `backend/app/services/engagement.py` |
| `DocumentUploadService` | Loads engagement, then compares `current_user.organization_id` to `engagement.organization_id` | `backend/app/services/document_upload.py:98-103` |
| `DocumentProcessingService` | Same check before claiming the document | `backend/app/services/document_processing.py:137-142` |
| `DocumentReadService` | Tenant-scoped list and detail | `backend/app/services/document_read.py` |
| `VectorRetrievalService` | Org scope from `current_user` only | `backend/app/services/vector_retrieval.py` |
| `RagAnalysisService` | Org derived from `current_user`; foreign document/engagement returns 404 | `backend/app/services/analysis/rag_analysis.py:169-218` |

Enforced again at the SQL layer for retrieval: `WHERE dce.organization_id = :organization_id` (`backend/app/infrastructure/repositories/document_chunk_embedding.py:232`). Embedding rows derive their tenant lineage **from the database via `INSERT ... SELECT ... JOIN`** on the chunk's real ownership chain rather than from application-supplied values (`document_chunk_embedding.py:82-96`) — a genuinely good design choice.

**Tests (executed, passing):** `test_organization_service.py`, `test_engagement_service.py`, `test_document_read_service.py`, `test_vector_retrieval_service.py`, `test_rag_analysis_service.py`, `tests/api/test_documents_read.py`, `tests/api/test_engagements.py` — all contain explicit cross-tenant negative cases.

**Caveat — do not overstate.** 144 integration tests that would prove this at the real database layer were **not executed** and are **excluded from CI**. Isolation is verified at the service/API layer with fakes; at the database layer it is Unverified.

### 3.3 Document upload validation

`backend/app/api/v1/documents.py:60-76` + `backend/app/services/document_upload.py:61-147`. Layered: bounded streaming read that aborts the instant the limit is exceeded (never buffers more than the max plus one 64 KB chunk) and closes the file in `finally`; control-character stripping and a 255-char cap on the filename; `.pdf` extension; `application/pdf` declared content type; `%PDF-` magic bytes; non-empty; and a second size check inside the service. Object key is server-generated (`organizations/{org}/engagements/{eng}/documents/{uuid}.pdf`) — the client never influences the storage path.

Compensation is correct: if the DB insert fails after the storage write succeeded, the exact object just written is deleted; if that delete fails it is logged with the orphaned key and swallowed so the original error still surfaces (`document_upload.py:131-153`).

**Tests:** `backend/tests/services/test_document_upload_service.py`, `backend/tests/api/test_documents.py` — executed, passing.

### 3.4 Extraction, normalization and chunking

- `backend/app/infrastructure/documents/text_extractor.py` — strategy registry for `pdf` (PyMuPDF), `docx`, `xlsx`/`xls`, `txt`; blocking parse work runs via `asyncio.to_thread`; failures raise typed exceptions rather than sentinel strings.
- `backend/app/infrastructure/documents/normalizer.py` — deliberately conservative: line-ending unification, control-character removal, trailing-whitespace trim, blank-run collapse. **Numbers, units, currency, dates and table rows are never touched, and no AI is used.** Correct for an evidence system.
- `backend/app/infrastructure/documents/chunker.py` — preserves `char_start` / `char_end` per chunk, which is what makes passage-level citation possible.

**Tests:** `tests/infrastructure/documents/test_text_extractor.py`, `test_normalizer.py`, `test_chunker.py` — executed, passing.

### 3.5 Embedding generation and pgvector retrieval

Idempotent by construction: `claim_new` uses `ON CONFLICT (chunk_id, provider, model, model_version) DO NOTHING ... RETURNING` so concurrent requests cannot double-embed; `retry_failed` and `reclaim_stale` are guarded state transitions; every write commits immediately because these are concurrency facts other requests must observe (`backend/app/infrastructure/repositories/document_chunk_embedding.py:69-210`). `embedding_dimension` is pinned to 1536 and the provider refuses to construct with any other value, matching the fixed `vector(1536)` column.

**Tests:** `tests/services/test_embedding_generation_service.py`, `tests/infrastructure/ai/test_openai_embedding_provider.py` (all HTTP intercepted via `httpx.MockTransport`) — executed, passing.

### 3.6 RAG analysis with grounded citations

The anti-fabrication design is the best-engineered part of the repository:

- The model is shown **only opaque `SOURCE_n` keys**, never a real chunk or document UUID (`backend/app/services/analysis/prompts.py:45-51`).
- The response is validated for **shape** by Pydantic (`structured_output.py`) and for **membership** by the service — `structured.all_source_keys() <= source_map.keys()` (`rag_analysis.py:342`).
- A response citing a key outside the assembled context marks the run **FAILED** with "Analysis provider cited sources outside the assembled context" (`rag_analysis.py:362-368`).
- Server-side remapping converts `source_keys` to real citation IDs **after** persistence (`rag_analysis.py:69-96`) — the model never influences citation identity.
- An explicit insufficient-evidence path exists and is honoured both from the model's own `evidence_status` and from an empty relevant-result set (`rag_analysis.py:323-327, 370-376`).
- Idempotency by request hash over all 15 parameters that affect the result, with claim/retry/stale-reclaim, and **no database transaction is ever held open across the external LLM call** (`rag_analysis.py:11-27, 240-298`).
- Provider errors are mapped to a fixed safe-message table so provider internals never reach the client (`rag_analysis.py:56-66`).

**Tests:** `tests/services/test_rag_analysis_service.py`, `test_structured_output.py`, `test_request_hash.py`, `tests/api/test_analysis.py`, `tests/infrastructure/ai/test_openai_llm_gateway.py` — executed, passing.

### 3.7 Frontend live vertical slice

Live and covered by executed tests: login via Supabase Auth (`liveAuthService.ts`), workspace resolution (`WorkspaceProvider.tsx`), documents list / detail / upload with processing and embedding polling, and the analysis run page rendering structured output and citations. The API client (`frontend/src/lib/api/client.ts`) is the single network seam — no page issues a direct `fetch` — reads the access token fresh from the Supabase SDK on every call, never logs it, and emits a session-expired event on 401.

Bilingual: full `en`/`ar` catalogues, `document.documentElement.dir` set to `rtl` for Arabic (`LocaleContext.tsx:11,26`).

**Tests:** 151 frontend tests across 27 files — executed, passing.

### 3.8 Engineering hygiene

`ruff` clean, `mypy` clean across 105 files, `oxlint` clean, `tsc -b` clean, production build succeeds. CI gates all of it on every push and PR (`.github/workflows/ci.yml`).

---

## 4. Unverified or Partial Capabilities

**Separating "code exists" from "proven to operate" is the entire point of this section.**

| Capability | Code exists | Proven | Precise status |
|---|---|---|---|
| Database-layer tenant isolation | Yes | **No** | 144 integration tests exist but were not executed here and are excluded from the CI gate (`ci.yml:25` runs `pytest -m "not integration"`). **Unverified at the DB layer.** |
| DOCX / XLSX ingestion | Yes (`text_extractor.py:106-112`) | **No** | Unreachable end-to-end: `_validate_pdf` rejects everything but PDF (`document_upload.py:135-147`). Extractor unit tests pass; the pipeline path does not exist. |
| CSV ingestion | **No** | No | Not registered in `_STRATEGIES`. Required by FND-KC-03. |
| Arabic extraction | Partially (PyMuPDF handles embedded Arabic text) | **No** | No Arabic-specific test in the suite; no benchmark defined or run. **Unverified.** |
| OCR (Arabic or English) | **No** | No | No OCR dependency in `requirements.txt`. Scanned documents cannot be ingested at all. |
| Page-level citation | **No** | No | `text_extractor.py:69` joins pages with `"\n"` — page identity is destroyed before chunking. `document_chunks` has no page column and none can be derived. |
| `overall_confidence` | Yes (field persisted) | **No** | Self-reported by the LLM, uncalibrated, never validated against outcomes. It is a model opinion, not a measurement. |
| Extracted metrics | Yes (`MetricValue`) | **No** | `value` is typed `str | None` and is **transcribed by the model, never calculated**. Nothing is recomputed or reconciled. |
| Supabase managed backup | Outside repository | **No** | No repository evidence; no restore ever demonstrated. **Unverified.** |
| Alembic migration state on the shared DB | 8 migrations tracked | **No** | Not queried (would require connecting to shared infrastructure). **Unverified.** |
| Role-based access | Frontend only | **No** | `RoleGuard` is UX; the server never reads `role`. Not a partial control — **absent** on the server. |
| Dashboard figures | Yes (renders) | **No** | 100 % mock data (`mockDashboardData.ts`). No API call. |
| Analysis history list | Partially | n/a | No backend list endpoint exists; the live branch honestly renders a limited-state page instead of mixing mock rows into a live session (`AnalysisListPage.tsx:52-78`). **Good practice, correctly noted as a gap.** |

---

## 5. Current Architecture

The verified system map is at `../03-current-system/Current_System_Map.mmd` (Mermaid, colour-coded LIVE / DEMO / MISSING / EXTERNAL / data).

### 5.1 Verified request flow, step by step

| # | Step | Exact artefact | Authorization | Tests | State |
|---|---|---|---|---|---|
| 1 | User signs in | `frontend/src/features/auth/services/liveAuthService.ts:64-89` → Supabase Auth | Supabase password grant | `liveAuthService.test.ts` | **LIVE** |
| 2 | Session resolved to profile | `liveAuthService.ts:30-61` → `GET /api/v1/auth/me` | Bearer ES256 token | `AuthContextLive.test.tsx` | **LIVE** |
| 3 | Token attached to every call | `frontend/src/lib/api/client.ts:40-65` | Fresh token from Supabase SDK per request | `client.test.ts` | **LIVE** |
| 4 | Token verified | `backend/app/infrastructure/security/supabase_jwt.py:122-146` | ES256 / JWKS / iss / aud / exp | `test_supabase_jwt.py` | **LIVE** |
| 5 | Identity → profile | `backend/app/api/deps.py:130-137` | `ProfileNotProvisionedError` → 403 if no `public.users` row | `test_auth.py` | **LIVE** |
| 6 | Workspace resolved | `WorkspaceProvider.tsx:58-76` → `GET /api/v1/organizations` | Own org only (`organization.py:40-47`) | `WorkspaceProvider.test.tsx` | **LIVE** |
| 7 | Upload PDF | `POST /api/v1/documents` → `documents.py:133-148` → `DocumentUploadService` | Org must match engagement's org | `test_document_upload_service.py` | **LIVE** |
| 8 | Store original | `SupabaseDocumentStorage` → Supabase Storage bucket | **Service-role key — bypasses RLS** (`supabase_document_storage.py:21-23`) | `test_supabase_document_storage.py` | **LIVE — trust boundary** |
| 9 | Process | `POST /{id}/process` → `DocumentProcessingService.process` | Org match, then atomic `begin_processing` claim | `test_document_processing_service.py` | **LIVE** |
| 10 | Extract → normalize → chunk | `text_extractor.py` → `normalizer.py` → `chunker.py`; rows in `extracted_text`, `document_chunks` | n/a (internal) | 3 test modules | **LIVE (PDF only)** |
| 11 | Embed | `POST /{id}/embeddings` → `EmbeddingGenerationService` → `OpenAIEmbeddingProvider` | Org match; tenant lineage derived in SQL | `test_embedding_generation_service.py` | **LIVE — trust boundary** |
| 12 | Retrieve | `POST /api/v1/retrieval/search` → `VectorRetrievalService` | `WHERE dce.organization_id = :organization_id` | `test_vector_retrieval_service.py` | **LIVE** |
| 13 | Analyse | `POST /analysis/documents/{id}/analyze` → `RagAnalysisService` → `OpenAILLMGateway` | Org derived from `current_user`; foreign id → 404 | `test_rag_analysis_service.py` | **LIVE — trust boundary** |
| 14 | Persist citations | `analysis_source_references` via `add_citations` | Server-controlled `SOURCE_n` → citation-id mapping | `test_analysis.py` | **LIVE** |
| 15 | Render result | `AnalysisRunPage.tsx` + `useAnalysisRunPoll.ts` | Frontend guards only | `AnalysisRunPageLive.test.tsx` | **LIVE** |
| — | **Human verification** | — | — | — | **MISSING — the flow ends without one** |

### 5.2 Trust boundaries and where sensitive data leaves the system

| # | Boundary | What crosses | Credential | Control | Residual risk |
|---|---|---|---|---|---|
| TB-1 | Browser → FastAPI | Access token, document bytes, queries | Supabase ES256 access token | CORS explicit allow-list (never `*`, `main.py:37-43`); Bearer verification | Roles not enforced server-side |
| TB-2 | Browser → Supabase Auth | Email + password | Public anon key | Supabase-managed | Anon key is correctly public-only; `.env.example` warns against service-role in the browser |
| TB-3 | FastAPI → Supabase Storage | **Full document originals** | **Service-role key — elevated, bypasses RLS** | Server-generated object keys; no client-controlled paths | A backend flaw exposes the whole bucket; residency Unverified |
| TB-4 | **FastAPI → OpenAI / OpenRouter** | **Full chunk text of every document, on every embed and every analysis** | `OPENAI_API_KEY` or `OPENROUTER_API_KEY` | Keys read only into `Authorization` headers, never logged | **This is where confidential project content leaves Saudi/organizational control. No DPA, retention position, or residency statement exists in the repository.** |
| TB-5 | FastAPI → Postgres | All data | `DATABASE_URL` | NullPool + PgBouncer-safe asyncpg config | Connects with a role that **bypasses RLS**; no RLS policies exist anyway |
| TB-6 | FastAPI → Supabase JWKS | Public keys only | none | 5-minute refresh throttle | Low |

**TB-4 is the most consequential finding for the Aramco proof case.** Every ingested document is transmitted in full to a third-party AI provider. `resolve_ai_credentials` (`backend/app/core/config.py:131-148`) transparently falls back from OpenAI to OpenRouter, and OpenRouter is itself a broker that routes to further upstream providers. Which provider ultimately processes a given request is, by design, configuration-dependent — and there is nothing in the repository recording an approved provider, a data-processing agreement, or a retention position.

### 5.3 Database schema — 9 live tables + 1 orphan

All under Alembic, linear chain: `eeb31636c877` → `12c7b2051fc6` → `693e23cf7797` → `73688728b480` → `81a7fdde2d19` → `233e7656bf79` → `3f3acc7fc556` → `da0298a9c722`.

| Table | Tenant field | Key controls | Notes |
|---|---|---|---|
| `organizations` | is the tenant | PK | |
| `users` | `organization_id` FK | unique `email` | **`role` column present but never enforced server-side** |
| `engagements` | `organization_id` FK | status default | No portfolio/stage/health/gate |
| `documents` | via `engagement_id` FK | unique `storage_path`; indexed `engagement_id` | **No checksum, no version, no evidence status, no page count** |
| `extracted_text` | via `document_id` | | |
| `document_chunks` | via `document_id` | unique `(document_id, chunk_index)`; `char_start`/`char_end` | **No `page_number`** |
| `document_chunk_embeddings` | **denormalized `organization_id`** | unique `(chunk_id, provider, model, model_version)`; 5 CHECK constraints; 5 indexes; `vector(1536)` | Tenant lineage derived in SQL, not supplied |
| `analysis_runs` | **`organization_id` NOT NULL** | unique on `request_hash` scope; CHECKs on status/attempt_count | Records provider, model, prompt + schema version, temperature, top-k, tokens |
| `analysis_source_references` | **`organization_id` NOT NULL** | unique `(analysis_run_id, citation_order)`; CHECK on offsets | Passage-level citation with `quoted_snippet` |
| `ai_analysis_results` | via `document_id` | — | **ORPHANED.** Model exists (`ai_analysis_result.py`) and is exported, but **no service, repository or endpoint uses it.** Superseded by `analysis_runs`. |

**Verified absent from the schema** (Observation — searched every migration): no audit table; no approval table; no evidence-review table; no agent registry; no agent-run reviewer/disposition; no document version or supersession chain; no file checksum; no page numbers; no retention or backup metadata; no PMO/project/portfolio register of any kind; **no `CREATE POLICY` and no `ENABLE ROW LEVEL SECURITY` in any migration.**

---

## 6. Test and Build Results

Full command-by-command record with working directories, safety pre-checks and exclusions: `Command_Test_Log.md`.

| Suite | Command | Passed | Failed | Skipped | Deselected | Result |
|---|---|---|---|---|---|---|
| Backend unit + API | `pytest -m "not integration" --deselect tests/test_health.py::test_health_db_reports_a_status -q` | **442** | **0** | 0 | 145 | PASS (14.76s) |
| Backend lint | `ruff check app tests` | — | 0 | — | — | PASS |
| Backend types | `mypy app` | — | 0 | — | — | PASS — 105 files |
| Frontend lint | `npm run lint` (oxlint) | — | 0 | — | — | PASS |
| Frontend types | `npm run typecheck` (`tsc -b --noEmit`) | — | 0 | — | — | PASS |
| Frontend tests | `npm test` (vitest) | **151** (27 files) | **0** | 0 | — | PASS (51.82s) |
| Frontend build | `npm run build` | — | 0 | — | — | PASS — 2,091 modules |

**Total: 593 tests executed, 593 passed, 0 failed, 0 skipped. No failures to attribute to product code, environment, test data, dependencies or external services.**

### Deliberately not executed — 145 backend tests

| Not run | Count | Reason |
|---|---|---|
| `pytest -m integration` | 144 | Requires a live `DATABASE_URL`, which on this machine resolves to the **shared Supabase instance**. These tests `INSERT` and `DELETE` real rows across eight tables. Writing to shared infrastructure is prohibited by the audit mandate. **Their pass state is Unverified.** |
| `tests/test_health.py::test_health_db_reports_a_status` | 1 | Resolves the real `get_db` dependency and executes `SELECT 1` against the shared instance. Read-only, but still shared-infrastructure contact — deselected conservatively. |

Also not run and why: any Alembic command (would connect to / could migrate the shared DB); `docker compose up` (mounts `backend/.env`, i.e. real credentials); any live OpenAI/OpenRouter call (paid); `npm install` / `pip install` (dependency changes prohibited); `npm audit` / `pip-audit` (registry contact / installation required); any E2E run (**no E2E harness exists in the repository**).

---

## 7. FND P0 Gap Matrix

Full matrix with sixteen columns per requirement — approved text, acceptance test, status, implementation, exact source files, tests, evidence, gap, risk, next action, owner, order, dependencies — is at `../04-p0-assessment/FND_P0_Gap_Matrix.csv`.

### 7.1 Status counts — all 23 P0 requirements

| Status | Count | Requirement IDs |
|---|---|---|
| **1. Implemented and Verified** | **0** | — |
| 2. Implemented but Unverified | 0 | — |
| 3. Partial | **8** | FND-KC-02, FND-KC-03, FND-KC-04, FND-AI-02, FND-AI-03, FND-SEC-01, FND-SEC-02, FND-TST-01 |
| 4. Missing | **14** | FND-GOV-01/02/03, FND-PMO-01/02/03, FND-KC-05, FND-AI-01, FND-PRJ-01/02/03, FND-MTH-01, FND-SEC-03, FND-REL-01 |
| 5. Contradicted or Unsafe | **1** | FND-KC-01 (OneDrive-as-source-of-record principle not implemented; originals in Supabase Storage with Unverified residency) |
| 6. Blocked by Decision / External Dependency | 0 | — |

P1: FND-UX-01 **Partial**; FND-FND-01 **Missing**.

### 7.2 By area

| Area | P0 count | Partial | Missing | Contradicted | Verified |
|---|---|---|---|---|---|
| Founder Office (GOV) | 3 | 0 | 3 | 0 | **0** |
| PMO | 3 | 0 | 3 | 0 | **0** |
| Knowledge Center (KC) | 5 | 3 | 1 | 1 | **0** |
| AIOS (AI) | 3 | 2 | 1 | 0 | **0** |
| Project (PRJ) | 3 | 0 | 3 | 0 | **0** |
| Methods (MTH) | 1 | 0 | 1 | 0 | **0** |
| Security (SEC) | 3 | 2 | 1 | 0 | **0** |
| Reliability (REL) | 1 | 0 | 1 | 0 | **0** |
| Testing (TST) | 1 | 1 | 0 | 0 | **0** |

**Every implementation effort to date has landed in exactly three of the nine areas.** Six areas — Founder Office, PMO, Project, Methods, Reliability, and the governance half of Security — are at zero.

### 7.3 Completion calculation — exact method

Four distinct things are measured separately, because collapsing them is how a demonstrator gets reported as a platform.

**Layer A — Code exists.** 385 tracked files; 9 live database tables; 14 API endpoints; 8 application services; 27 frontend test files. Not a percentage — a fact.

**Layer B — Code is tested.** 593 automated tests executed and passing; ruff/mypy/oxlint/tsc all clean. **But 144 integration tests are outside both this audit and the CI gate**, and there are zero agent-evaluation, calculation, or golden-journey tests.

**Layer C — Feature passes its official acceptance test.** **0 of 23.** No acceptance test from the Foundation Plan has been executed against this system.

**Layer D — Feature approved for internal use.** **0 of 23.** No approval mechanism exists in the system, so nothing can be approved *by* it either.

#### Technical implementation completion — 20 % to 28 %

Scored across the seven architecture layers the Plan itself defines in §2, each weighted equally, credit assigned from the evidence in §3–§5:

| Plan §2 layer | Credit | Justification |
|---|---|---|
| 1. Source & Storage | 0.40 | Upload, original preservation and unique keys work; no checksums, versions, retention; wrong storage plane per §1.2 |
| 2. Ingestion & Extraction | 0.50 | PDF path is solid and tested; no OCR, no CSV, DOCX/XLSX unreachable, no benchmark |
| 3. Knowledge & Evidence | 0.50 | Chunks + passage citations + status lifecycle for embeddings; no page citations, tags, entities, relationships, or evidence status |
| 4. Methods & Controls | 0.00 | Nothing exists |
| 5. AIOS™ Agents | 0.30 | One well-built RAG use case; no registry, permissions, escalation, kill switch, approval |
| 6. Operating Systems | 0.05 | No Founder Office, PMO or project workspace; only engagement CRUD |
| 7. Control Tower | 0.15 | App shell, navigation, bilingual UI and two live pages; dashboards are mock; no alerts, approvals, or audit views |
| **Sum** | **1.90 / 7** | **27.1 %** |

Sensitivity: ±0.10 credit per layer moves the total to **22.9 % – 31.4 %**. Reported conservatively as **20 – 28 %**.

#### Verification / acceptance readiness — 9 % to 14 %

Requirement-weighted over the 23 P0 items, crediting only progress toward the Plan's own acceptance test: Verified = 1.0, Partial = 0.25–0.40, everything else = 0.

- Lower bound: 8 × 0.25 = 2.00 / 23 = **8.7 %**
- Upper bound: 8 × 0.40 = 3.20 / 23 = **13.9 %**

Reported as **9 – 14 %**.

#### Largest factors that could move the score

**Upward (highest leverage first):**
1. **The audit spine (FND-SEC-03).** Absent, it blocks 8 other requirements; present, it converts several Missing items into achievable-in-one-sprint items. Single largest multiplier.
2. **Server-side role enforcement (FND-SEC-01).** Unblocks FND-GOV-02, FND-KC-05 and FND-AI-01/03, all of which need a defined approver.
3. **Executing and CI-gating the 144 integration tests.** Would convert database-layer tenant isolation from Unverified to Verified — pure verification gain at near-zero build cost.
4. **A generic register framework.** Six Missing requirements (GOV-01, PMO-01/03, PRJ-01/02/03) are variations of one pattern; built once on the audit spine, they land together.
5. **Page-number capture in extraction.** Small contained change; upgrades FND-KC-04 substantially and is a precondition for FND-PRJ-01's "linked to source".

**Downward:**
1. **If the 144 integration tests fail when finally executed**, the tenant-isolation claim in §3.2 weakens materially. This is the single largest unquantified risk in this audit.
2. **If the OneDrive principle is upheld**, the entire storage plane is rework, and FND-KC-01/02 restart.
3. **If data residency forbids the current AI provider path**, the embedding and analysis layers need re-platforming — that is layers 2, 3 and 5 simultaneously.
4. **A security review of the browser-only RBAC** would likely raise further findings beyond the one recorded here.

---

## 8. Security and Reliability Blockers

Ordered by release-blocking severity.

### BLOCKER-1 — No audit trail whatsoever (FND-SEC-03) — CRITICAL

**Observation.** No migration in `backend/migrations/versions/` creates an audit table. Business rows (`documents`, `analysis_runs`, `engagements`) are updated in place with no actor, no previous state and no history. `backend/app/domain/entities/__init__.py:10` mentions `AuditLog` **only as design inspiration from the Hemaya reference project** — it was never implemented. The system has Python application logging (`app/core/logging.py`) and nothing else.

**Why this is the deepest gap.** The Foundation Plan's Non-Negotiable Principle 3 requires every accepted requirement, decision, KPI and report to be traceable to its source or a named human authority. Nothing in this system is currently reconstructable after the fact. Worse structurally: every future register (GOV, PMO, PRJ), every evidence state (KC-05) and every AI disposition (AI-03) must write into this spine. Building any of them first guarantees a full retrofit of all of them.

**Distinction the Plan explicitly demands.** Application logs ≠ business audit events ≠ append-only audit ≠ tamper-evident audit. This repository has **only the first**. Nothing here may be described as tamper-evident.

### BLOCKER-2 — No server-side role enforcement (FND-SEC-01, FND-GOV-02) — CRITICAL

**Observation.** `users.role` is read in exactly one place in the entire backend — `backend/app/api/v1/auth.py:31` — where it is echoed back to the client. A grep for `current_user.role` across `backend/app` returns no authorization use. The five-tier model lives entirely in `frontend/src/features/rbac/roles.ts`, whose own comment (line 5) states *"Server re-validates everything; this is a UX layer only."* **The server does not.**

**Concrete failure.** A user with `role = 'viewer'` sees no Upload navigation item and is bounced from `/documents/upload` by `RoleGuard`. That same user can call `POST /api/v1/documents` directly with their valid token and the upload succeeds. The same holds for process, embeddings, analyze, and engagement create/update. **Every authenticated organization member has effective Owner-level API access.**

**Note on scope.** This is *not* a tenant-isolation failure — cross-organization access is genuinely blocked and negatively tested. It is a within-tenant privilege failure. That distinction matters and should not be blurred in either direction.

### BLOCKER-3 — No demonstrated restore (FND-REL-01) — CRITICAL

**Observation.** No backup script, no restore runbook, no recovery evidence, no RPO/RTO anywhere in the repository. `docker-compose.yml` defines one `api` service and no database. Managed Supabase backup may exist but is **Unverified** and has never been restore-tested. The Plan is explicit: a configured backup without a tested restore does not satisfy this requirement. Here neither is evidenced.

### BLOCKER-4 — No malware scanning or quarantine (FND-SEC-02) — HIGH

**Observation.** Validation is genuinely layered (§3.3) and a renamed executable is rejected by the magic-byte check. But a **structurally valid PDF carrying a malicious payload passes every check**, is stored, is parsed by PyMuPDF, and its text becomes retrievable evidence. `documents.processing_status` has no `PENDING_SCAN` or `QUARANTINED` state. The stated acceptance test — "unsafe test file cannot enter verified evidence" — is not met.

### BLOCKER-5 — Confidential content leaves the system with no governing decision — HIGH

**Observation.** Every chunk of every document is transmitted to an external AI provider on embed (`OpenAIEmbeddingProvider`) and on analysis (`OpenAILLMGateway`). `resolve_ai_credentials` (`backend/app/core/config.py:131-148`) silently falls back from OpenAI to OpenRouter, and OpenRouter routes onward to further upstream providers. The repository contains **no record of an approved provider, no data-processing agreement, no retention position, and no residency statement.** For the Aramco proof case this is a contractual and legal exposure before it is a technical one, and it is a **management decision, not an engineering fix**.

### BLOCKER-6 — No human approval gate (FND-KC-05, FND-AI-03) — HIGH

**Observation.** Retrieval filters on `organization_id` and embedding `status = 'COMPLETED'` only (`document_chunk_embedding.py:232-240`). There is no evidence-review dimension to filter on, no reviewer, no disposition. Non-Negotiable Principle 2 requires human approval before any AI statement becomes official; today **every ingested chunk is automatically authoritative** and no output can be approved. "Official output" is currently an undefined concept in this system — which means the Plan's flagship KPI ("Official output approval coverage = 100 %") is not merely unmet but unmeasurable.

### Secondary security observations

| # | Finding | Severity | Evidence |
|---|---|---|---|
| S-1 | **No RLS defence-in-depth.** No migration contains `CREATE POLICY` or `ENABLE ROW LEVEL SECURITY`. Storage uses the service-role key, which explicitly bypasses RLS (`supabase_document_storage.py:21-23`), and the DB role likewise bypasses it. A single missed service-layer check has no second barrier. | High | migrations; storage module docstring |
| S-2 | **Demo session takes precedence over live session at bootstrap.** `AuthContext.tsx:37-42` calls `service.getSession()` first, which for `ResolvedAuthService` delegates to `mockAuthService` (localStorage `ghp:session`). A demo session present in localStorage is restored and reported `authenticated` **in a production build**, since `isDevAuthBypassEnabled()` gates only session *creation*, not restoration. | Medium — **not a backend bypass** (the API client would send no token and the backend would 401), but a real client-state integrity defect that shows an authenticated shell with no working session | `AuthContext.tsx:37-42`; `resolvedAuthService.ts:43-45`, `:59-61` |
| S-3 | **`VITE_DEV_AUTH_BYPASS=true` is the default in `frontend/.env.example`**, and `frontend/README.md` publishes shared demo credentials and the dev OTP. Correctly neutralised in production builds by Vite's static `import.meta.env.DEV` replacement — but an insecure-by-default example invites a misconfigured environment. | Medium | `frontend/.env.example:11`; `frontend/README.md` |
| S-4 | **No prompt-injection defence.** Document text is interpolated directly into the user prompt (`prompts.py:50`). A hostile PDF can address the model. Mitigated in impact by the `SOURCE_n` indirection and the membership check, but the Plan's §5.1 requirement for malicious-input testing is unmet. | Medium | `prompts.py:45-51` |
| S-5 | **`executive_summary` requires no citation.** `structured_output.py:68-70` imposes `source_keys` on `reported_metrics`, `key_findings` and `recommendations` only. The single most-read field of the output has no grounding obligation. | Medium-High | `structured_output.py:64-74` |
| S-6 | **No dependency or security scanning.** No `pip-audit`, no `npm audit`, no Dependabot, no SAST, no secret scanning in `.github/workflows/ci.yml`. | Medium | `ci.yml:1-48` |
| S-7 | **Container hardening absent.** `backend/Dockerfile` runs as root, has no `HEALTHCHECK`, no pinned base digest, and no non-root user. | Low-Medium | `Dockerfile:1-14` |
| S-8 | **Local/CI Python drift.** Local 3.14.3 vs CI 3.12. Tests pass locally on 3.14 but the gate runs 3.12 — a class of version-specific defect can pass one and fail the other. | Low | `ci.yml:17` |

---

## 9. Technical Debt and Contradictions

| # | Item | Type | Evidence | Impact |
|---|---|---|---|---|
| D-1 | **`backend/README.md` is materially false.** States *"foundation skeleton only (Sprint 1). No business logic, authentication, or AI/RAG features are implemented yet"* and *"No migrations exist yet — `migrations/versions/` is currently empty."* In reality: 8 migrations, full auth, full RAG. | Stale documentation | `backend/README.md:7-8, 45-47` | A reviewer or new engineer trusting the README would misjudge the system in **both** directions |
| D-2 | **`backend/CLAUDE.md` states "Current Sprint: Sprint 1"** and "Do not implement business logic until the architecture is established" — roughly ten sprints behind reality. | Stale governance doc | `backend/CLAUDE.md` | Governance documents that lag the code cannot be used as controls |
| D-3 | **`frontend/README.md` states "mock authentication ... The backend has no auth endpoints yet"** and documents five demo accounts with a shared password as the way in. Live Supabase auth has been implemented since commit `b9fd35d`. | Stale documentation | `frontend/README.md:3-4, 22-24` | Publishes credentials for a path that is no longer the primary one |
| D-4 | **Orphaned `ai_analysis_results` table + model.** Created by migration `693e23cf7797`, modelled at `app/infrastructure/db/models/ai_analysis_result.py`, exported from `models/__init__.py` — and used by **no service, repository or endpoint**. Superseded by `analysis_runs`. | Duplicate/dead implementation | grep: zero non-model references | Two "analysis result" concepts in one schema; a future developer may write to the wrong one |
| D-5 | **`OrganizationService.create` unconditionally raises `AuthorizationError`** — organization creation is disabled for every caller because no provisioning/RBAC design exists yet. The endpoint is still published and documented as 201-returning. | Deliberate, documented restriction — but a functional hole | `app/services/organization.py:33-34`; `api/v1/organizations.py:42-55` | User/organization provisioning is entirely out-of-band. **No user can be onboarded through the system.** |
| D-6 | **Hybrid live/mock auth service.** `ResolvedAuthService` routes `requestLogin`/`restoreSession`/`subscribe` to live and `verifyOtp`/`resendOtp`/`getSession`/`setActiveOrg` to mock. Deliberate and documented — but it is the root cause of S-2. | Transitional architecture | `resolvedAuthService.ts:22-66` | Confusing session semantics; production build restores demo sessions |
| D-7 | **Dashboard is 100 % mock data** while looking like a live executive dashboard, and the Analysis list falls back to seeded demo rows outside a live session. Both carry a `DemoDataBadge` — good practice — but this is precisely the Plan's §13 risk *"Interface mistaken for working capability" (H/High)*. | Demo data presented as capability | `mockDashboardData.ts`; `AnalysisListPage.tsx:80-97` | An unlabelled screenshot of the dashboard would materially misrepresent the system |
| D-8 | **Ten stub pages behind real navigation:** Reports, Organizations, Users, Settings, Notifications, Audit, Frameworks, Carbon, Telemetry, HubZero. | Placeholder modules | `features/placeholders/`, `shell/StubModulePage.tsx` | Navigation breadth implies capability breadth that does not exist |
| D-9 | **Metrics are transcribed, not calculated.** `MetricValue.value` is `str | None`, populated by the LLM reading a document. No deterministic calculation exists anywhere. | Unsafe assumption risk | `structured_output.py:48-54` | Structured output *looks* computed. Any KPI or funding claim built on it today would be unsupported — FND-MTH-01 is Missing for exactly this reason |
| D-10 | **Page numbers destroyed at extraction.** `text_extractor.py:69` joins pages with `"\n"`. Page-level citation is not merely unimplemented — it is **unrecoverable** without changing extraction. | Architectural constraint | `text_extractor.py:63-71` | Blocks FND-KC-04's page-level requirement and weakens FND-PRJ-01 traceability |
| D-11 | **Storage plane contradicts the approved principle.** Plan §1.2: *"OneDrive stores controlled originals; the platform stores structured metadata."* Implementation: originals in Supabase Storage; zero OneDrive/Graph/SharePoint references in the repository. | **Contradiction with approved baseline** | `document_upload.py:72-73`; grep | Requires a Founder decision: implement OneDrive, or formally amend the principle through the Decision Register |
| D-12 | **Provider and residency gap.** `resolve_ai_credentials` silently prefers OpenAI, else OpenRouter — a broker that routes onward. No approved-provider record, no DPA, no retention or residency statement. | Provider/residency gap | `core/config.py:131-148` | See BLOCKER-5 |
| D-13 | **6 commits + ~500 uncommitted lines exist only locally.** Audited branch has no upstream. | Continuity / IP risk | `git branch -vv` | Matches Plan §13 *"Vendor dependency / IP leakage"*. Recent output is one disk failure from loss |
| D-14 | **Root `node_modules/` untracked and un-ignored**; root `.gitignore` contains one unrelated line; no root `package.json`. | Repository hygiene | `.gitignore`; `Get-ChildItem` | Pollutes `git status`; risk of accidental commit |
| D-15 | **Integration tests excluded from the CI gate.** `ci.yml:25` runs `pytest -m "not integration"`, so the 144 tests that prove database-layer tenant isolation never run automatically. | Verification gap | `ci.yml:25` | The most security-relevant tests in the repository are the ones CI does not run |
| D-16 | **No coverage measurement.** No `pytest-cov`, no threshold, no report. | Quality gate gap | `requirements-dev.txt` | "Zero P0 defects" cannot be evidenced without knowing what is untested |

---

## 10. Recommended Phase 1 Backlog

Full sprint definition — stories, DB/backend/frontend changes, security considerations, automated and manual tests, evidence IDs, Definition of Done, out-of-scope, risks and complexity — is at `../05-delivery/Phase1_Recommended_Backlog.md`.

### Recommended first sprint

**"Governance Spine: server-enforced authorization + tamper-evident audit + file quarantine"** — FND-SEC-01, FND-SEC-03, FND-SEC-02, plus CI hardening for FND-TST-01.

**Why this and not something else.** The mandate suggested FND-SEC-01 as the likely priority. The evidence supports it **but shows FND-SEC-03 is at least equally urgent and must ship in the same sprint**, for a structural reason: eight other P0 requirements (GOV-01/02/03, PMO-01/03, KC-05, AI-01/03, PRJ-01) must all write into an audit trail. Build any register, evidence state, or approval workflow before the audit spine and every one of them requires retrofitting. Ordering here is not preference — it determines whether Sprints 2–6 are additive or rework.

FND-SEC-02's quarantine **state machine** joins the sprint because it is cheap and needs no external dependency; the **scanner choice** is deferred pending a management decision (cost + residency).

### Sequence after Sprint 1

| Sprint | Focus | Requirements | Rationale |
|---|---|---|---|
| 1 | Governance spine | SEC-01, SEC-03, SEC-02 (partial), TST-01 (CI) | Unblocks everything; prevents mass retrofit |
| 2 | Evidence lifecycle + human approval | KC-05, AI-03 | Delivers Non-Negotiable Principle 2 |
| 3 | Evidence integrity | KC-02 (checksums, duplicates, versions), KC-04 (page numbers) | Small, contained, high proof value |
| 4 | Register framework | PMO-03 then GOV-01, PMO-01 | One pattern, six requirements |
| 5 | AI governance | AI-01, AI-02 (eval set + injection defence) | Needs an approver, so must follow Sprint 2 |
| 6 | Reliability | REL-01 — **executed** restore, measured RPO/RTO | Independent; can run in parallel from Sprint 2 |
| 7 | Project workspace | PRJ-01/02/03, MTH-01 | Enables the Aramco proof case |

**Deliberately deferred:** everything under FND-FND-01 and every external or funding-facing artefact. Per Plan §13 *"Government pitch overstates maturity"*, no external material may be prepared before G2 is passed and KPI baselines are captured.

---

## 11. Decisions Required From Management

Engineering cannot resolve any of these. Each should be entered into the Decision Register the moment one exists.

| # | Decision | Why engineering cannot decide | Blocks | Urgency |
|---|---|---|---|---|
| **M-1** | **Is OneDrive the mandatory source of record for controlled originals, or is the Plan §1.2 principle formally amended to permit Supabase Storage?** | Amending an approved Non-Negotiable Principle is a Founder authority | FND-KC-01, FND-KC-02, all Knowledge Center work | **Immediate — before any further KC work** |
| **M-2** | **Which AI provider is approved, under what data-processing agreement, with what retention and residency position?** Today the code silently falls back OpenAI → OpenRouter, and OpenRouter routes onward. | Contractual, legal and Aramco-confidentiality question | Any use of real project data; FND-AI-02 | **Immediate — before any real data** |
| **M-3** | **What is the data residency position of the Supabase project** (Postgres and Storage), and is it acceptable for Aramco-adjacent material? | Regulatory/contractual | Real-data readiness, FND-KC-01 | **Immediate** |
| **M-4** | **What is the authoritative role model** (are the five UI tiers correct?) **and who holds which approval authority** per the Delegated Authority Matrix? | Business authority definition, not a technical choice | FND-SEC-01 Sprint 1 delivery, FND-GOV-02, FND-KC-05 | **Immediate — Sprint 1 is blocked without it** |
| **M-5** | **How are users and organizations provisioned?** `OrganizationService.create` is disabled for every caller and `User.organization_id` is assigned out-of-band, so nobody can currently be onboarded through the system. | Requires an approved provisioning and access-granting policy | User onboarding, any pilot with more than one operator | **High** |
| **M-6** | **Malware-scanning approach:** external SaaS scanner (cost, and document content leaves again) vs. self-hosted ClamAV (infrastructure) vs. documented acceptance of the risk for internal synthetic data only. | Cost + residency trade-off | FND-SEC-02 completion | High |
| **M-7** | **Is the current single-organization model the target**, or is multi-organization/multi-project tenancy required for the Aramco proof case and beyond? Today `OrganizationService.list` returns exactly one row. | Product scope | FND-PMO-01 portfolio design | High — determines Sprint 4 schema |
| **M-8** | **Confirm the proof-case data boundary:** exactly which Aramco documents are authorized, and confirmation that none may be loaded until the §8 blockers are closed. | Plan §17 Day 2 action, Founder/Project Lead authority | Weeks 10–12 proof run | High |
| **M-9** | **Approve remediation of the repository continuity risk:** push the 6 local commits, and confirm the IP-assignment and code-handover position with the technical partner. | Plan §13 IP/vendor risk is a Founder/Legal item | Continuity of all recent work | **Immediate — low effort, high consequence** |
| **M-10** | **Accept or reject the revised completion baseline** (20–28 % technical / 9–14 % verified) as the new controlled figure, superseding the historical 30–36 %. | Baseline figures are a Founder approval | All subsequent reporting and any funding narrative | High |
| **M-11** | **Authorize a controlled execution of the 144 integration tests** against a dedicated non-shared database, so database-layer tenant isolation moves from Unverified to Verified. | Requires provisioning a separate environment (cost) | The single largest unquantified risk in this audit | High |
| **M-12** | **Confirm whether page-level citation is mandatory for acceptance.** If yes, extraction must be reworked now, before more documents are ingested under the current lossy pipeline. | Acceptance-criteria interpretation | FND-KC-04, FND-PRJ-01 | Medium-High |

---

## 12. Final Recommendation

### What should happen next

1. **Record this audit as the controlled Phase 0 baseline** and formally supersede the 30 %/36 % figures with **20–28 % technical implementation / 9–14 % verified readiness / 0 of 23 P0 requirements accepted**.
2. **Resolve M-1, M-2, M-3, M-4 and M-9 first.** M-4 blocks Sprint 1 from starting; M-9 takes minutes and removes a single-point-of-failure over all recent work; M-1/M-2/M-3 determine whether parts of the current architecture survive at all.
3. **Authorize Sprint 1 — the governance spine** (FND-SEC-01 + FND-SEC-03 + FND-SEC-02 quarantine + CI hardening) as defined in `Phase1_Recommended_Backlog.md`, on milestone-released budget per Plan §10.1.
4. **Provision a dedicated non-shared test database** and bring the 144 integration tests into the CI gate (M-11). Highest verification return for the lowest build cost in the entire backlog.
5. **Correct the three stale documents** (`backend/README.md`, `backend/CLAUDE.md`, `frontend/README.md`). Governance documents that contradict the code cannot function as controls.

### What must NOT happen yet

- **No real Aramco, client, confidential or regulated data may be loaded into this system.** Four independent blockers (§8) forbid it, and two open legal/residency decisions (M-2, M-3) sit on top of them.
- **No external, government, funding or investor material** may cite this system's capabilities. Per Plan §13, this is precisely the *"Government pitch overstates maturity"* risk; there is currently no measured result to support any benefit claim.
- **No new feature breadth.** No new hubs, no new modules, no filling in of the ten stub pages. The Plan's §13 *"Scope expands into all hubs"* risk is live, and the correct response is depth on the governance spine.
- **No register, workflow or approval feature before the audit spine exists** — building them first guarantees rework of all of them.
- **No claim that tenant isolation is complete.** It is verified at the service/API layer and **Unverified at the database layer** until the integration suite runs in a controlled environment.
- **No G2 (Build) gate sign-off.** The Plan's G2 exit condition requires knowledge ingestion, evidence governance and a functioning project workspace. Evidence governance and the project workspace do not exist.

### Closing judgement

The engineering discipline in this repository is genuinely good — clean architecture, strong authentication, thoughtful anti-fabrication controls in the AI layer, and a real CI gate with 593 passing tests. That is a real asset and it should be said plainly.

It has, however, been aimed at the document-intelligence *pipeline* rather than at the *governance spine* that the Foundation is actually defined by. The Plan's own closing line applies exactly: *"The Foundation succeeds when it changes the operating reality... It does not succeed merely because another release is deployed."* Today the system can ingest a document and produce a cited analysis. It cannot record who decided anything, cannot enforce who is allowed to do what, cannot let a human verify or approve evidence, and cannot prove it could be recovered. Those four capabilities — not more screens — are the Foundation.

---

**Audit integrity statement.** No application source file, migration, database schema, database row, environment file, secret, or dependency was modified in the course of this audit. No secret value was read or printed. No paid AI API was called. No file was uploaded to any external service. No write was made to any shared or production database. No git write operation of any kind was performed. The only files created are the five documents under `project-governance/`.

*Prepared 2026-08-01 against commit `079efef`. Findings are valid for that commit only.*
