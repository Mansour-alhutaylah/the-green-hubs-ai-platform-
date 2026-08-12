# Phase 1 MVP Slice 4 Evidence Lifecycle and Verified-Only Retrieval Design

Evidence IDs: **EV-KC-05-01**, **EV-ARC-EVID-01**

Date: 2026-08-12 (Asia/Riyadh)

Branch: working tree on `main` (uncommitted — see "Release state" below)

Baseline commit: `284e27b` (Merge PR #10, MVP Slice 3 Organization Data Isolation)

Backlog reference: `Phase1_Recommended_Backlog.md` — FND-KC-05 (evidence review
states and human approval), the state half. Builds directly on Slice 2
(server-side authorization) and Slice 3 (organization data isolation).

## Scope

Slice 4 makes human approval a precondition for evidence retrieval.

The invariant it closes:

> Only evidence explicitly VERIFIED by an authorized human reviewer may enter
> normal retrieval.

Before this slice, any document that reached `processing_status = 'PROCESSED'`
and had embeddings generated was retrievable. There was no concept of a human
having looked at it. A document was usable as evidence because a *parser*
succeeded, not because a *person* approved it.

It adds no new page, no dashboard, no audit table, no answer-approval workflow
and no clearance model. The frontend is untouched.

---

## 1. Two lifecycles, deliberately separate

| | Technical processing lifecycle | Human evidence lifecycle |
|---|---|---|
| Column | `documents.processing_status` | `documents.evidence_status` |
| Owner | `DocumentProcessingService` | `EvidenceReviewService` |
| States | `PENDING` → `PROCESSING` → `PROCESSED` / `FAILED` | `PENDING_REVIEW`, `VERIFIED`, `REJECTED`, `RESTRICTED`, `SUPERSEDED` |
| Meaning | did extraction and chunking succeed | did a human approve this as evidence |
| Decided by | the pipeline | an authorized reviewer |

The combination that matters most is legal and common:

```
processing_status = PROCESSED
evidence_status   = PENDING_REVIEW
→ retrieval-ineligible
```

`PROCESSED` says the text was extracted. It says nothing about whether the
document is the right document, the current version, from a trustworthy source,
or free of figures a reviewer would refuse to stand behind. Only `VERIFIED`
says that, and only a human can put it there.

The two lifecycles are otherwise orthogonal, with exactly one documented
coupling (§3).

---

## 2. The state model

The five states are **five distinct business outcomes, not a sequence**. The
authoritative matrix lives in `app/domain/evidence/lifecycle.py`
(`ALLOWED_TRANSITIONS`) and is asserted cell-by-cell — all 5 × 4 pairs — in
`tests/domain/evidence/test_lifecycle.py`.

| from \ command | VERIFY | REJECT | RESTRICT | SUPERSEDE |
|---|---|---|---|---|
| `PENDING_REVIEW` | yes¹ | yes | yes | yes |
| `VERIFIED` | repeat² | yes | yes | yes |
| `REJECTED` | **no** | repeat² | **no** | **no** |
| `RESTRICTED` | **no** | **no** | repeat² | **no** |
| `SUPERSEDED` | **no** | **no** | **no** | repeat² |

¹ subject to the processing precondition (§3).
² the document already holds the command's target state — resolved by the
repeat-equivalence rule (§5), never by the matrix.

**Withdrawal is supported; reactivation is not.** A `VERIFIED` document can be
withdrawn to any of the three refusal states when new information appears,
because evidence that turns out to be wrong must be removable. The reverse is
refused: Slice 4 defines no approved re-review command, and letting a second
`verify` undo a rejection would make the rejection decorative.

**Terminal states are terminal for every command**, not only for `VERIFY`. A
`REJECTED` document cannot be `RESTRICTED` and vice versa. All three are already
retrieval-ineligible, so nothing unsafe is preserved; what is preserved is the
recorded decision, which this slice has no approved mechanism to replace.

**`SUPERSEDE` from `PENDING_REVIEW` is allowed.** A document can be made obsolete
by a newer upload before anyone reviews it. Both states are ineligible, so this
moves nothing into an approved state.

---

## 3. The processing precondition (the one coupling)

`required_processing_status_for()`:

| command | requires |
|---|---|
| `VERIFY` | `processing_status = 'PROCESSED'` |
| `REJECT` / `RESTRICT` / `SUPERSEDE` | nothing |

Approving a document asserts something about *content* that does not exist until
extraction and chunking have completed. `PENDING`, `PROCESSING`, `FAILED` and a
missing/malformed value are all refused, fail-closed.

The direction is deliberate: withdrawal carries **no** precondition, because a
document whose extraction failed is exactly the kind that needs rejecting, and a
precondition there would strand it in `PENDING_REVIEW` permanently.

The check is enforced **inside the conditional UPDATE's predicate**, not only by
the earlier application read — a document can begin reprocessing in between.
`test_a_processing_change_between_read_and_write_blocks_verification` proves the
window is closed against the real database.

---

## 4. No arbitrary state mutation

There is **no** `PATCH /documents/{id}` and no request model anywhere accepts an
evidence column. The lifecycle is driven by four explicit commands:

```
POST /api/v1/documents/{document_id}/evidence/verify      (reason optional)
POST /api/v1/documents/{document_id}/evidence/reject      (reason required)
POST /api/v1/documents/{document_id}/evidence/restrict    (reason required)
POST /api/v1/documents/{document_id}/evidence/supersede   (reason required,
                                                           successor optional)
```

Each command: authenticates the caller; authorizes them against
`Permission.EVIDENCE_REVIEW`; resolves the organization server-side from the
profile; locates the document under that organization predicate *in SQL*;
validates the current state, the transition, and the processing precondition;
derives `reviewed_by` from the authenticated profile and `reviewed_at` from the
database clock; and writes the transition atomically.

The client never supplies — and has no field through which it could supply —
reviewer identity, organization identity or review timestamp.
`superseded_by_document_id` is the one client-supplied evidence *column*, and it
is accepted only on the `supersede` command's own schema; the other three routes
bind schemas without the field. All of this is pinned structurally in
`tests/api/test_document_evidence.py`.

### Authorization

`Permission.EVIDENCE_REVIEW` (`evidence.review`) is added to the Slice 2 catalog
and granted to every role that already holds write permissions —
`editor`, `approver`, `admin`, `owner` — and to no other. `viewer` is denied, as
are unrecognized and missing roles.

**This is the coarsest split that closes the property Slice 4 needs, and it is
deliberately not the final answer.** Which roles may *approve evidence* is
management decision **M-4**, still open, and backlog risk **R-1** explicitly
forbids engineering from inventing an authority model. Narrowing
`evidence.review` to approver-class roles when M-4 lands is a one-line edit to
`ROLE_PERMISSIONS` plus a one-line edit to its pinning test. The API tests derive
their allowed/denied role sets from the live policy rather than hardcoding role
names, so they follow that change instead of blocking it.

---

## 5. Atomic transitions and concurrency

The decision is a single conditional, immediately-committed `UPDATE`
(`_TRANSITION_EVIDENCE_SQL`). Every clause in its `WHERE` is load-bearing:

```sql
UPDATE documents AS d
SET evidence_status = :new_status,
    reviewed_by = :reviewed_by,
    reviewed_at = now(),
    review_reason = CAST(:review_reason AS text),
    superseded_by_document_id = CAST(:superseded_by_document_id AS uuid),
    updated_at = now()
WHERE d.id = :document_id
  AND d.evidence_status = :expected_status                    -- concurrency guard
  AND EXISTS (SELECT 1 FROM engagements e                     -- tenant predicate
              WHERE e.id = d.engagement_id
                AND e.organization_id = :organization_id)
  AND (CAST(:required_processing_status AS varchar) IS NULL   -- approval precondition
       OR d.processing_status = CAST(:required_processing_status AS varchar))
  AND (CAST(:superseded_by_document_id AS uuid) IS NULL       -- successor ownership
       OR EXISTS (SELECT 1 FROM documents s
                  JOIN engagements se ON se.id = s.engagement_id
                  WHERE s.id = CAST(:superseded_by_document_id AS uuid)
                    AND se.organization_id = :organization_id
                    AND s.id <> d.id))
RETURNING ...
```

A read, an inspection in Python, and an unconditional write by id would let a
second reviewer's decision be silently replaced. Here the loser of the race
matches zero rows and changes nothing; the service then re-reads (tenant-scoped)
and answers truthfully — the decision that stands, or a 409 naming the current
state. `_explain_lost_transition` handles every branch and, when nothing accounts
for the zero-row result, returns a generic conflict rather than inventing a
missing successor.

### Retry behaviour (documented and deterministic)

Repeating a command is an **idempotent success only when the document already
holds the target state *and* the request is materially the same decision** —
same normalized reason, same successor. The stored decision is then returned
unchanged, with its original reviewer and timestamp, and nothing is written: a
retried `verify` cannot take attribution for someone else's approval.

A repeat carrying a **different** reason or successor is a different decision.
Since Slice 4 has no approved path for replacing a recorded one, it is a **409**
that leaves the stored decision standing — never a silent success that would
report an unrecorded correction as recorded.

---

## 6. Successor rules

`supersede` may optionally record a successor. It must exist, must belong to the
caller's own organization, and must not be the document itself. A cross-tenant
valid UUID returns the same 404 as an unknown one, so the field is not an
existence oracle.

**Recording a successor does not approve it.** V4 → `SUPERSEDED` leaves V5
exactly as it was, typically `PENDING_REVIEW`; V5 becomes retrievable only when
a human verifies it in its own right.

---

## 7. Verified-only retrieval

`RETRIEVAL_ELIGIBLE_STATUSES = {VERIFIED}`. The predicate is applied **before
ranking and before `LIMIT`**, in the same statement:

```sql
FROM document_chunk_embeddings dce
JOIN document_chunks dc ON dc.id = dce.chunk_id
JOIN documents d ON d.id = dce.document_id
WHERE dce.organization_id = :organization_id
  AND d.evidence_status = ANY(:retrieval_eligible_statuses)
  AND dce.status = 'COMPLETED'
  ...
ORDER BY dce.embedding <=> :query_vector
LIMIT :top_k
```

Filtering a ranked page afterwards would let an ineligible document's stronger
match consume a `top_k` slot and silently shrink the approved evidence returned.
`test_a_stronger_unverified_match_never_displaces_a_verified_one` is built to
fail against that design: the REJECTED document holds the exact query text
(distance 0), the VERIFIED one holds merely related text, and `top_k=1` is
requested. A post-ranking filter returns an empty list; only a pre-ranking
predicate returns the verified document. The test additionally proves, directly
against the database, that the rejected document *would* rank first without the
predicate.

There is exactly one vector-retrieval path in the codebase
(`SQLAlchemyDocumentChunkEmbeddingRepository.search`), reached by
`VectorRetrievalService.search`, which serves both `POST /retrieval/search` and
`RagAnalysisService`. Grounded analysis therefore inherits the same gate: a
non-verified document contributes no chunks, and the run records insufficient
evidence rather than citing unapproved material.

Withdrawal takes effect on the **next query** with no re-embedding or
reindexing, because the state is read live from `documents` by the ranking query
itself.

---

## 8. Embeddings are not deleted

Rejection, restriction and supersession change **eligibility, not existence**.
No evidence command deletes a document, its extracted text, its chunks, its
embeddings, or its stored object. Embeddings may also be generated *before*
verification — the pipeline stays independent of the review. Deleting vectors as
a way of enforcing eligibility would destroy the record of what was rejected and
would make a later re-review slice impossible.

---

## 9. Migration and legacy data

New revision **`b7d41e0c9a52`**, predecessor **`a4f1c9d2e7b3`**. Additive only:
five columns, two foreign keys, four CHECK constraints, one index. No existing
column is altered and no existing row is rewritten beyond receiving the column
default.

**Every pre-existing document becomes `PENDING_REVIEW`, and therefore
retrieval-ineligible.** This is the deliberate fail-closed choice: the platform
has never had a human evidence approval, so there is no basis on which any
historical row could be backfilled as `VERIFIED`. Backfilling approval would
fabricate the exact record this slice exists to create.

This is proved as a real migration, not simulated:
`tests/integration/test_evidence_migration.py` downgrades to `a4f1c9d2e7b3`,
inserts a `PROCESSED` document while the evidence columns genuinely do not
exist, upgrades through `b7d41e0c9a52`, and asserts the row is `PENDING_REVIEW`
with no invented reviewer or timestamp. It also proves the migration is
reversible and re-appliable (upgrade → downgrade → upgrade).

Database-level invariants (all proved by raw-SQL negative tests):

| Constraint | Enforces |
|---|---|
| `ck_documents_evidence_status` | only the five canonical spellings |
| `ck_documents_evidence_review_consistency` | `PENDING_REVIEW` carries no review metadata; every decided state carries a reviewer and timestamp; `REJECTED`/`RESTRICTED`/`SUPERSEDED` carry a reason; only `SUPERSEDED` may carry a successor |
| `ck_documents_review_reason_format` | non-blank, ≤ 1000 characters |
| `ck_documents_not_superseded_by_self` | no self-supersession |
| `fk_documents_reviewed_by_users` | a reviewer must be a real user |
| `fk_documents_superseded_by_document` | a successor must be a real document |

---

## 10. Implemented

- Separate technical processing and evidence-review lifecycles.
- Explicit human evidence decisions — four named commands, no generic mutation.
- VERIFIED-only retrieval, enforced before vector ranking and `LIMIT`.
- Tenant-scoped evidence review; cross-tenant documents and successors are
  indistinguishable from nonexistent ones.
- Atomic conditional transitions; stale reviews cannot overwrite newer decisions.
- Processing prerequisite for `VERIFY` only, enforced in the same statement.
- Reason rules (required for withdrawal, optional note for approval,
  whitespace-only rejected, bounded) validated server-side and at the database.
- Successor rules, including "supersession never approves the successor".
- Deterministic retry semantics with material repeat-equivalence.
- Fail-closed legacy migration.

## 11. Explicit limitations — what Slice 4 does NOT provide

**Current-state provenance is not audit history.** The four review columns record
what the decision *is now*, who made it, when and why. Each transition
**overwrites the previous reviewer, timestamp and reason in place**. There is no
record that a document was verified before it was rejected, or by whom.

Slice 4 does **not** provide:

- append-only decision history;
- tamper-evident audit or hash chains (Slice 8 / FND-SEC-03);
- page or passage citation preservation (Slice 5);
- prompt-injection defences or grounded-answer redesign (Slice 6);
- human approval of AI answers (Slice 7);
- Golden Journey / UAT evidence (Slice 9);
- any re-review, reopen or reactivation workflow;
- document clearance, classification or per-user visibility;
- a review dashboard, bulk review, or any frontend change at all.

### Remaining risks

| # | Risk | Assessment |
|---|---|---|
| R-1 | **Overwritten review metadata.** A `VERIFIED → REJECTED` transition destroys the prior approval's reviewer, timestamp and note. Nothing can reconstruct who approved it or when. | Accepted for this slice; closed by the tamper-evident audit slice. Must not be described as auditable history in the meantime. |
| R-2 | **Terminal states have no approved exit.** A document rejected in error cannot be corrected through the API; it needs a new upload or a future re-review command. | Deliberate. Inventing a reopen path would weaken the refusal this slice exists to create. |
| R-3 | **`evidence.review` role mapping is provisional.** It currently matches the write-capable role set pending **M-4**. | The security-relevant property (a `viewer` cannot approve evidence) holds regardless. Narrowing is one line. |
| R-4 | **Previously produced analysis runs keep their citation snippets.** `GET /analysis/runs/{id}` still returns `quoted_snippet` text captured while the document was verified, even after withdrawal. | Not a retrieval bypass — no new retrieval occurs and new analyses exclude the document — but withdrawal is not retroactive over stored analysis records. Belongs with the citation/audit slices. |
| R-5 | **Reprocessing after approval.** Today `begin_processing` only accepts `PENDING`, so a `PROCESSED` document's content cannot change under an existing approval. If a future slice adds reprocessing, it must reset `evidence_status`, or an approval could outlive the content it approved. | Documented here as a constraint on future work. |
| R-6 | **All historical documents are now unretrievable** until reviewed. | Intended. Operationally, someone must review the existing corpus before retrieval returns anything. |

---

## Release state

Work is complete and verified but **uncommitted, on `main`**. It has not been
committed, pushed, merged or deployed. Per the Definition of Done in
`Phase1_Recommended_Backlog.md`, it should be moved onto a feature branch
(`feat/mvp-evidence-lifecycle`) before commit and PR.
