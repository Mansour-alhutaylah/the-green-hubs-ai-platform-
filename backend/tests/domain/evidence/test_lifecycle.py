"""The evidence state machine, exercised as pure policy.

No database, no HTTP, no service: this file pins the decisions the rest
of Slice 4 depends on, so a change to the matrix, the preconditions or
the repeat rule fails here first -- in the one place where the failure
message names the rule rather than an endpoint.

The transition table is asserted **exhaustively**: every one of the
5 x 4 (state, command) pairs has an expected outcome written out below.
A test that only checked the interesting cases would let a future edit
silently open a cell nobody thought to look at -- and the cells that
matter most (anything ending in VERIFIED) are exactly the ones an
incomplete test would miss.
"""

import uuid

import pytest

from app.domain.evidence.lifecycle import (
    ALLOWED_TRANSITIONS,
    COMMAND_TARGET_STATUS,
    INITIAL_EVIDENCE_STATUS,
    MAX_REVIEW_REASON_CHARS,
    PROCESSED_PROCESSING_STATUS,
    RETRIEVAL_ELIGIBLE_STATUSES,
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

VERIFY = EvidenceReviewCommand.VERIFY
REJECT = EvidenceReviewCommand.REJECT
RESTRICT = EvidenceReviewCommand.RESTRICT
SUPERSEDE = EvidenceReviewCommand.SUPERSEDE

PENDING = EvidenceStatus.PENDING_REVIEW
VERIFIED = EvidenceStatus.VERIFIED
REJECTED = EvidenceStatus.REJECTED
RESTRICTED = EvidenceStatus.RESTRICTED
SUPERSEDED = EvidenceStatus.SUPERSEDED

ALLOWED = TransitionOutcome.ALLOWED
REPEAT = TransitionOutcome.ALREADY_IN_TARGET_STATE
CONFLICT = TransitionOutcome.CONFLICT

#: The complete matrix, written out cell by cell. Reading down a column
#: is the interesting exercise: VERIFY is reachable from exactly one
#: state, and no state reaches it from a decided one.
FULL_MATRIX: dict[tuple[EvidenceStatus, EvidenceReviewCommand], TransitionOutcome] = {
    (PENDING, VERIFY): ALLOWED,
    (PENDING, REJECT): ALLOWED,
    (PENDING, RESTRICT): ALLOWED,
    (PENDING, SUPERSEDE): ALLOWED,
    (VERIFIED, VERIFY): REPEAT,
    (VERIFIED, REJECT): ALLOWED,
    (VERIFIED, RESTRICT): ALLOWED,
    (VERIFIED, SUPERSEDE): ALLOWED,
    (REJECTED, VERIFY): CONFLICT,
    (REJECTED, REJECT): REPEAT,
    (REJECTED, RESTRICT): CONFLICT,
    (REJECTED, SUPERSEDE): CONFLICT,
    (RESTRICTED, VERIFY): CONFLICT,
    (RESTRICTED, REJECT): CONFLICT,
    (RESTRICTED, RESTRICT): REPEAT,
    (RESTRICTED, SUPERSEDE): CONFLICT,
    (SUPERSEDED, VERIFY): CONFLICT,
    (SUPERSEDED, REJECT): CONFLICT,
    (SUPERSEDED, RESTRICT): CONFLICT,
    (SUPERSEDED, SUPERSEDE): REPEAT,
}


# ---------------------------------------------------------------------------
# The matrix
# ---------------------------------------------------------------------------


def test_the_matrix_covers_every_state_and_command_pair() -> None:
    """A missing cell would make the parametrized test below pass by
    simply not asking about it."""

    expected = {
        (status, command) for status in EvidenceStatus for command in EvidenceReviewCommand
    }

    assert set(FULL_MATRIX) == expected
    assert len(FULL_MATRIX) == 20


@pytest.mark.parametrize(("state", "command", "expected"), [
    (state, command, outcome) for (state, command), outcome in FULL_MATRIX.items()
])
def test_every_transition_matches_the_documented_matrix(
    state: EvidenceStatus, command: EvidenceReviewCommand, expected: TransitionOutcome
) -> None:
    assert evaluate_transition(state, command) is expected


@pytest.mark.parametrize("state", [REJECTED, RESTRICTED, SUPERSEDED])
def test_no_decided_state_can_be_reactivated(state: EvidenceStatus) -> None:
    """The property Slice 4 must not lose: nothing returns a withdrawn or
    refused document to the retrieval-eligible state."""

    assert evaluate_transition(state, VERIFY) is CONFLICT
    assert VERIFY not in ALLOWED_TRANSITIONS[state]


@pytest.mark.parametrize("command", [REJECT, RESTRICT, SUPERSEDE])
def test_verified_evidence_can_always_be_withdrawn(
    command: EvidenceReviewCommand,
) -> None:
    """The other half of the same property: an approval that turns out to
    be wrong is removable."""

    assert evaluate_transition(VERIFIED, command) is ALLOWED


def test_a_pending_document_can_be_superseded_without_review() -> None:
    """Both states are retrieval-ineligible, so this moves nothing into
    an approved state."""

    assert evaluate_transition(PENDING, SUPERSEDE) is ALLOWED


def test_the_initial_state_is_the_unapproved_one() -> None:
    assert INITIAL_EVIDENCE_STATUS is PENDING
    assert not is_retrieval_eligible(INITIAL_EVIDENCE_STATUS)


def test_the_policy_tables_are_immutable() -> None:
    """A mutable policy is one a compromised or careless code path can
    widen at runtime."""

    with pytest.raises(TypeError):
        ALLOWED_TRANSITIONS[REJECTED] = frozenset({VERIFY})  # type: ignore[index]
    with pytest.raises(TypeError):
        COMMAND_TARGET_STATUS[VERIFY] = REJECTED  # type: ignore[index]
    with pytest.raises(AttributeError):
        ALLOWED_TRANSITIONS[REJECTED].add(VERIFY)  # type: ignore[attr-defined]


@pytest.mark.parametrize(("command", "expected"), [
    (VERIFY, VERIFIED),
    (REJECT, REJECTED),
    (RESTRICT, RESTRICTED),
    (SUPERSEDE, SUPERSEDED),
])
def test_each_command_records_its_own_state(
    command: EvidenceReviewCommand, expected: EvidenceStatus
) -> None:
    assert target_status_for(command) is expected


# ---------------------------------------------------------------------------
# Retrieval eligibility
# ---------------------------------------------------------------------------


def test_only_verified_evidence_is_retrieval_eligible() -> None:
    assert RETRIEVAL_ELIGIBLE_STATUSES == frozenset({VERIFIED})
    assert retrieval_eligible_status_values() == ("VERIFIED",)


@pytest.mark.parametrize("state", [PENDING, REJECTED, RESTRICTED, SUPERSEDED])
def test_every_other_state_is_ineligible(state: EvidenceStatus) -> None:
    assert not is_retrieval_eligible(state)
    assert not is_retrieval_eligible(state.value)


@pytest.mark.parametrize("raw", [None, "", "verified", "VERIFIED ", "APPROVED", 7])
def test_an_unrecognized_status_is_never_eligible(raw: object) -> None:
    """Deny by default: an unparseable value must not be read as
    approved, whatever produced it."""

    assert parse_evidence_status(raw) is None  # type: ignore[arg-type]
    assert not is_retrieval_eligible(raw)  # type: ignore[arg-type]


def test_every_canonical_value_parses_back_to_its_state() -> None:
    assert evidence_status_values() == (
        "PENDING_REVIEW",
        "VERIFIED",
        "REJECTED",
        "RESTRICTED",
        "SUPERSEDED",
    )
    for status in EvidenceStatus:
        assert parse_evidence_status(status.value) is status


# ---------------------------------------------------------------------------
# Reason and successor rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", [REJECT, RESTRICT, SUPERSEDE])
def test_withdrawal_commands_require_a_reason(command: EvidenceReviewCommand) -> None:
    assert requires_reason(command)


def test_verify_does_not_require_a_reason() -> None:
    assert not requires_reason(VERIFY)


def test_only_supersede_accepts_a_successor() -> None:
    assert accepts_successor(SUPERSEDE)
    for command in (VERIFY, REJECT, RESTRICT):
        assert not accepts_successor(command)


def test_the_reason_bound_is_explicit() -> None:
    assert MAX_REVIEW_REASON_CHARS == 1000


# ---------------------------------------------------------------------------
# The processing precondition
# ---------------------------------------------------------------------------


def test_only_verify_carries_a_processing_precondition() -> None:
    assert required_processing_status_for(VERIFY) == PROCESSED_PROCESSING_STATUS
    for command in (REJECT, RESTRICT, SUPERSEDE):
        assert required_processing_status_for(command) is None


@pytest.mark.parametrize("processing_status", ["PENDING", "PROCESSING", "FAILED", None, ""])
def test_verify_is_refused_unless_the_document_is_processed(
    processing_status: str | None,
) -> None:
    """Including ``None`` and ``""``: a missing processing state fails
    closed rather than being waved through."""

    assert not satisfies_processing_precondition(VERIFY, processing_status)


def test_verify_is_permitted_on_a_processed_document() -> None:
    assert satisfies_processing_precondition(VERIFY, "PROCESSED")


@pytest.mark.parametrize("command", [REJECT, RESTRICT, SUPERSEDE])
@pytest.mark.parametrize(
    "processing_status", ["PENDING", "PROCESSING", "FAILED", "PROCESSED", None]
)
def test_withdrawal_is_permitted_in_every_processing_state(
    command: EvidenceReviewCommand, processing_status: str | None
) -> None:
    """A document whose extraction failed is exactly the one that needs
    rejecting; a precondition here would strand it in PENDING_REVIEW."""

    assert satisfies_processing_precondition(command, processing_status)


# ---------------------------------------------------------------------------
# Repeat equivalence
# ---------------------------------------------------------------------------


def test_an_identical_repeat_is_equivalent() -> None:
    successor = uuid.uuid4()

    assert is_equivalent_repeat(
        recorded_reason="superseded by the FY25 restatement",
        requested_reason="superseded by the FY25 restatement",
        recorded_successor=successor,
        requested_successor=successor,
    )


def test_a_repeat_with_no_reason_and_no_successor_is_equivalent() -> None:
    assert is_equivalent_repeat(
        recorded_reason=None,
        requested_reason=None,
        recorded_successor=None,
        requested_successor=None,
    )


def test_a_repeat_naming_a_different_successor_is_not_equivalent() -> None:
    """The case that makes this rule necessary: answering 200 here would
    report a correction as recorded while the stored successor is still
    the first one."""

    assert not is_equivalent_repeat(
        recorded_reason="obsolete",
        requested_reason="obsolete",
        recorded_successor=uuid.uuid4(),
        requested_successor=uuid.uuid4(),
    )


def test_a_repeat_dropping_the_successor_is_not_equivalent() -> None:
    assert not is_equivalent_repeat(
        recorded_reason="obsolete",
        requested_reason="obsolete",
        recorded_successor=uuid.uuid4(),
        requested_successor=None,
    )


def test_a_repeat_adding_a_successor_is_not_equivalent() -> None:
    assert not is_equivalent_repeat(
        recorded_reason="obsolete",
        requested_reason="obsolete",
        recorded_successor=None,
        requested_successor=uuid.uuid4(),
    )


def test_a_repeat_with_a_different_reason_is_not_equivalent() -> None:
    assert not is_equivalent_repeat(
        recorded_reason="wrong reporting period",
        requested_reason="unverifiable emissions factor",
        recorded_successor=None,
        requested_successor=None,
    )
