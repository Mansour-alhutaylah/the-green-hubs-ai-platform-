"""Evidence review lifecycle primitives.

Deliberately framework-independent (no FastAPI, no SQLAlchemy, no
Pydantic imports), mirroring ``app.domain.security``: the state machine
must stay testable in isolation and reusable by the repository SQL, the
service commands, the retrieval predicate and any later approval or
audit capability. The FastAPI binding lives in ``app.api.v1.documents``;
the persistence binding lives in
``app.infrastructure.repositories.document``.
"""

from app.domain.evidence.lifecycle import (
    ALLOWED_TRANSITIONS,
    COMMAND_TARGET_STATUS,
    INITIAL_EVIDENCE_STATUS,
    MAX_REVIEW_REASON_CHARS,
    PROCESSED_PROCESSING_STATUS,
    PROCESSING_PRECONDITION_COMMANDS,
    REASON_REQUIRED_COMMANDS,
    RETRIEVAL_ELIGIBLE_STATUSES,
    SUCCESSOR_ACCEPTING_COMMANDS,
    EvidenceReviewCommand,
    EvidenceStatus,
    TransitionOutcome,
    accepts_successor,
    evaluate_transition,
    evidence_status_values,
    is_equivalent_repeat,
    is_retrieval_eligible,
    parse_evidence_status,
    required_processing_status_for,
    requires_reason,
    retrieval_eligible_status_values,
    satisfies_processing_precondition,
    target_status_for,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "COMMAND_TARGET_STATUS",
    "INITIAL_EVIDENCE_STATUS",
    "MAX_REVIEW_REASON_CHARS",
    "PROCESSED_PROCESSING_STATUS",
    "PROCESSING_PRECONDITION_COMMANDS",
    "REASON_REQUIRED_COMMANDS",
    "RETRIEVAL_ELIGIBLE_STATUSES",
    "SUCCESSOR_ACCEPTING_COMMANDS",
    "EvidenceReviewCommand",
    "EvidenceStatus",
    "TransitionOutcome",
    "accepts_successor",
    "evaluate_transition",
    "evidence_status_values",
    "is_equivalent_repeat",
    "is_retrieval_eligible",
    "parse_evidence_status",
    "required_processing_status_for",
    "requires_reason",
    "retrieval_eligible_status_values",
    "satisfies_processing_precondition",
    "target_status_for",
]
