"""The explicit evidence-review state machine.

MVP Slice 4 (Evidence Review Lifecycle), closing FND-KC-05's state half.
This module is the single source of truth for *which* evidence decisions
exist, which ones may follow which, what each one requires, and which
state makes a document eligible for normal retrieval. Everything else --
the repository SQL, the service commands, the API routes, the retrieval
predicate -- reads its policy from here rather than restating it, so a
change to the matrix is one edit in one file.

**The states are not a sequence.** They are five distinct business
outcomes, and modelling them as a linear pipeline (the mistake this
module exists to prevent) would imply, for example, that a document must
be VERIFIED before it can be REJECTED, or that SUPERSEDED is "later"
than RESTRICTED. It is not:

* ``PENDING_REVIEW`` -- the safe, not-approved initial state. Every
  document lands here on upload (``documents.evidence_status``'s column
  default), and nothing but an explicit human decision moves it.
* ``VERIFIED`` -- an authorized human reviewer has explicitly approved
  this document as evidence eligible for normal retrieval. This is the
  *only* retrieval-eligible state (:data:`RETRIEVAL_ELIGIBLE_STATUSES`).
* ``REJECTED`` -- must not be used as approved evidence. Reason required.
* ``RESTRICTED`` -- the document exists but is deliberately excluded from
  normal MVP retrieval. Reason required. This is *not* a clearance or
  classification system: for Slice 4 it means exactly "retrieval
  ineligible", nothing more.
* ``SUPERSEDED`` -- no longer the current evidence source, because a
  replacement exists or the reviewer marked it obsolete. Reason
  required; a successor document may optionally be recorded.

Transition matrix (:data:`ALLOWED_TRANSITIONS`), stated in full:

===============  ======  ======  ========  =========
from \\ command   VERIFY  REJECT  RESTRICT  SUPERSEDE
===============  ======  ======  ========  =========
PENDING_REVIEW   yes*    yes     yes       yes
VERIFIED         --      yes     yes       yes
REJECTED         no      --      no        no
RESTRICTED       no      no      --        no
SUPERSEDED       no      no      no        --
===============  ======  ======  ========  =========

``--`` marks a command whose target state the document already occupies;
those are decided by :func:`is_equivalent_repeat`, not by this table.
``no`` is a real refusal. ``*`` marks the one cell with an additional
precondition -- see "the processing precondition" below.

Three properties are deliberate and worth stating outright.

**Withdrawal is supported; reactivation is not.** A VERIFIED document
can be withdrawn later -- to REJECTED, RESTRICTED or SUPERSEDED -- when
new information appears, because evidence that turns out to be wrong
must be removable from retrieval. The reverse (REJECTED/RESTRICTED/
SUPERSEDED back to VERIFIED) is refused: Slice 4 defines no approved
re-review command, and silently allowing a second ``verify`` call to
undo a rejection would make the rejection decorative. If the product
later needs reconsideration, that is a new, explicit, separately
authorized command -- not a widening of this table.

**SUPERSEDE from PENDING_REVIEW is allowed.** A document can be made
obsolete by a newer upload before anyone reviews it, and both states are
retrieval-ineligible, so this moves nothing into an approved state. It
is a genuine business outcome, not a bypass.

**Terminal states are terminal for every command**, not only for VERIFY.
A REJECTED document cannot be RESTRICTED, a RESTRICTED one cannot be
REJECTED, and neither can be SUPERSEDED. All three are already
retrieval-ineligible, so nothing unsafe is being preserved; what is
being preserved is the recorded decision, which Slice 4 has no approved
mechanism to replace.

Two further rules sit alongside the matrix, because a
(from-state, command) pair is not on its own enough to decide a case.

**The processing precondition** (:func:`required_processing_status_for`).
The evidence lifecycle and the technical processing lifecycle
(``documents.processing_status``) are otherwise orthogonal -- a document
whose extraction failed can and should be rejectable, restrictable and
supersedable, and refusing those would strand it in PENDING_REVIEW
forever. VERIFY is the exception: approving a document as *retrievable
evidence* asserts something about content that does not exist until
extraction and chunking have completed, and a PENDING/PROCESSING/FAILED
document has no such content. So VERIFY requires
``processing_status = 'PROCESSED'`` and every other command requires
nothing. Note which direction this runs -- it constrains approval only,
never withdrawal.

**Repeat equivalence** (:func:`is_equivalent_repeat`). "The document is
already in the target state" is not by itself an idempotent retry. A
second ``supersede`` naming a *different* successor, or any repeat
carrying a different reason, is a different decision wearing the same
command name -- and since a recorded decision has no approved
replacement path in Slice 4, it is a conflict, not a success. Only a
materially identical repeat (same normalized reason, same successor) is
answered as the retry it is. The comparison is exact, which is what
makes it deterministic: a genuine client retry re-sends the same body
and matches; anything else is a new decision and is refused rather than
silently ignored.

This module is pure, deterministic, framework-independent policy: no
database, no network, no LLM, no request-supplied value reaches any
decision here.
"""

from enum import Enum
from types import MappingProxyType
from typing import Final, Mapping
from uuid import UUID


class EvidenceStatus(str, Enum):
    """The five distinct evidence states. Unknown values are never coerced.

    ``str``-valued to match ``Permission``/``Role``'s established shape,
    so the stored column value and the enum member share one spelling and
    FastAPI can use the enum directly as a query-parameter type.
    """

    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    RESTRICTED = "RESTRICTED"
    SUPERSEDED = "SUPERSEDED"


class EvidenceReviewCommand(str, Enum):
    """The four explicit review commands.

    Deliberately distinct from :class:`EvidenceStatus`: a command is a
    human decision being *made*, a status is the decision already
    recorded. Keeping them separate is what lets ``VERIFY`` be refused
    while ``VERIFIED`` remains a legitimate current state.
    """

    VERIFY = "verify"
    REJECT = "reject"
    RESTRICT = "restrict"
    SUPERSEDE = "supersede"


class TransitionOutcome(Enum):
    """What the state machine says about one (current state, command) pair."""

    #: A real transition: check the precondition, then apply it.
    ALLOWED = "allowed"
    #: The document already holds the command's target state. Whether
    #: that is an idempotent retry or a conflicting second decision is
    #: decided by :func:`is_equivalent_repeat`, never by the state alone.
    ALREADY_IN_TARGET_STATE = "already_in_target_state"
    #: Refused. The caller is told the current state, not silently given
    #: a different transition.
    CONFLICT = "conflict"


#: The state a newly created document starts in. Mirrored by the
#: ``documents.evidence_status`` column default, so a row written by any
#: path -- service, migration backfill, or direct SQL -- is not approved
#: evidence until a human says so.
INITIAL_EVIDENCE_STATUS: Final = EvidenceStatus.PENDING_REVIEW

#: Which state each command records when it succeeds.
COMMAND_TARGET_STATUS: Final[Mapping[EvidenceReviewCommand, EvidenceStatus]] = MappingProxyType(
    {
        EvidenceReviewCommand.VERIFY: EvidenceStatus.VERIFIED,
        EvidenceReviewCommand.REJECT: EvidenceStatus.REJECTED,
        EvidenceReviewCommand.RESTRICT: EvidenceStatus.RESTRICTED,
        EvidenceReviewCommand.SUPERSEDE: EvidenceStatus.SUPERSEDED,
    }
)

#: The authoritative transition matrix: from each state, the commands
#: that may genuinely change it. Read-only at runtime (``MappingProxyType``
#: of ``frozenset``s) so no code path can widen the policy after import.
#: A command whose target equals the current state is *not* listed here --
#: that case is the repeat one, handled before this table is consulted.
ALLOWED_TRANSITIONS: Final[
    Mapping[EvidenceStatus, frozenset[EvidenceReviewCommand]]
] = MappingProxyType(
    {
        EvidenceStatus.PENDING_REVIEW: frozenset(
            {
                EvidenceReviewCommand.VERIFY,
                EvidenceReviewCommand.REJECT,
                EvidenceReviewCommand.RESTRICT,
                EvidenceReviewCommand.SUPERSEDE,
            }
        ),
        # Withdrawal of an approval, never a second approval.
        EvidenceStatus.VERIFIED: frozenset(
            {
                EvidenceReviewCommand.REJECT,
                EvidenceReviewCommand.RESTRICT,
                EvidenceReviewCommand.SUPERSEDE,
            }
        ),
        # Terminal for Slice 4: no approved re-review command exists, so
        # nothing here may return a document to an eligible state -- or to
        # any other decision -- through the ordinary review commands.
        EvidenceStatus.REJECTED: frozenset(),
        EvidenceStatus.RESTRICTED: frozenset(),
        EvidenceStatus.SUPERSEDED: frozenset(),
    }
)

#: Commands whose reason is mandatory. VERIFY's note is optional: an
#: approval's meaning is carried by the decision itself, whereas a
#: refusal, restriction or supersession is not interpretable without one.
REASON_REQUIRED_COMMANDS: Final[frozenset[EvidenceReviewCommand]] = frozenset(
    {
        EvidenceReviewCommand.REJECT,
        EvidenceReviewCommand.RESTRICT,
        EvidenceReviewCommand.SUPERSEDE,
    }
)

#: The only command that may record a successor document.
SUCCESSOR_ACCEPTING_COMMANDS: Final[frozenset[EvidenceReviewCommand]] = frozenset(
    {EvidenceReviewCommand.SUPERSEDE}
)

#: Bounded, per the existing API convention of explicit maximum sizes on
#: free text (``_MAX_QUERY_TEXT_CHARS``/``_MAX_QUOTED_SNIPPET_CHARS`` in
#: the analysis service). This is a review justification, not a comment
#: thread -- Slice 4 builds no discussion system.
MAX_REVIEW_REASON_CHARS: Final = 1000

#: The states whose documents may be retrieved as evidence. Exactly one.
#: Every other state -- including the initial one -- is ineligible, so
#: retrieval fails closed for anything a human has not explicitly
#: approved. The retrieval SQL binds this set rather than spelling
#: ``'VERIFIED'`` into a query string.
RETRIEVAL_ELIGIBLE_STATUSES: Final[frozenset[EvidenceStatus]] = frozenset(
    {EvidenceStatus.VERIFIED}
)

#: The ``documents.processing_status`` value a document must hold before
#: it may be approved as evidence. A plain string, because
#: ``processing_status`` is a plain, un-enumerated ``varchar`` column
#: throughout this codebase (see the ``Document`` entity's docstring);
#: promoting that column to a domain enum is a worthwhile later
#: refactor, and when it happens this constant is where the evidence
#: lifecycle's dependency on it is already isolated.
PROCESSED_PROCESSING_STATUS: Final = "PROCESSED"

#: Commands that may only be applied to a fully processed document.
#: Exactly one: approval. Withdrawal commands deliberately carry no
#: processing precondition, so a PENDING, PROCESSING or FAILED document
#: can still be rejected, restricted or superseded.
PROCESSING_PRECONDITION_COMMANDS: Final[frozenset[EvidenceReviewCommand]] = frozenset(
    {EvidenceReviewCommand.VERIFY}
)


def parse_evidence_status(raw: str | None) -> EvidenceStatus | None:
    """Resolve a stored column value to a state, or ``None`` if unusable.

    Fails closed by returning ``None`` for anything unrecognized -- a
    missing value, a non-string, or a value outside :class:`EvidenceStatus`
    -- so a row written by some future or buggy path can never be treated
    as an approved one. Unlike ``resolve_trusted_role`` this does *not*
    normalize case or whitespace: ``documents.evidence_status`` carries a
    database CHECK constraint restricting it to the exact five spellings,
    so a differing value is a real integrity problem to surface, not a
    formatting variation to absorb.
    """

    if not isinstance(raw, str):
        return None
    try:
        return EvidenceStatus(raw)
    except ValueError:
        return None


def target_status_for(command: EvidenceReviewCommand) -> EvidenceStatus:
    """The state ``command`` records when it is applied."""

    return COMMAND_TARGET_STATUS[command]


def evaluate_transition(
    current: EvidenceStatus, command: EvidenceReviewCommand
) -> TransitionOutcome:
    """Decide what ``command`` means for a document currently in ``current``.

    The repeat case is tested *first*, deliberately: a reviewer whose
    browser retries a ``verify`` must not be answered as though they were
    attempting a fresh transition. Only after that does the matrix decide
    between a real transition and a refusal.

    This answers the state question only. A caller must still apply
    :func:`satisfies_processing_precondition` to an ``ALLOWED`` result,
    and :func:`is_equivalent_repeat` to an ``ALREADY_IN_TARGET_STATE``
    one.
    """

    if current is target_status_for(command):
        return TransitionOutcome.ALREADY_IN_TARGET_STATE
    if command in ALLOWED_TRANSITIONS[current]:
        return TransitionOutcome.ALLOWED
    return TransitionOutcome.CONFLICT


def requires_reason(command: EvidenceReviewCommand) -> bool:
    """Whether ``command`` may not be recorded without a reason."""

    return command in REASON_REQUIRED_COMMANDS


def accepts_successor(command: EvidenceReviewCommand) -> bool:
    """Whether ``command`` may record a successor document."""

    return command in SUCCESSOR_ACCEPTING_COMMANDS


def required_processing_status_for(command: EvidenceReviewCommand) -> str | None:
    """The ``processing_status`` ``command`` requires, or ``None`` for any.

    Only VERIFY constrains it, and only to ``PROCESSED``: an approval
    asserts that this document's *content* is usable evidence, and until
    extraction and chunking have completed there is no content to
    approve -- a PENDING or PROCESSING document has not produced it yet
    and a FAILED one never will. Returning ``None`` for the three
    withdrawal commands is equally deliberate: a document that failed
    extraction is exactly the kind that needs rejecting, and a
    precondition there would strand it in PENDING_REVIEW permanently.

    Callers pass the result into the conditional UPDATE's predicate, so
    the precondition is enforced in the same statement as the
    transition rather than only by an earlier check.
    """

    if command in PROCESSING_PRECONDITION_COMMANDS:
        return PROCESSED_PROCESSING_STATUS
    return None


def satisfies_processing_precondition(
    command: EvidenceReviewCommand, processing_status: str | None
) -> bool:
    """Whether ``processing_status`` permits ``command`` to be applied.

    Accepts ``None`` and fails closed on it: a command that requires a
    specific processing state is refused when the state is absent or
    unknown, rather than being allowed through on the assumption that a
    missing value is harmless. A command with no precondition is
    unaffected either way.
    """

    required = required_processing_status_for(command)
    if required is None:
        return True
    return processing_status == required


def is_equivalent_repeat(
    *,
    recorded_reason: str | None,
    requested_reason: str | None,
    recorded_successor: UUID | None,
    requested_successor: UUID | None,
) -> bool:
    """Whether a repeated command is the *same decision* already recorded.

    Reaching this function means the document already holds the
    command's target state. That fact alone is not enough to call the
    request a retry: ``supersede`` twice with two different successors
    names two different replacement documents, and answering the second
    with a cheerful 200 would tell a reviewer their correction was
    recorded when the stored successor is still the first one. The same
    applies to a differing reason, which is the recorded justification
    for a decision that cannot otherwise be amended in Slice 4.

    Equivalence is therefore exact on both material fields, and both
    arguments are compared post-normalization (the caller strips and
    empty-to-``None``-collapses the requested reason before calling, so
    ``"  approved  "`` matches a stored ``"approved"`` while
    ``"approved with caveats"`` does not).

    A non-equivalent repeat is a conflict, not a silent no-op and not an
    overwrite: the recorded decision stands and the caller is told so.
    """

    return recorded_reason == requested_reason and recorded_successor == requested_successor


def is_retrieval_eligible(status: EvidenceStatus | str | None) -> bool:
    """Whether a document in ``status`` may be returned by retrieval.

    Accepts the raw stored string as well as the enum so callers holding
    either form ask the same question of the same policy. Anything
    unparseable is ineligible -- deny by default.
    """

    resolved = status if isinstance(status, EvidenceStatus) else parse_evidence_status(status)
    if resolved is None:
        return False
    return resolved in RETRIEVAL_ELIGIBLE_STATUSES


def retrieval_eligible_status_values() -> tuple[str, ...]:
    """The eligible states as sorted column values, for SQL binding."""

    return tuple(sorted(status.value for status in RETRIEVAL_ELIGIBLE_STATUSES))


def evidence_status_values() -> tuple[str, ...]:
    """Every valid column value, in declaration order."""

    return tuple(status.value for status in EvidenceStatus)
