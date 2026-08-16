"""The AIOS request/response contract: version, statuses, error categories.

Gate 3 of the AIOS foundation (see
``project-governance/07-aios/AIOS_Foundation_Architecture_Design.md``).
This module is pure, deterministic, framework-independent policy -- no
database, no network, no LLM, and no request-supplied value reaches any
decision here. It mirrors the shape of
``app.domain.evidence.lifecycle``: the vocabulary lives in one module and
everything downstream reads its policy from here rather than restating
it.

**What the contract is for.** n8n orchestrates; it carries no independent
product authority. The envelope therefore separates two kinds of field,
and the separation is the whole point:

* *authoritative* fields -- ``request_id``, ``correlation_id``,
  ``requested_at``, ``actor.*``, ``workflow`` -- are produced by this
  application after authentication and authorization. A client never
  supplies them.
* *informational* fields -- everything under ``input`` -- are the
  workflow's own payload and confer no authority whatsoever.

Once forwarded, the actor block is *execution context*: it exists so a
workflow can label its logs and route a checkpoint. It is never an
authorization decision made by n8n.

:data:`FORBIDDEN_ACTOR_FIELDS` is the enforcement of that rule at the
inbound boundary. A client that sends one of those names -- at any depth
of the payload -- is refused rather than silently stripped: stripping
teaches a caller that sending it was acceptable, and the next caller
sends it expecting it to matter.
"""

from enum import Enum
from types import MappingProxyType
from typing import Any, Final, Mapping

#: The only contract version this application speaks. An envelope or
#: response carrying anything else is rejected, never coerced -- a
#: version field that is tolerated when it disagrees is decoration.
CONTRACT_VERSION: Final = "1.0"


class AIOSStatus(str, Enum):
    """The lifecycle of one orchestration request.

    ``str``-valued to match ``Permission``/``Role``/``EvidenceStatus``'s
    established shape, so the wire value and the enum member share one
    spelling.
    """

    #: Contract and authentication passed; work has not started.
    ACCEPTED = "accepted"
    #: Execution in progress.
    RUNNING = "running"
    #: Finished successfully. ``output`` is valid.
    COMPLETED = "completed"
    #: Refused before execution -- contract, allowlist, window or auth.
    REJECTED = "rejected"
    #: Paused at a human checkpoint. Neither an approval nor a denial:
    #: a decision is outstanding. n8n may *request* approval; it may
    #: never manufacture one, and a timeout is never consent.
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    #: Execution failed. An error category is populated.
    FAILED = "failed"


#: Statuses that end a request. ``HUMAN_APPROVAL_REQUIRED`` is
#: deliberately absent -- a pause is not an outcome.
TERMINAL_STATUSES: Final[frozenset[AIOSStatus]] = frozenset(
    {AIOSStatus.COMPLETED, AIOSStatus.REJECTED, AIOSStatus.FAILED}
)


class AIOSErrorCategory(str, Enum):
    """The closed set of failure reasons a caller may be told.

    Closed on purpose: an open-ended reason string is how provider
    messages, SQL fragments and stack traces reach clients.
    """

    CONTRACT_INVALID = "contract_invalid"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    SIGNATURE_INVALID = "signature_invalid"
    TIMESTAMP_OUT_OF_WINDOW = "timestamp_out_of_window"
    UNSUPPORTED_KEY_ID = "unsupported_key_id"
    WORKFLOW_NOT_ALLOWED = "workflow_not_allowed"
    DUPLICATE_REQUEST = "duplicate_request"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    UPSTREAM_UNEXPECTED_RESPONSE = "upstream_unexpected_response"
    INTERNAL_ERROR = "internal_error"


#: One fixed, safe sentence per category. Nothing here names a secret, a
#: key id, a host, a node, a stack frame or an upstream product.
#: ``SupabaseJWTVerifier`` already applies this discipline by collapsing
#: every verification failure to a single generic message; this is the
#: same rule expressed as a table.
SAFE_ERROR_MESSAGES: Final[Mapping[AIOSErrorCategory, str]] = MappingProxyType(
    {
        AIOSErrorCategory.CONTRACT_INVALID: "The orchestration request was not valid.",
        AIOSErrorCategory.UNAUTHENTICATED: "Invalid authentication credentials",
        AIOSErrorCategory.FORBIDDEN: "You do not have permission to perform this action.",
        AIOSErrorCategory.SIGNATURE_INVALID: "The orchestration request was not valid.",
        AIOSErrorCategory.TIMESTAMP_OUT_OF_WINDOW: (
            "The orchestration request was not valid."
        ),
        AIOSErrorCategory.UNSUPPORTED_KEY_ID: "The orchestration request was not valid.",
        AIOSErrorCategory.WORKFLOW_NOT_ALLOWED: "That workflow is not available.",
        AIOSErrorCategory.DUPLICATE_REQUEST: "This request has already been submitted.",
        AIOSErrorCategory.PAYLOAD_TOO_LARGE: "The request payload is too large.",
        AIOSErrorCategory.UPSTREAM_TIMEOUT: (
            "The orchestration request did not complete in time."
        ),
        AIOSErrorCategory.UPSTREAM_UNAVAILABLE: (
            "The orchestration service is temporarily unavailable."
        ),
        AIOSErrorCategory.UPSTREAM_UNEXPECTED_RESPONSE: (
            "The orchestration service returned an unexpected result."
        ),
        AIOSErrorCategory.INTERNAL_ERROR: (
            "An unexpected error occurred. Please try again later."
        ),
    }
)

#: The three signature-verification failures that must be indistinguishable
#: to anyone who can reach the internal verification endpoint. They are
#: kept apart internally -- an operator debugging a rotation needs to know
#: which one fired -- but every one of them is *answered* as
#: ``SIGNATURE_INVALID``. Telling a caller "unsupported key id" instead of
#: "bad signature" turns the endpoint into an oracle for which key ids
#: exist.
INDISTINGUISHABLE_VERIFICATION_CATEGORIES: Final[frozenset[AIOSErrorCategory]] = (
    frozenset(
        {
            AIOSErrorCategory.SIGNATURE_INVALID,
            AIOSErrorCategory.TIMESTAMP_OUT_OF_WINDOW,
            AIOSErrorCategory.UNSUPPORTED_KEY_ID,
        }
    )
)

#: The single category every verification failure is reported as.
GENERIC_VERIFICATION_FAILURE: Final = AIOSErrorCategory.SIGNATURE_INVALID

#: Names a client may never place in an orchestration payload, at any
#: depth. Each one is either resolved server-side from the authenticated
#: profile (``user_id``, ``organization_id``, ``role``), decided by the
#: server-side permission policy (``permission``, ``permissions``,
#: ``is_admin``), or recorded only by an authorized human decision
#: (``reviewed_by``, ``evidence_status``, ``approval_state``).
#:
#: Sending one is refused, never stripped -- see the module docstring.
FORBIDDEN_ACTOR_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "user_id",
        "organization_id",
        "role",
        "permission",
        "permissions",
        "reviewed_by",
        "evidence_status",
        "approval_state",
        "is_admin",
    }
)


def parse_status(raw: object) -> AIOSStatus | None:
    """Resolve a wire status value, or ``None`` if unusable.

    Fails closed on anything unrecognized so an upstream that invents a
    status can never be read as a success. Callers map ``None`` to
    :attr:`AIOSStatus.FAILED` -- never optimistically to ``COMPLETED``.
    """

    if not isinstance(raw, str):
        return None
    try:
        return AIOSStatus(raw)
    except ValueError:
        return None


def safe_message_for(category: AIOSErrorCategory) -> str:
    """The one sentence a caller may be told about ``category``."""

    return SAFE_ERROR_MESSAGES[category]


def find_forbidden_field(payload: object) -> str | None:
    """Return the first forbidden authority field found, or ``None``.

    Walks the whole structure -- nested objects and arrays included --
    because a client that cannot set ``organization_id`` at the top level
    will try ``input.actor.organization_id`` next. Only mapping *keys*
    are inspected; a string value that happens to read ``"role"`` is
    ordinary data and is left alone.
    """

    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if isinstance(key, str) and key.strip().lower() in FORBIDDEN_ACTOR_FIELDS:
                return key.strip().lower()
            found = find_forbidden_field(value)
            if found is not None:
                return found
        return None

    if isinstance(payload, (list, tuple)):
        for item in payload:
            found = find_forbidden_field(item)
            if found is not None:
                return found
    return None


def is_supported_contract_version(raw: Any) -> bool:
    """Whether ``raw`` is the exact contract version this app speaks."""

    return isinstance(raw, str) and raw == CONTRACT_VERSION
