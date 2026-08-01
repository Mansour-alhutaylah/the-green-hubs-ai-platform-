# Phase 1 — Recommended First Implementation Sprint

| Field | Value |
|---|---|
| Document ID | GH-SIP-PH1-BACKLOG-001 |
| Derived from | `../01-baseline/SIP_Phase0_Baseline_Audit.md` (commit `079efef`) |
| Controlling baseline | Foundation Requirements & Proof Plan V1.0, 29 July 2026 |
| Status | **Proposed — not implemented.** Phase 0 is an audit and planning phase only. |
| Blocked on | Management decision **M-4** (authoritative role model and approval authorities). Sprint 1 cannot start without it. |

---

## Sprint 1 — "Governance Spine"

### Sprint goal

> Make the system able to answer three questions it currently cannot answer at all:
> **who did it, were they allowed to, and can we prove the record was not altered.**
>
> Concretely: enforce roles on the server, record every business-significant action in an append-only, tamper-evident audit trail, and prevent an unscanned file from entering the evidence pipeline — without changing any existing tenant-isolation behaviour.

### Requirement IDs in scope

| ID | Requirement | Current status | Target status after Sprint 1 |
|---|---|---|---|
| **FND-SEC-01** | Authentication, least-privilege roles and record/project access enforcement on server | Partial | Implemented and Verified |
| **FND-SEC-03** | Tamper-evident audit sequence and protected administrator actions | Missing | Implemented and Verified |
| **FND-SEC-02** | File validation, size/type controls, malware scanning or quarantine workflow | Partial | Partial → quarantine workflow Verified; scanner integration deferred pending **M-6** |
| **FND-TST-01** | Unit, integration, authorization, extraction, agent, calculation and golden-journey tests | Partial | Partial (improved) — integration tests enter the CI gate; agent/calculation/golden-journey remain out of scope |

### Why this sprint and not another

The audit mandate anticipated FND-SEC-01 as the likely first priority. The evidence supports that — **and shows FND-SEC-03 must ship in the same sprint, not after it.**

**The structural argument.** Eight P0 requirements must write into an audit trail: FND-GOV-01 (decisions), FND-GOV-02 (approvals), FND-GOV-03 (traceable figures), FND-PMO-01 and FND-PMO-03 (register history), FND-KC-05 (evidence review states), FND-AI-03 (reviewer and disposition), FND-PRJ-01 (obligation status history). Build any of them before the audit spine and all eight need retrofitting later — the single largest avoidable cost in the remaining programme.

**The authorization argument.** FND-KC-05, FND-AI-01, FND-AI-03 and FND-GOV-02 all require the concept of "who is allowed to approve." That concept does not exist server-side today. Server-side roles are a hard prerequisite for the entire approval half of the Foundation.

**Why not start with the registers or the Aramco workspace?** They are the visible value, but every one of them writes into both mechanisms above. Starting there produces a demo, then a rewrite.

**Why FND-SEC-02 only partially.** The quarantine *state machine* is cheap, has no external dependency, and closes the "unsafe file enters verified evidence" path by construction. The *scanner* itself carries cost and data-residency implications and is a management decision (**M-6**). Shipping the state machine now means the scanner is later a plug-in, not a schema change.

---

## Stories

### Epic A — Server-side authorization (FND-SEC-01)

| ID | Story | Acceptance |
|---|---|---|
| **A-1** | As the Founder, I want the authoritative role model and per-action authority recorded in code from an approved source, so the UI and the server agree. | A single server-side permission map exists, derived from the **M-4** decision. Frontend `roles.ts` tiers are reconciled against it; any divergence is either fixed or explicitly recorded. |
| **A-2** | As a security reviewer, I want a reusable authorization dependency, so no endpoint can be added without an explicit permission declaration. | A `require_permission(...)` FastAPI dependency exists alongside `get_current_user`. It raises `AuthorizationError` (403). **Existing tenant checks are not moved or altered.** |
| **A-3** | As a Viewer, I must be denied write actions at the API even when I bypass the UI. | `POST /documents`, `POST /{id}/process`, `POST /{id}/embeddings`, `POST /engagements`, `PATCH /engagements/{id}`, `PATCH /organizations/{id}`, `POST /analysis/**` each carry an explicit permission. Viewer receives 403 on every one. |
| **A-4** | As an auditor, I want every denied attempt recorded, so refused access is evidence, not silence. | Every `AuthorizationError` raised by A-2 writes an audit event (Epic B) with actor, endpoint, resource id and reason. |
| **A-5** | As a security reviewer, I want RLS as defence-in-depth so a missed service check is not a single point of failure. | RLS enabled with policies on the tenant-scoped tables, plus a documented, explicit statement of which connection role bypasses it and why. **Design + migration authored this sprint; enabling on any shared instance is gated on M-11's dedicated environment.** |

### Epic B — Tamper-evident audit trail (FND-SEC-03)

| ID | Story | Acceptance |
|---|---|---|
| **B-1** | As the Founder, I want every business-significant action recorded with actor, time, action, resource, previous state and new state. | An `audit_events` table exists with: `id`, `organization_id`, `actor_user_id`, `actor_role`, `action`, `resource_type`, `resource_id`, `previous_state` (JSONB), `new_state` (JSONB), `reason`, `outcome` (allowed/denied), `request_id`, `occurred_at`, `sequence_number`, `previous_hash`, `entry_hash`. |
| **B-2** | As an auditor, I want the trail to be append-only. | No `UPDATE` or `DELETE` path exists in application code. Database-level protection (trigger or revoked grants) blocks both. A test proves an update attempt fails. |
| **B-3** | As an auditor, I want alteration to be **detectable**, not merely discouraged. | Each row's `entry_hash` = SHA-256 over its canonical content **plus the previous row's `entry_hash`**, forming a chain per organization. A `verify_audit_chain` routine walks the chain and reports the first break. A test mutates a row directly in SQL and proves verification fails at that exact row. |
| **B-4** | As an engineer, I want auditing to be a service-layer concern, not scattered through routers. | A single `AuditService` / audit unit-of-work writes events. Audit writes participate correctly in the surrounding transaction semantics — **a failed business operation must not leave a "succeeded" audit event, and a denied attempt must be recorded even though nothing else is written.** |
| **B-5** | As the Founder, I want the actions that already exist covered from day one. | Audited: login-resolution failure (`ProfileNotProvisionedError`), document upload, process, embedding generation, analysis run start/complete/fail, engagement create/update, organization update, and every authorization denial from A-4. |
| **B-6** | As an auditor, I want administrator-class operations distinguished and protected. | Actions classified admin-class are flagged in the event and require the elevated permission from A-2. |

### Epic C — File quarantine workflow (FND-SEC-02, partial)

| ID | Story | Acceptance |
|---|---|---|
| **C-1** | As a Knowledge Lead, I want an uploaded file to be non-authoritative until cleared. | `documents.processing_status` gains `PENDING_SCAN` and `QUARANTINED`. Upload lands in `PENDING_SCAN`, never `PENDING`. |
| **C-2** | As a Knowledge Lead, I want processing to be impossible before clearance. | `DocumentProcessingService.process` raises `InvalidStateTransitionError` (409) for `PENDING_SCAN` and `QUARANTINED`. Tested. |
| **C-3** | As a security reviewer, I want the scanner to be a pluggable port, not a rewrite. | An `IFileScanner` domain port exists with a `NullFileScanner` that **explicitly quarantines by default** unless an approved-scanner setting is present — fail-closed, never fail-open. Concrete scanner deferred to **M-6**. |
| **C-4** | As an auditor, I want scan outcomes on the record. | Clearance and quarantine both write audit events (Epic B). |

### Epic D — CI hardening (FND-TST-01, partial)

| ID | Story | Acceptance |
|---|---|---|
| **D-1** | As a security reviewer, I want database-layer tenant isolation continuously verified. | CI gains an ephemeral Postgres + pgvector service container; the full suite including the 144 integration tests runs on every PR. **No shared or production database is ever contacted by CI.** |
| **D-2** | As a QA lead, I want to know what is untested. | Coverage measured and reported; a baseline threshold agreed (not retro-fitted to pass). |
| **D-3** | As a security reviewer, I want dependency risk visible. | `pip-audit` and `npm audit` run in CI; findings reported (non-blocking in Sprint 1, blocking from Sprint 2). |
| **D-4** | As an engineer, I want local and CI Python aligned. | CI Python matrix reconciled with the local 3.14 runtime, or the local runtime formally pinned to 3.12. |

---

## Dependencies

| Dependency | Type | Blocks | Status |
|---|---|---|---|
| **M-4** — authoritative role model + approval authorities | Management decision | **All of Epic A**, therefore the sprint | **OPEN — start blocked** |
| **M-11** — dedicated non-shared test database | Management decision + provisioning | D-1; the verification half of A-3/A-5/B-2/B-3 | **OPEN — high priority** |
| **M-6** — malware scanner approach | Management decision | C-3 concrete scanner (state machine unaffected) | Open — does not block the sprint |
| **M-9** — push local commits, confirm IP/handover | Management decision | Continuity of all work, including this sprint's | **OPEN — minutes of effort** |
| Existing tenant isolation (`§3.2` of the audit) | Technical | Epic A builds beside it | **Available** |
| Existing `AppError` envelope (`core/exceptions.py`) | Technical | A-2 reuses `AuthorizationError` | **Available** |
| Alembic chain head `da0298a9c722` | Technical | New migrations extend it | **Available** |
| Existing CI workflow | Technical | Epic D extends it | **Available** |

**Not depended on and deliberately untouched:** the AI provider layer, the extraction pipeline, the embedding/retrieval layer, and the frontend live pages.

---

## Expected changes

### Database (new migrations only — no existing table is altered destructively)

| Change | Type | Notes |
|---|---|---|
| `audit_events` table | New | Append-only; hash-chained; indexed on `(organization_id, sequence_number)`, `(resource_type, resource_id)`, `occurred_at` |
| Append-only protection | New | Trigger or revoked `UPDATE`/`DELETE` grants on `audit_events` |
| `documents.processing_status` | Extend | Add `PENDING_SCAN`, `QUARANTINED`. **Additive: existing rows keep their current values; no backfill that would rewrite history.** |
| `documents.scan_status`, `scanned_at` | New columns | Nullable |
| RLS policies on tenant-scoped tables | New | Authored this sprint; enabling gated on M-11 |
| **Not in scope** | — | No change to `organizations`, `users`, `engagements`, `document_chunks`, `document_chunk_embeddings`, `analysis_runs`, `analysis_source_references` |

### Backend

| Area | Change |
|---|---|
| `app/domain/entities/` | New `AuditEvent` entity |
| `app/domain/repositories/` | New `IAuditEventRepository` (append + read + verify-chain; **no update, no delete**) |
| `app/domain/security/` | New `Permission` / `Role` value objects and the permission map |
| `app/domain/scanning/` | New `IFileScanner` port |
| `app/services/audit.py` | New `AuditService` |
| `app/api/deps.py` | New `require_permission(...)`; `get_audit_service`; `get_file_scanner` |
| `app/api/v1/*.py` | Add an explicit permission declaration to each mutating endpoint. **No change to existing tenant logic.** |
| `app/services/document_upload.py` | Land in `PENDING_SCAN`; emit audit event |
| `app/services/document_processing.py` | Reject `PENDING_SCAN`/`QUARANTINED`; emit audit events |
| `app/services/engagement.py`, `organization.py`, `analysis/rag_analysis.py` | Emit audit events at state transitions |
| `app/core/exceptions.py` | Audit hook on `AuthorizationError` |
| `app/infrastructure/repositories/audit_event.py` | New — append-only, hash-chained |

### Frontend

Deliberately minimal — this sprint is a server-side sprint.

| Area | Change |
|---|---|
| `lib/api/errors.ts` | Ensure 403 from `require_permission` surfaces as a distinct, actionable message rather than a generic failure |
| Documents pages | Render `PENDING_SCAN` / `QUARANTINED` states truthfully (no silent "processing") |
| `features/rbac/roles.ts` | Reconcile tiers with the server permission map; the UI must never offer an action the server will refuse |
| **Explicitly not in scope** | No audit-viewer UI, no admin console, no dashboard change |

---

## Security considerations

1. **Do not weaken what works.** Existing tenant isolation is the strongest control in the system. Authorization is **added beside** it, never refactored into it. Every existing tenant test must still pass unchanged — that is a hard gate.
2. **Fail closed everywhere.** Unknown role → deny. Missing permission declaration → deny. Scanner unavailable → quarantine. No default-allow path may exist.
3. **Preserve the 404-vs-403 discipline.** Cross-tenant probes must keep returning 404 (§3.2 of the audit); the new 403 is for *within-tenant* privilege denial only. Confusing the two would leak tenant existence.
4. **The audit trail must not become a leak.** `previous_state`/`new_state` must never store document content, tokens, credentials, or full connection strings. A test asserts no known secret-shaped value can be written.
5. **Audit availability must not break business operations, and audit integrity must not be silently sacrificed.** If an audit write fails, the outcome must be an explicit, deliberate, documented decision (fail-closed for admin-class actions is the recommended default) — never an unnoticed skip.
6. **Hash chain must cover what matters.** The canonical hash input must include actor, action, resource, both states, and the previous hash. Excluding any of these makes the chain decorative.
7. **RLS is defence-in-depth, not a replacement.** Service-layer checks stay. The bypass role must be documented explicitly (`supabase_document_storage.py:21-23` already notes the storage side; the DB side must be stated too).
8. **No secret may enter CI logs.** The ephemeral CI database must use a throwaway credential and never `backend/.env`.

---

## Tests

### Automated (must exist and pass before Definition of Done)

| # | Test | Category | Proves |
|---|---|---|---|
| T-1 | Each role × each mutating endpoint → expected 200/403 | Authorization, negative | FND-SEC-01 A-3 |
| T-2 | Viewer bypassing the UI and calling `POST /documents` directly → 403 | Authorization, negative | The exact BLOCKER-2 failure is closed |
| T-3 | Every existing cross-tenant test still passes unchanged | Regression | No isolation weakened |
| T-4 | Endpoint without a permission declaration → denied (or CI fails) | Structural | No endpoint can be added unguarded |
| T-5 | Each audited action writes exactly one event with correct actor/resource/states | Audit | FND-SEC-03 B-1/B-5 |
| T-6 | `UPDATE` and `DELETE` against `audit_events` both fail | Audit, negative | Append-only (B-2) |
| T-7 | Direct SQL mutation of one audit row → chain verification fails at that row | Audit, tamper-evidence | **B-3 — the acceptance test of FND-SEC-03** |
| T-8 | Denied attempt writes an audit event even though no business write occurs | Audit | A-4 |
| T-9 | Failed business operation writes no "succeeded" event | Audit, transactional | B-4 |
| T-10 | Upload lands in `PENDING_SCAN`; process on `PENDING_SCAN`/`QUARANTINED` → 409 | State machine | FND-SEC-02 C-1/C-2 |
| T-11 | `NullFileScanner` quarantines by default | Fail-closed | C-3 |
| T-12 | Audit payload rejects/redacts secret-shaped values | Security | Consideration 4 |
| T-13 | RLS policy tests against the ephemeral database | Defence-in-depth | A-5 |
| T-14 | Full suite incl. all 144 integration tests green in CI | Verification | D-1 |

### Manual (evidence-producing, performed once and recorded)

| # | Test | Evidence produced |
|---|---|---|
| M-T1 | Authenticate as each role in turn and attempt every controlled action via direct API call (not the UI) | Authorization test record → EV-SEC |
| M-T2 | Tamper with one audit row via direct SQL in the dedicated environment; run chain verification; capture the failure output | Tamper-evidence demonstration → EV-SEC |
| M-T3 | Upload a valid PDF, confirm `PENDING_SCAN`, attempt processing, confirm 409, confirm audit events | Quarantine walkthrough → EV-SEC |
| M-T4 | Attempt a cross-tenant read with a second organization's token; confirm 404 and an audit event | Tenant-isolation re-confirmation → EV-SEC |
| M-T5 | Review one week of audit output with the Founder for completeness and readability | Founder acceptance record → EV-GOV |

---

## Evidence IDs produced

| Evidence ID | Artefact | Owner |
|---|---|---|
| **EV-SEC-01** | Role × endpoint authorization matrix with executed results (T-1, T-2, M-T1) | Security Reviewer |
| **EV-SEC-02** | Audit append-only + tamper-evidence demonstration output (T-6, T-7, M-T2) | Security Reviewer |
| **EV-SEC-03** | File quarantine workflow test record (T-10, T-11, M-T3) | Technical Lead |
| **EV-SEC-04** | Cross-tenant negative test re-confirmation post-change (T-3, M-T4) | Security Reviewer |
| **EV-ARC-01** | Authorization model + audit schema decision record, including the RLS bypass-role statement | Technical Lead |
| **EV-GOV-01** | Approved role model and Delegated Authority mapping from **M-4** | Founder Office |
| **EV-KPI-01** | Baseline for "Critical authorization failures = 0" (Plan §7) | PMO |

---

## Definition of Done

Per Plan §14.1, every item required:

- [ ] Requirement implemented in the controlled environment.
- [ ] Acceptance test executed **with the result retained** — specifically T-7 (tamper evidence) and T-2 (privilege denial), the two that close the named blockers.
- [ ] Security and data-boundary impact reviewed by the cybersecurity specialist.
- [ ] User guidance / SOP updated — **including correcting the three stale documents** (`backend/README.md`, `backend/CLAUDE.md`, `frontend/README.md`), which currently contradict the code.
- [ ] Evidence ID linked to each requirement (table above).
- [ ] Named business owner accepts the result (Founder for EV-GOV-01; Security Reviewer for EV-SEC-*).
- [ ] Open defects recorded with severity and due date.
- [ ] `ruff`, `mypy`, `oxlint`, `tsc` all clean; full suite **including integration tests** green in CI.
- [ ] Zero P0 defects open.
- [ ] All work **committed and pushed to `origin`** (closes the continuity risk in audit §2).

---

## Explicitly out of scope

Naming these prevents the Plan's §13 *"Scope expands into all hubs"* risk from materialising inside the sprint.

| Out of scope | Why |
|---|---|
| Decision Register, Authority Matrix UI, CEO brief (FND-GOV-01/02/03) | Must be built **on** the audit spine, not beside it |
| Master Portfolio, six-gate lifecycle, PMO registers (FND-PMO-01/02/03) | Same |
| Requirement/deliverable/RFI registers (FND-PRJ-01/02/03) | Same |
| Evidence review states and human approval (FND-KC-05) | Sprint 2 — needs Sprint 1's roles first |
| Agent registry, kill switch, evaluation set (FND-AI-01/02) | Sprint 5 — needs an approver first |
| Checksums, duplicates, versions (FND-KC-02) | Sprint 3 |
| Page-number capture (FND-KC-04) | Sprint 3 |
| Deterministic calculation engine (FND-MTH-01) | Sprint 7 |
| Backup and tested restore (FND-REL-01) | Sprint 6 — independent, may run in parallel |
| OCR, CSV, DOCX/XLSX end-to-end (FND-KC-03) | Blocked on M-1/M-3 |
| OneDrive integration (FND-KC-01) | **Blocked on M-1** — a management decision, not a task |
| Concrete malware scanner | **Blocked on M-6**; the port and fail-closed default ship regardless |
| Audit-viewer UI / admin console | Server-side integrity first; a viewer over an untrustworthy trail is worse than none |
| Any dashboard, reports, or stub-page work | No new breadth |
| Any Aramco or real client data | Forbidden until §8 blockers close and M-2/M-3/M-8 resolve |
| Any external, funding or government material | Plan §13 — no measured result exists to support a claim |

---

## Risks

| # | Risk | L / I | Treatment | Owner |
|---|---|---|---|---|
| R-1 | **M-4 does not arrive, and engineering invents a role model.** Highest-probability failure mode — it would embed an unapproved authority model into the system's foundation. | H / High | **Do not start Epic A without M-4.** If it slips, deliver Epics B and D first — the audit spine has no dependency on the role model. | Founder |
| R-2 | **Adding authorization breaks existing tenant isolation.** | M / Critical | T-3 makes the unchanged existing tenant suite a hard gate. Authorization is added beside, never refactored into, tenant logic. | Technical |
| R-3 | **Audit writes coupled into business transactions cause deadlocks or partial states.** | M / High | Explicit transaction design in EV-ARC-01 before implementation; T-8 and T-9 pin both directions. | Technical |
| R-4 | **The hash chain is decorative** — e.g. hashing only the id, or leaving `UPDATE` reachable. | M / Critical | T-7 requires a *demonstrated* detection of a real SQL-level mutation. A chain that cannot fail this test is not tamper-evident. | Security Specialist |
| R-5 | **M-11 does not arrive**, so the integration suite and RLS stay unverified. | M / High | Escalate immediately — this is the largest unquantified risk carried forward from Phase 0. RLS migrations may be authored but must not be enabled against shared infrastructure. | Founder |
| R-6 | **Quarantine-by-default blocks all internal testing** because no scanner exists. | H / Medium | Fail-closed default plus an explicit, audited, environment-gated override for the internal synthetic-data environment only. Never available in a production configuration. | Technical |
| R-7 | **Scope creep into registers** once the audit spine exists and looks ready to build on. | H / High | The out-of-scope table above is frozen for the sprint; changes only via the Change Register. | Founder |
| R-8 | **Local Python 3.14 vs CI 3.12 masks a defect** in new code. | L / Medium | D-4 resolves the drift within the sprint. | Technical |
| R-9 | **Work again exists only locally.** | M / High | Push-to-origin is a Definition-of-Done item, not an afterthought. | Technical |

---

## Estimated complexity

Complexity only — **no time guarantee**, per the audit mandate. Scale: S / M / L / XL relative to the existing codebase.

| Epic | Complexity | Reasoning |
|---|---|---|
| **A — Server-side authorization** | **M** | The clean architecture makes this genuinely tractable: one new dependency, one permission map, one declaration per endpoint. The hard part is not code — it is M-4 and the exhaustive role × endpoint negative test matrix. |
| **B — Tamper-evident audit** | **L** | New table, new repository, append-only enforcement, hash chain, transaction semantics, and instrumentation of ~10 call sites. The hash chain and transaction design carry the real difficulty. |
| **C — Quarantine workflow** | **S** | Two status values, one guard, one fail-closed port. Deliberately small. |
| **D — CI hardening** | **S–M** | Service container plus pgvector setup is routine; the unknown is whether the 144 integration tests pass on first CI execution — see R-5 and audit §7.3. |
| **Sprint total** | **L** | Concentrated, foundational, with one hard external dependency (M-4) and one significant unknown (integration-suite behaviour in CI). |

**Recommendation on release:** fund this sprint under the Plan §10.1 milestone-release model, and hold the release conditional on **EV-SEC-02 (demonstrated tamper evidence)** and **EV-SEC-01 (demonstrated privilege denial)**. Those two artefacts, and not a passing screen, are what closes the two critical blockers.

---

*Proposed 2026-08-01. Not to be implemented until the Phase 0 audit is reviewed and explicitly approved, and until decision M-4 is recorded.*
