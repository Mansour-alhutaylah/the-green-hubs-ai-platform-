"""``EvidenceReviewService`` against an in-memory repository.

The fake below is not a stub that returns whatever the test wants: it
reimplements the repository's *contract* -- tenant scoping, and the
conditional transition that matches nothing unless the expected
evidence state, the required processing state and the successor's
ownership all still hold. That is what lets these tests exercise the
concurrency and precondition branches deterministically, without a
database. The same behaviours are then proved again against real
PostgreSQL in ``tests/api/test_document_evidence_integration.py``;
neither file is a substitute for the other.

``transition_calls`` and the ``on_transition`` hook are the two levers
the concurrency tests use: the hook runs *between* the service's read
and its conditional write, which is exactly the window a second
reviewer acts in.
"""

import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Callable, Sequence

import pytest

from app.core.exceptions import (
    AuthorizationError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)
from app.domain.entities.document_evidence import DocumentEvidence
from app.domain.entities.user import User
from app.domain.evidence.lifecycle import MAX_REVIEW_REASON_CHARS, EvidenceStatus
from app.domain.repositories.document import IDocumentRepository
from app.services.evidence_review import EvidenceReviewService

ORGANIZATION_A = uuid.uuid4()
ORGANIZATION_B = uuid.uuid4()


def _evidence(
    *,
    document_id: uuid.UUID | None = None,
    evidence_status: EvidenceStatus = EvidenceStatus.PENDING_REVIEW,
    # `str | None`, matching DocumentEvidence: the absent-processing-state
    # case is a real one the approval precondition must fail closed on,
    # so tests must be able to express it without a type escape hatch.
    processing_status: str | None = "PROCESSED",
    reviewed_by: uuid.UUID | None = None,
    reviewed_at: datetime | None = None,
    review_reason: str | None = None,
    superseded_by_document_id: uuid.UUID | None = None,
) -> DocumentEvidence:
    return DocumentEvidence(
        document_id=document_id or uuid.uuid4(),
        engagement_id=uuid.uuid4(),
        evidence_status=evidence_status,
        processing_status=processing_status,
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
        review_reason=review_reason,
        superseded_by_document_id=superseded_by_document_id,
        updated_at=datetime.now(timezone.utc),
    )


class FakeDocumentRepository(IDocumentRepository):
    """Implements the two evidence methods faithfully; nothing else."""

    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, tuple[DocumentEvidence, uuid.UUID]] = {}
        self.transition_calls: list[dict] = []
        self.get_evidence_calls: list[dict] = []
        #: Runs before each conditional write, standing in for whatever a
        #: concurrent reviewer (or a reprocessing request) did in the
        #: window between the service's read and its write.
        self.on_transition: Callable[[], None] | None = None

    def seed(
        self, evidence: DocumentEvidence, *, organization_id: uuid.UUID = ORGANIZATION_A
    ) -> DocumentEvidence:
        self.rows[evidence.document_id] = (evidence, organization_id)
        return evidence

    def stored(self, document_id: uuid.UUID) -> DocumentEvidence:
        return self.rows[document_id][0]

    def _owned(
        self, document_id: uuid.UUID, organization_id: uuid.UUID
    ) -> DocumentEvidence | None:
        entry = self.rows.get(document_id)
        if entry is None:
            return None
        evidence, owner_organization_id = entry
        # The tenant predicate is part of the lookup, so a foreign id is
        # indistinguishable from an unknown one -- as in the real SQL.
        if owner_organization_id != organization_id:
            return None
        return evidence

    async def get_evidence_for_organization(
        self, document_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> DocumentEvidence | None:
        self.get_evidence_calls.append(
            {"document_id": document_id, "organization_id": organization_id}
        )
        return self._owned(document_id, organization_id)

    async def transition_evidence(
        self,
        document_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        expected_status: EvidenceStatus,
        new_status: EvidenceStatus,
        reviewed_by: uuid.UUID,
        review_reason: str | None,
        superseded_by_document_id: uuid.UUID | None,
        required_processing_status: str | None,
    ) -> DocumentEvidence | None:
        self.transition_calls.append(
            {
                "document_id": document_id,
                "organization_id": organization_id,
                "expected_status": expected_status,
                "new_status": new_status,
                "reviewed_by": reviewed_by,
                "review_reason": review_reason,
                "superseded_by_document_id": superseded_by_document_id,
                "required_processing_status": required_processing_status,
            }
        )
        if self.on_transition is not None:
            hook, self.on_transition = self.on_transition, None
            hook()

        # Every predicate the real statement carries, in the same order.
        current = self._owned(document_id, organization_id)
        if current is None:
            return None
        if current.evidence_status is not expected_status:
            return None
        if (
            required_processing_status is not None
            and current.processing_status != required_processing_status
        ):
            return None
        if superseded_by_document_id is not None:
            successor = self._owned(superseded_by_document_id, organization_id)
            if successor is None or superseded_by_document_id == document_id:
                return None

        updated = replace(
            current,
            evidence_status=new_status,
            reviewed_by=reviewed_by,
            reviewed_at=datetime.now(timezone.utc),
            review_reason=review_reason,
            superseded_by_document_id=superseded_by_document_id,
            updated_at=datetime.now(timezone.utc),
        )
        self.rows[document_id] = (updated, organization_id)
        return updated

    # -- Unused by EvidenceReviewService; kept only to satisfy the ABC. --
    async def get_for_organization(self, document_id, *, organization_id):
        raise NotImplementedError

    async def get_by_engagement(self, engagement_id, *, organization_id):
        raise NotImplementedError

    async def update_status(self, document_id, status, *, organization_id):
        raise NotImplementedError

    async def begin_processing(self, document_id, *, organization_id):
        raise NotImplementedError

    async def complete_processing(self, document_id, *, organization_id):
        raise NotImplementedError

    async def get_read_model_for_organization(self, document_id, **kwargs):
        raise NotImplementedError

    async def list_read_models_for_organization(self, **kwargs) -> Sequence:
        raise NotImplementedError

    async def count_for_organization(self, **kwargs) -> int:
        raise NotImplementedError

    async def create(self, entity):
        raise NotImplementedError

    async def update(self, entity):
        raise NotImplementedError

    async def delete(self, entity):
        raise NotImplementedError


def _user(
    *, organization_id: uuid.UUID | None = ORGANIZATION_A, user_id: uuid.UUID | None = None
) -> User:
    return User(
        id=user_id or uuid.uuid4(),
        organization_id=organization_id,
        full_name="Reviewer",
        email=f"reviewer-{uuid.uuid4()}@example.com",
        role="approver",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def repository() -> FakeDocumentRepository:
    return FakeDocumentRepository()


@pytest.fixture
def service(repository: FakeDocumentRepository) -> EvidenceReviewService:
    return EvidenceReviewService(repository)


@pytest.fixture
def reviewer() -> User:
    return _user()


# ---------------------------------------------------------------------------
# Tenant scope and server-derived provenance
# ---------------------------------------------------------------------------


async def test_a_user_without_an_organization_is_refused(
    service: EvidenceReviewService, repository: FakeDocumentRepository
) -> None:
    document = repository.seed(_evidence())

    with pytest.raises(AuthorizationError):
        await service.verify(document.document_id, _user(organization_id=None))

    assert repository.transition_calls == []


async def test_another_organizations_document_is_not_found(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    """A real, valid foreign UUID must behave exactly like an unknown
    one -- no 403, which would confirm the document exists."""

    document = repository.seed(_evidence(), organization_id=ORGANIZATION_B)

    with pytest.raises(NotFoundError):
        await service.verify(document.document_id, reviewer)

    assert repository.transition_calls == []
    assert repository.stored(document.document_id).evidence_status is EvidenceStatus.PENDING_REVIEW


async def test_reviewer_identity_comes_from_the_authenticated_profile(
    service: EvidenceReviewService, repository: FakeDocumentRepository
) -> None:
    reviewer = _user()
    document = repository.seed(_evidence())

    result = await service.verify(document.document_id, reviewer)

    assert result.reviewed_by == reviewer.id
    assert repository.transition_calls[0]["reviewed_by"] == reviewer.id
    assert repository.transition_calls[0]["organization_id"] == ORGANIZATION_A


async def test_the_transition_carries_the_observed_state_as_its_predicate(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    """The concurrency guarantee, asserted at the call boundary: the
    write is conditional on the state the service actually read."""

    document = repository.seed(_evidence(evidence_status=EvidenceStatus.VERIFIED))

    await service.reject(document.document_id, reviewer, reason="restated figures")

    call = repository.transition_calls[0]
    assert call["expected_status"] is EvidenceStatus.VERIFIED
    assert call["new_status"] is EvidenceStatus.REJECTED


# ---------------------------------------------------------------------------
# The four commands
# ---------------------------------------------------------------------------


async def test_verify_approves_a_processed_document(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence())

    result = await service.verify(document.document_id, reviewer, reason="checked totals")

    assert result.evidence_status is EvidenceStatus.VERIFIED
    assert result.review_reason == "checked totals"
    assert result.reviewed_at is not None


async def test_verify_without_a_note_is_accepted(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence())

    result = await service.verify(document.document_id, reviewer)

    assert result.evidence_status is EvidenceStatus.VERIFIED
    assert result.review_reason is None


@pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
async def test_a_blank_verify_note_is_stored_as_no_note(
    service: EvidenceReviewService,
    repository: FakeDocumentRepository,
    reviewer: User,
    blank: str,
) -> None:
    document = repository.seed(_evidence())

    result = await service.verify(document.document_id, reviewer, reason=blank)

    assert result.review_reason is None


async def test_reject_records_the_reason(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence(evidence_status=EvidenceStatus.VERIFIED))

    result = await service.reject(document.document_id, reviewer, reason="unverifiable factor")

    assert result.evidence_status is EvidenceStatus.REJECTED
    assert result.review_reason == "unverifiable factor"


async def test_restrict_records_the_reason(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence())

    result = await service.restrict(document.document_id, reviewer, reason="client confidential")

    assert result.evidence_status is EvidenceStatus.RESTRICTED
    assert result.review_reason == "client confidential"


async def test_supersede_records_the_reason_without_a_successor(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence())

    result = await service.supersede(document.document_id, reviewer, reason="obsolete")

    assert result.evidence_status is EvidenceStatus.SUPERSEDED
    assert result.superseded_by_document_id is None


async def test_the_reason_is_stripped_before_storage(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence())

    result = await service.reject(document.document_id, reviewer, reason="   wrong period   ")

    assert result.review_reason == "wrong period"


# ---------------------------------------------------------------------------
# Reason validation (server-side)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command_name", ["reject", "restrict", "supersede"])
@pytest.mark.parametrize("reason", [None, "", "   ", "\t\n"])
async def test_a_missing_or_blank_required_reason_is_rejected(
    service: EvidenceReviewService,
    repository: FakeDocumentRepository,
    reviewer: User,
    command_name: str,
    reason: str | None,
) -> None:
    document = repository.seed(_evidence())
    command = getattr(service, command_name)

    with pytest.raises(ValidationError):
        await command(document.document_id, reviewer, reason=reason)

    assert repository.transition_calls == []
    assert repository.stored(document.document_id).evidence_status is EvidenceStatus.PENDING_REVIEW


async def test_an_over_long_reason_is_rejected(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence())

    with pytest.raises(ValidationError):
        await service.reject(
            document.document_id, reviewer, reason="x" * (MAX_REVIEW_REASON_CHARS + 1)
        )

    assert repository.transition_calls == []


async def test_a_reason_at_the_bound_is_accepted(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence())

    result = await service.reject(
        document.document_id, reviewer, reason="x" * MAX_REVIEW_REASON_CHARS
    )

    assert result.evidence_status is EvidenceStatus.REJECTED


# ---------------------------------------------------------------------------
# The processing precondition
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("processing_status", ["PENDING", "PROCESSING", "FAILED", None])
async def test_verify_is_refused_unless_the_document_is_processed(
    service: EvidenceReviewService,
    repository: FakeDocumentRepository,
    reviewer: User,
    processing_status: str | None,
) -> None:
    """Including the ``None`` case: an absent processing state fails
    closed, and the message never renders it as an empty string."""

    document = repository.seed(_evidence(processing_status=processing_status))

    with pytest.raises(InvalidStateTransitionError) as excinfo:
        await service.verify(document.document_id, reviewer)

    assert "PROCESSED" in str(excinfo.value)
    assert repository.transition_calls == []
    assert repository.stored(document.document_id).evidence_status is EvidenceStatus.PENDING_REVIEW


async def test_the_precondition_message_never_renders_a_missing_state_as_blank(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence(processing_status=None))

    with pytest.raises(InvalidStateTransitionError) as excinfo:
        await service.verify(document.document_id, reviewer)

    assert "status is unknown" in str(excinfo.value)
    assert "status is None" not in str(excinfo.value)


async def test_verify_is_allowed_on_a_processed_document(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence(processing_status="PROCESSED"))

    result = await service.verify(document.document_id, reviewer)

    assert result.evidence_status is EvidenceStatus.VERIFIED
    assert repository.transition_calls[0]["required_processing_status"] == "PROCESSED"


@pytest.mark.parametrize("command_name", ["reject", "restrict", "supersede"])
@pytest.mark.parametrize("processing_status", ["PENDING", "PROCESSING", "FAILED"])
async def test_withdrawal_never_requires_a_processed_document(
    service: EvidenceReviewService,
    repository: FakeDocumentRepository,
    reviewer: User,
    command_name: str,
    processing_status: str,
) -> None:
    """A document whose extraction failed must still be refusable, or it
    is stranded in PENDING_REVIEW forever."""

    document = repository.seed(_evidence(processing_status=processing_status))
    command = getattr(service, command_name)

    result = await command(document.document_id, reviewer, reason="not usable")

    assert result.evidence_status is not EvidenceStatus.PENDING_REVIEW
    assert repository.transition_calls[0]["required_processing_status"] is None


async def test_a_document_that_starts_reprocessing_mid_review_is_refused(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    """The precondition lives in the write's predicate, not only in the
    earlier check, so this window is closed rather than narrow."""

    document = repository.seed(_evidence(processing_status="PROCESSED"))

    def reprocess() -> None:
        current, owner = repository.rows[document.document_id]
        repository.rows[document.document_id] = (
            replace(current, processing_status="PROCESSING"),
            owner,
        )

    repository.on_transition = reprocess

    with pytest.raises(InvalidStateTransitionError) as excinfo:
        await service.verify(document.document_id, reviewer)

    assert "PROCESSING" in str(excinfo.value)
    assert repository.stored(document.document_id).evidence_status is EvidenceStatus.PENDING_REVIEW


# ---------------------------------------------------------------------------
# Refused transitions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "state", [EvidenceStatus.REJECTED, EvidenceStatus.RESTRICTED, EvidenceStatus.SUPERSEDED]
)
async def test_a_decided_document_cannot_be_reactivated(
    service: EvidenceReviewService,
    repository: FakeDocumentRepository,
    reviewer: User,
    state: EvidenceStatus,
) -> None:
    """There is no client-reachable path back to VERIFIED, and the
    attempt writes nothing."""

    document = repository.seed(
        _evidence(
            evidence_status=state,
            reviewed_by=uuid.uuid4(),
            reviewed_at=datetime.now(timezone.utc),
            review_reason="original decision",
        )
    )

    with pytest.raises(InvalidStateTransitionError) as excinfo:
        await service.verify(document.document_id, reviewer)

    assert state.value in str(excinfo.value)
    assert repository.transition_calls == []
    stored = repository.stored(document.document_id)
    assert stored.evidence_status is state
    assert stored.review_reason == "original decision"


async def test_a_rejected_document_cannot_be_restricted(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(
        _evidence(
            evidence_status=EvidenceStatus.REJECTED,
            reviewed_by=uuid.uuid4(),
            reviewed_at=datetime.now(timezone.utc),
            review_reason="refused",
        )
    )

    with pytest.raises(InvalidStateTransitionError):
        await service.restrict(document.document_id, reviewer, reason="second thoughts")

    assert repository.stored(document.document_id).review_reason == "refused"


# ---------------------------------------------------------------------------
# Duplicate command / retry behaviour
# ---------------------------------------------------------------------------


async def test_a_duplicate_verify_returns_the_original_decision_unchanged(
    service: EvidenceReviewService, repository: FakeDocumentRepository
) -> None:
    """The documented retry behaviour, and the provenance property that
    makes it safe: the second caller does not become the reviewer."""

    first_reviewer = _user()
    second_reviewer = _user()
    document = repository.seed(_evidence())

    first = await service.verify(document.document_id, first_reviewer)
    repository.transition_calls.clear()
    second = await service.verify(document.document_id, second_reviewer)

    assert second == first
    assert second.reviewed_by == first_reviewer.id
    assert second.reviewed_at == first.reviewed_at
    assert repository.transition_calls == []


async def test_a_duplicate_reject_with_the_same_reason_is_idempotent(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence())

    first = await service.reject(document.document_id, reviewer, reason="wrong period")
    second = await service.reject(document.document_id, reviewer, reason="  wrong period  ")

    assert second == first


async def test_a_repeated_reject_with_a_different_reason_conflicts(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence())
    await service.reject(document.document_id, reviewer, reason="wrong period")
    repository.transition_calls.clear()

    with pytest.raises(InvalidStateTransitionError):
        await service.reject(document.document_id, reviewer, reason="unverifiable factor")

    assert repository.transition_calls == []
    assert repository.stored(document.document_id).review_reason == "wrong period"


async def test_a_repeated_supersede_naming_a_different_successor_conflicts(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    """The case that makes same-state-alone insufficient: a cheerful 200
    here would report the correction as recorded while the stored
    successor is still the first one."""

    document = repository.seed(_evidence())
    first_successor = repository.seed(_evidence())
    second_successor = repository.seed(_evidence())

    await service.supersede(
        document.document_id,
        reviewer,
        reason="replaced",
        superseded_by_document_id=first_successor.document_id,
    )
    repository.transition_calls.clear()

    with pytest.raises(InvalidStateTransitionError):
        await service.supersede(
            document.document_id,
            reviewer,
            reason="replaced",
            superseded_by_document_id=second_successor.document_id,
        )

    assert repository.transition_calls == []
    assert (
        repository.stored(document.document_id).superseded_by_document_id
        == first_successor.document_id
    )


async def test_a_repeated_supersede_dropping_the_successor_conflicts(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence())
    successor = repository.seed(_evidence())
    await service.supersede(
        document.document_id,
        reviewer,
        reason="replaced",
        superseded_by_document_id=successor.document_id,
    )

    with pytest.raises(InvalidStateTransitionError):
        await service.supersede(document.document_id, reviewer, reason="replaced")

    assert (
        repository.stored(document.document_id).superseded_by_document_id
        == successor.document_id
    )


async def test_an_identical_repeated_supersede_is_idempotent(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence())
    successor = repository.seed(_evidence())

    first = await service.supersede(
        document.document_id,
        reviewer,
        reason="replaced",
        superseded_by_document_id=successor.document_id,
    )
    second = await service.supersede(
        document.document_id,
        reviewer,
        reason="replaced",
        superseded_by_document_id=successor.document_id,
    )

    assert second == first


# ---------------------------------------------------------------------------
# Supersession successor rules
# ---------------------------------------------------------------------------


async def test_a_document_cannot_supersede_itself(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence())

    with pytest.raises(ValidationError):
        await service.supersede(
            document.document_id,
            reviewer,
            reason="replaced",
            superseded_by_document_id=document.document_id,
        )

    assert repository.transition_calls == []


async def test_an_unknown_successor_is_not_found(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence())

    with pytest.raises(NotFoundError):
        await service.supersede(
            document.document_id,
            reviewer,
            reason="replaced",
            superseded_by_document_id=uuid.uuid4(),
        )

    assert repository.transition_calls == []


async def test_a_cross_tenant_successor_is_not_found(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    """A real, valid UUID from another organization must not become an
    existence oracle -- same 404 as a made-up one."""

    document = repository.seed(_evidence())
    foreign = repository.seed(_evidence(), organization_id=ORGANIZATION_B)

    with pytest.raises(NotFoundError):
        await service.supersede(
            document.document_id,
            reviewer,
            reason="replaced",
            superseded_by_document_id=foreign.document_id,
        )

    assert repository.transition_calls == []
    assert repository.stored(document.document_id).evidence_status is EvidenceStatus.PENDING_REVIEW


async def test_recording_a_successor_does_not_verify_it(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    """V4 -> SUPERSEDED must leave V5 exactly as it was; only an explicit
    human decision makes the replacement retrievable."""

    old = repository.seed(_evidence())
    successor = repository.seed(_evidence())

    await service.supersede(
        old.document_id,
        reviewer,
        reason="replaced by FY25 restatement",
        superseded_by_document_id=successor.document_id,
    )

    stored_successor = repository.stored(successor.document_id)
    assert stored_successor.evidence_status is EvidenceStatus.PENDING_REVIEW
    assert stored_successor.reviewed_by is None
    assert stored_successor.reviewed_at is None


async def test_a_successor_deleted_between_the_check_and_the_write_is_not_found(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    """The write's own successor predicate is what catches this; the
    earlier check had already passed."""

    document = repository.seed(_evidence())
    successor = repository.seed(_evidence())

    repository.on_transition = lambda: repository.rows.pop(successor.document_id)

    with pytest.raises(NotFoundError) as excinfo:
        await service.supersede(
            document.document_id,
            reviewer,
            reason="replaced",
            superseded_by_document_id=successor.document_id,
        )

    assert str(successor.document_id) in str(excinfo.value)
    assert repository.stored(document.document_id).evidence_status is EvidenceStatus.PENDING_REVIEW


# ---------------------------------------------------------------------------
# Concurrency: the loser of a race never overwrites the winner
# ---------------------------------------------------------------------------


async def test_a_stale_decision_cannot_overwrite_a_newer_one(
    service: EvidenceReviewService, repository: FakeDocumentRepository
) -> None:
    """Reviewer A and Reviewer B both read PENDING_REVIEW. A rejects; B's
    verify must not silently replace A's decision."""

    reviewer_a = _user()
    reviewer_b = _user()
    document = repository.seed(_evidence())

    def reviewer_a_rejects() -> None:
        current, owner = repository.rows[document.document_id]
        repository.rows[document.document_id] = (
            replace(
                current,
                evidence_status=EvidenceStatus.REJECTED,
                reviewed_by=reviewer_a.id,
                reviewed_at=datetime.now(timezone.utc),
                review_reason="unverifiable factor",
            ),
            owner,
        )

    repository.on_transition = reviewer_a_rejects

    with pytest.raises(InvalidStateTransitionError) as excinfo:
        await service.verify(document.document_id, reviewer_b)

    assert "REJECTED" in str(excinfo.value)
    stored = repository.stored(document.document_id)
    assert stored.evidence_status is EvidenceStatus.REJECTED
    assert stored.reviewed_by == reviewer_a.id
    assert stored.review_reason == "unverifiable factor"


async def test_losing_a_race_to_the_same_decision_returns_the_winners_record(
    service: EvidenceReviewService, repository: FakeDocumentRepository
) -> None:
    """Two reviewers issue the *same* command; the loser is answered with
    the decision that stands, not with its own attribution."""

    winner = _user()
    loser = _user()
    document = repository.seed(_evidence())
    winning_time = datetime.now(timezone.utc) - timedelta(seconds=5)

    def winner_verifies() -> None:
        current, owner = repository.rows[document.document_id]
        repository.rows[document.document_id] = (
            replace(
                current,
                evidence_status=EvidenceStatus.VERIFIED,
                reviewed_by=winner.id,
                reviewed_at=winning_time,
                review_reason=None,
            ),
            owner,
        )

    repository.on_transition = winner_verifies

    result = await service.verify(document.document_id, loser)

    assert result.reviewed_by == winner.id
    assert result.reviewed_at == winning_time


async def test_losing_a_race_to_a_materially_different_decision_conflicts(
    service: EvidenceReviewService, repository: FakeDocumentRepository
) -> None:
    """Same target state, different recorded reason: the loser is told,
    not handed a success that hides whose reason was stored."""

    winner = _user()
    loser = _user()
    document = repository.seed(_evidence())

    def winner_rejects() -> None:
        current, owner = repository.rows[document.document_id]
        repository.rows[document.document_id] = (
            replace(
                current,
                evidence_status=EvidenceStatus.REJECTED,
                reviewed_by=winner.id,
                reviewed_at=datetime.now(timezone.utc),
                review_reason="winner's reason",
            ),
            owner,
        )

    repository.on_transition = winner_rejects

    with pytest.raises(InvalidStateTransitionError):
        await service.reject(document.document_id, loser, reason="loser's reason")

    assert repository.stored(document.document_id).review_reason == "winner's reason"


async def test_a_document_deleted_mid_review_is_not_found(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    document = repository.seed(_evidence())
    repository.on_transition = lambda: repository.rows.pop(document.document_id)

    with pytest.raises(NotFoundError):
        await service.verify(document.document_id, reviewer)


@pytest.mark.parametrize("command_name", ["verify", "reject", "restrict"])
async def test_an_unexplained_zero_row_write_is_a_conflict_not_a_missing_successor(
    service: EvidenceReviewService,
    repository: FakeDocumentRepository,
    reviewer: User,
    command_name: str,
) -> None:
    """None of these commands has a successor, so the fallback must never
    report one: ``Document None not found`` would be both false and
    nonsense. The answer is a deterministic conflict telling the caller
    to reload -- never a success, and never an unconditional retry."""

    document = repository.seed(_evidence())

    async def refuse_every_write(*args: object, **kwargs: object) -> None:
        return None

    repository.transition_evidence = refuse_every_write  # type: ignore[method-assign]
    command = getattr(service, command_name)
    kwargs = {} if command_name == "verify" else {"reason": "a reason"}

    with pytest.raises(InvalidStateTransitionError) as excinfo:
        await command(document.document_id, reviewer, **kwargs)

    message = str(excinfo.value)
    assert "None not found" not in message
    assert "changed concurrently" in message
    assert repository.stored(document.document_id).evidence_status is EvidenceStatus.PENDING_REVIEW


async def test_an_unexplained_zero_row_supersede_without_a_successor_is_a_conflict(
    service: EvidenceReviewService, repository: FakeDocumentRepository, reviewer: User
) -> None:
    """SUPERSEDE *may* carry a successor, but this request did not -- so
    the successor branch must not be taken here either."""

    document = repository.seed(_evidence())

    async def refuse_every_write(*args: object, **kwargs: object) -> None:
        return None

    repository.transition_evidence = refuse_every_write  # type: ignore[method-assign]

    with pytest.raises(InvalidStateTransitionError) as excinfo:
        await service.supersede(document.document_id, reviewer, reason="obsolete")

    assert "None not found" not in str(excinfo.value)
    assert "changed concurrently" in str(excinfo.value)
