"""Pure domain entity for a Document's *current* evidence decision.

MVP Slice 4 (Evidence Review Lifecycle). Deliberately a separate entity
rather than five more fields on ``Document``:

* ``Document`` remains the upload/processing aggregate. The
  evidence-review path never loads or mutates it, and needs none of
  ``storage_path``, ``filename`` or the rest of the upload/storage
  fields to decide an evidence question;
* the evidence columns are written by exactly one statement (the atomic
  conditional UPDATE in ``SQLAlchemyDocumentRepository``), never by the
  generic ``update()``. A separate return type makes that boundary
  visible in the type system rather than only in a docstring.

The two lifecycles stay distinct and are not merged here:

* ``processing_status`` -- the technical processing lifecycle
  (PENDING -> PROCESSING -> PROCESSED/FAILED), owned by
  ``DocumentProcessingService``;
* ``evidence_status`` -- the human evidence-review lifecycle, owned by
  ``EvidenceReviewService``.

``processing_status`` is carried on this entity for one reason only:
VERIFY has an explicit processing precondition
(``required_processing_status_for``), so the review path must be able to
*observe* that state -- to refuse an approval of an unprocessed document
with a precise error, and to tell a failed conditional write apart from
a concurrency loss. The review commands cannot mutate it: no method on
this path writes ``processing_status``, and the transition statement
only reads it as a predicate.

It is typed ``str | None`` even though ``documents.processing_status``
is ``NOT NULL``, matching ``satisfies_processing_precondition``'s own
signature: that policy accepts a missing state and *fails closed* on it,
and a type here declaring the value can never be absent would make the
fail-closed branch look unreachable and invite a later caller to drop
it. Missing or malformed persistence data must never be able to bypass
the approval precondition -- ``None`` refuses VERIFY exactly as
``"PENDING"`` does.

``evidence_status`` is the :class:`EvidenceStatus` enum, not the raw
column string: an entity that could hold an arbitrary status value would
push "is this a state we recognize?" onto every reader, and the one
reader that forgot would be a document treated as approved evidence on
the strength of an unrecognized string. The raw value is parsed once, at
the repository boundary, which fails closed on anything outside the five
canonical spellings (see ``SQLAlchemyDocumentRepository``); past that
boundary the state is known-valid by construction.

**This is current-state provenance, not history.** The four review
fields answer "what is the evidence decision now, who made it, when, and
why" -- the question Slice 4 is required to answer. They do not answer
"what were the previous decisions": each transition overwrites the
previous reviewer, timestamp and reason in place. There is no
append-only event, no hash chain, and no decision timeline here; those
belong to the later tamper-evident audit slice (Epic B / FND-SEC-03),
and this entity must not be described as providing them.

``reviewed_by``/``reviewed_at``/``review_reason`` are all ``None`` while
the document sits in the initial ``PENDING_REVIEW`` state -- no human
has decided anything yet, so fabricating a reviewer or a timestamp there
would be inventing provenance. ``superseded_by_document_id`` is set only
by a ``supersede`` command that recorded a successor, and is optional
even then (a reviewer may mark a document obsolete without a
replacement).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.evidence.lifecycle import EvidenceStatus


@dataclass(frozen=True)
class DocumentEvidence:
    """One Document's current evidence decision, as stored."""

    document_id: UUID
    engagement_id: UUID
    evidence_status: EvidenceStatus
    processing_status: str | None
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_reason: str | None
    superseded_by_document_id: UUID | None
    updated_at: datetime
