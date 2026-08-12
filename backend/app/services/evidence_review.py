"""Evidence review use case: the four explicit human decisions.

MVP Slice 4 (Evidence Review Lifecycle). Deliberately
framework-independent -- no FastAPI import anywhere in this module --
and deliberately *not* a generic status setter. The public surface is
four named commands (``verify``, ``reject``, ``restrict``,
``supersede``), one per business decision, because "set this field to
this value" is not a decision a reviewer makes and is not a decision an
API should accept: an endpoint shaped
``PATCH /documents/{id} {"evidence_status": "VERIFIED"}`` would let any
client-chosen string drive the lifecycle, including transitions the
state machine forbids.

Every command performs the same steps, in this order:

1. the caller is already authenticated and already holds
   ``Permission.EVIDENCE_REVIEW`` (the route's ``require_permission``
   dependency ran first; this service is never reached otherwise);
2. the trusted organization is resolved *server-side* from
   ``current_user`` -- it is not a parameter of any method here, so no
   caller can pass one;
3. the reason is validated server-side, whatever the client sent;
4. a named successor, if any, is resolved inside the caller's own
   organization;
5. the document is located under the same organization predicate, in
   SQL, by the repository;
6. the current state is read, and the requested transition validated
   against the state machine -- including the approval precondition on
   ``processing_status`` and, for a repeat, whether the request is
   materially the decision already recorded;
7. the reviewer identity and the review timestamp are derived
   server-side -- ``reviewed_by`` from the authenticated profile,
   ``reviewed_at`` from the database's clock inside the write itself;
8. the transition is written atomically, conditional on both the
   evidence state and the processing state observed at step 6.

**Concurrency.** Step 6's read and step 8's write are not a
transaction, and are deliberately not treated as one: two reviewers can
act between them, and so can a reprocessing request. Both observed
states travel into the ``UPDATE``'s ``WHERE`` clause, so if either
changed in between, the write matches zero rows and *nothing happens*.
This service then re-reads and answers the loser truthfully -- with the
decision that actually stands, or a 409 naming the current state --
rather than overwriting a colleague's review. See
``IDocumentRepository.transition_evidence``.

**Retry behaviour (the documented, deterministic one).** Repeating a
command is an idempotent success only when the document already holds
the target state *and* the request is materially the same decision:
same normalized reason, same successor. Then the stored decision is
returned unchanged, with its original reviewer and timestamp, and
nothing is written -- so a retried ``verify`` cannot take attribution
for someone else's approval or refresh its timestamp. A repeat carrying
a *different* reason or a different successor is a different decision,
and Slice 4 has no approved path for replacing a recorded one, so it is
a 409 that leaves the stored decision standing. Requesting a different
transition out of a state that does not permit one is likewise a 409
naming the current state -- never a silent no-op, and never a different
transition than the one asked for.

**Approval has a content precondition; withdrawal does not.** VERIFY
requires ``processing_status = 'PROCESSED'``, because approving a
document as retrievable evidence asserts something about content that
PENDING/PROCESSING/FAILED documents do not have. REJECT, RESTRICT and
SUPERSEDE carry no such precondition -- a document whose extraction
failed is exactly the kind that needs rejecting.

**Withdrawal, not reactivation.** VERIFIED evidence can be withdrawn
(to REJECTED, RESTRICTED or SUPERSEDED) because new information
appears. The reverse is refused here for every command, because Slice 4
defines no approved re-review path; see ``app.domain.evidence.lifecycle``.

**What this service does not do.** It never deletes a document, its
extracted text, its chunks, or its embeddings -- rejection and
restriction change eligibility, not existence, and the underlying work
stays available for a later re-review slice to reconsider. It writes no
audit event and keeps no decision history: the four review columns hold
the *current* decision only, and each transition overwrites the previous
one in place. That limitation is real and is recorded in the slice's
design record; it is not a gap this service quietly papers over.
"""

from uuid import UUID

from app.core.exceptions import (
    AuthorizationError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)
from app.domain.entities.document_evidence import DocumentEvidence
from app.domain.entities.user import User
from app.domain.evidence.lifecycle import (
    MAX_REVIEW_REASON_CHARS,
    EvidenceReviewCommand,
    EvidenceStatus,
    TransitionOutcome,
    accepts_successor,
    evaluate_transition,
    is_equivalent_repeat,
    required_processing_status_for,
    requires_reason,
    satisfies_processing_precondition,
    target_status_for,
)
from app.domain.repositories.document import IDocumentRepository

#: Answer for a conditional write that matched no row and whose failure
#: none of the re-read checks could account for. Deterministic, generic,
#: and deliberately free of SQL or predicate detail: the caller is told
#: what to do (reload and retry), not how the statement is shaped.
_UNEXPLAINED_CONFLICT_DETAIL = (
    "The evidence decision could not be applied because the document changed "
    "concurrently; reload the current state and retry."
)


def _conflict_message(current: EvidenceStatus, command: EvidenceReviewCommand) -> str:
    """Say what the state is and that the command does not apply to it.

    Disclosing the current state is safe and necessary: the caller has
    already been proven to own the document (the lookup was
    tenant-scoped), and a reviewer told only "conflict" cannot tell an
    already-rejected document from one a colleague just restricted."""

    return (
        f"Document evidence status is {current.value}; "
        f"a {command.value} decision is not permitted from that state."
    )


def _repeat_conflict_message(current: EvidenceStatus) -> str:
    """Explain a repeat that is not the decision already on record.

    Names no stored value -- not the recorded reason and not the
    recorded successor -- because the caller can read those with an
    ordinary document read; what they need from *this* response is that
    their differing decision was refused rather than applied."""

    return (
        f"Document evidence status is already {current.value}, recorded with a "
        "different reason or successor; the existing decision was not replaced."
    )


def _precondition_message(
    command: EvidenceReviewCommand, processing_status: str | None
) -> str:
    """Explain an approval refused because the document is not processed.

    Takes ``str | None`` because that is what the policy it reports on
    accepts: ``satisfies_processing_precondition`` fails closed on a
    missing processing state, so this message must be able to describe
    that case rather than assume it away."""

    required = required_processing_status_for(command)
    observed = processing_status if processing_status else "unknown"
    return (
        f"Document processing status is {observed}; a {command.value} decision "
        f"requires processing status {required}."
    )


class EvidenceReviewService:
    """The four evidence commands, each atomic and each tenant-scoped."""

    def __init__(self, document_repository: IDocumentRepository) -> None:
        self._document_repository = document_repository

    async def verify(
        self, document_id: UUID, current_user: User, *, reason: str | None = None
    ) -> DocumentEvidence:
        """Approve this document as evidence eligible for retrieval.

        Requires the document to be ``PROCESSED``: there is no content
        to approve before extraction and chunking have completed. The
        note is optional (see ``REASON_REQUIRED_COMMANDS``); a blank or
        whitespace-only one is stored as no note at all rather than as
        an empty string."""

        return await self._review(
            document_id, EvidenceReviewCommand.VERIFY, current_user, reason=reason
        )

    async def reject(
        self, document_id: UUID, current_user: User, *, reason: str
    ) -> DocumentEvidence:
        """Refuse this document as approved evidence. Reason required.

        Nothing is deleted: the document, its extracted text, its chunks
        and its embeddings all remain. Only retrieval eligibility
        changes, and it changes immediately."""

        return await self._review(
            document_id, EvidenceReviewCommand.REJECT, current_user, reason=reason
        )

    async def restrict(
        self, document_id: UUID, current_user: User, *, reason: str
    ) -> DocumentEvidence:
        """Exclude this document from normal retrieval. Reason required.

        For Slice 4 this means exactly "retrieval ineligible" -- it is
        not a clearance level, a classification, or a per-user
        visibility rule, and no such system is implied by it."""

        return await self._review(
            document_id, EvidenceReviewCommand.RESTRICT, current_user, reason=reason
        )

    async def supersede(
        self,
        document_id: UUID,
        current_user: User,
        *,
        reason: str,
        superseded_by_document_id: UUID | None = None,
    ) -> DocumentEvidence:
        """Mark this document obsolete. Reason required; successor optional.

        A recorded successor must exist, must belong to the caller's own
        organization, and must not be the document itself. Recording it
        does **not** approve it: the successor keeps whatever state it
        already had (typically ``PENDING_REVIEW``), so a replacement
        becomes retrievable only when a human verifies it in its own
        right."""

        return await self._review(
            document_id,
            EvidenceReviewCommand.SUPERSEDE,
            current_user,
            reason=reason,
            superseded_by_document_id=superseded_by_document_id,
        )

    def _require_user_organization(self, current_user: User) -> UUID:
        # Fail closed: a profile with no organization has no tenant scope,
        # so there is no document whose evidence it may decide. Never a
        # default or first-organization fallback.
        if current_user.organization_id is None:
            raise AuthorizationError("User has no organization")
        return current_user.organization_id

    def _normalize_reason(
        self, command: EvidenceReviewCommand, reason: str | None
    ) -> str | None:
        """Validate the reason on the server, whatever the client sent.

        The API schema rejects most bad input first, but this check is
        the authoritative one: it is the layer every caller must pass,
        including a future internal caller that never constructs a
        Pydantic model. Whitespace-only is treated as absent, so padding
        a required reason with spaces is rejected exactly as omitting
        it is -- and the stripped form is what gets stored and what
        later repeat-equivalence comparisons are made against."""

        stripped = reason.strip() if reason is not None else ""
        if not stripped:
            if requires_reason(command):
                raise ValidationError(
                    f"A review reason is required to {command.value} evidence"
                )
            return None
        if len(stripped) > MAX_REVIEW_REASON_CHARS:
            raise ValidationError(
                f"Review reason must be at most {MAX_REVIEW_REASON_CHARS} characters"
            )
        return stripped

    async def _require_successor(
        self,
        document_id: UUID,
        superseded_by_document_id: UUID,
        *,
        organization_id: UUID,
    ) -> None:
        """Prove a named successor is usable before any state changes.

        Self-supersession is checked first and answered 422: it is a
        malformed request, not a missing resource, and answering 404
        would wrongly imply the id was unknown. Existence is then
        checked tenant-scoped, so a valid UUID belonging to another
        organization produces the same 404 as one belonging to nobody --
        the successor field must not become an existence oracle for
        other tenants' documents.

        This check is for the *error message*, not for safety: the same
        ownership rule is enforced again inside the transition's own SQL
        predicate, which is what closes the window between here and the
        write."""

        if superseded_by_document_id == document_id:
            raise ValidationError("A document cannot supersede itself")
        successor = await self._document_repository.get_evidence_for_organization(
            superseded_by_document_id, organization_id=organization_id
        )
        if successor is None:
            raise NotFoundError(f"Document {superseded_by_document_id} not found")

    def _resolve_repeat(
        self,
        current: DocumentEvidence,
        command: EvidenceReviewCommand,
        *,
        review_reason: str | None,
        superseded_by_document_id: UUID | None,
    ) -> DocumentEvidence:
        """Answer a command whose target state the document already holds.

        Idempotent success only for a materially identical repeat --
        re-writing an equivalent decision would replace another
        reviewer's identity and timestamp with this caller's for no
        change in state, the precise provenance corruption a retried
        request must not cause. A repeat that differs in reason or
        successor is a *different* decision, refused with 409 so the
        caller cannot mistake "your correction was recorded" for what
        actually happened, which is nothing."""

        if is_equivalent_repeat(
            recorded_reason=current.review_reason,
            requested_reason=review_reason,
            recorded_successor=current.superseded_by_document_id,
            requested_successor=superseded_by_document_id,
        ):
            return current
        raise InvalidStateTransitionError(_repeat_conflict_message(current.evidence_status))

    async def _review(
        self,
        document_id: UUID,
        command: EvidenceReviewCommand,
        current_user: User,
        *,
        reason: str | None,
        superseded_by_document_id: UUID | None = None,
    ) -> DocumentEvidence:
        organization_id = self._require_user_organization(current_user)
        review_reason = self._normalize_reason(command, reason)

        if superseded_by_document_id is not None:
            await self._require_successor(
                document_id, superseded_by_document_id, organization_id=organization_id
            )

        current = await self._document_repository.get_evidence_for_organization(
            document_id, organization_id=organization_id
        )
        if current is None:
            raise NotFoundError(f"Document {document_id} not found")

        target = target_status_for(command)
        outcome = evaluate_transition(current.evidence_status, command)
        if outcome is TransitionOutcome.ALREADY_IN_TARGET_STATE:
            return self._resolve_repeat(
                current,
                command,
                review_reason=review_reason,
                superseded_by_document_id=superseded_by_document_id,
            )
        if outcome is TransitionOutcome.CONFLICT:
            raise InvalidStateTransitionError(
                _conflict_message(current.evidence_status, command)
            )

        if not satisfies_processing_precondition(command, current.processing_status):
            raise InvalidStateTransitionError(
                _precondition_message(command, current.processing_status)
            )

        updated = await self._document_repository.transition_evidence(
            document_id,
            organization_id=organization_id,
            expected_status=current.evidence_status,
            new_status=target,
            reviewed_by=current_user.id,
            review_reason=review_reason,
            superseded_by_document_id=superseded_by_document_id,
            required_processing_status=required_processing_status_for(command),
        )
        if updated is not None:
            return updated

        return await self._explain_lost_transition(
            document_id,
            command,
            organization_id=organization_id,
            expected_status=current.evidence_status,
            target=target,
            review_reason=review_reason,
            superseded_by_document_id=superseded_by_document_id,
        )

    async def _explain_lost_transition(
        self,
        document_id: UUID,
        command: EvidenceReviewCommand,
        *,
        organization_id: UUID,
        expected_status: EvidenceStatus,
        target: EvidenceStatus,
        review_reason: str | None,
        superseded_by_document_id: UUID | None,
    ) -> DocumentEvidence:
        """Answer a caller whose conditional write matched no row.

        The write carries five predicates (identity, tenancy, expected
        evidence state, required processing state, successor ownership)
        and reports only that they did not all hold together. This
        re-read -- itself tenant-scoped, so it cannot disclose another
        organization's row either -- decides which, and always raises or
        returns something truthful:

        * the document is gone or was never the caller's -> 404, the
          same answer an unknown UUID gets;
        * a concurrent reviewer already recorded this same decision ->
          it is returned, or refused as a differing repeat, by exactly
          the rule a first-attempt repeat gets;
        * a concurrent reviewer recorded a *different* decision -> 409
          naming the state that actually stands, never a silent
          overwrite of it;
        * the evidence state is untouched but the processing state no
          longer satisfies the command (the document began reprocessing
          in the meantime) -> 409 naming that;
        * only for a supersession that actually named a successor is the
          remaining case attributable to the successor predicate -> 404
          for that successor.

        Anything left over is unexplained, and is answered with a
        generic conflict. The alternative -- reporting a missing
        successor for a command that never had one -- would produce a
        nonsense ``Document None not found``; and the other alternatives
        (retrying unconditionally, or returning success) would each
        defeat the concurrency guarantee this method exists to
        preserve."""

        fresh = await self._document_repository.get_evidence_for_organization(
            document_id, organization_id=organization_id
        )
        if fresh is None:
            raise NotFoundError(f"Document {document_id} not found")
        if fresh.evidence_status is target:
            return self._resolve_repeat(
                fresh,
                command,
                review_reason=review_reason,
                superseded_by_document_id=superseded_by_document_id,
            )
        if fresh.evidence_status is not expected_status:
            raise InvalidStateTransitionError(
                _conflict_message(fresh.evidence_status, command)
            )
        if not satisfies_processing_precondition(command, fresh.processing_status):
            raise InvalidStateTransitionError(
                _precondition_message(command, fresh.processing_status)
            )
        if accepts_successor(command) and superseded_by_document_id is not None:
            raise NotFoundError(f"Document {superseded_by_document_id} not found")
        raise InvalidStateTransitionError(_UNEXPLAINED_CONFLICT_DETAIL)
