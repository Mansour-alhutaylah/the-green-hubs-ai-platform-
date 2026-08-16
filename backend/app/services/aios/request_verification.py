"""Verifies a signature on behalf of the orchestrator. Nothing else.

This is the Cloud-compatible half of the signing design. The target is
n8n Cloud, where a Code node cannot read a credential value and ``$env``
is unavailable, and Founder decision (Gate 1) forbids placing the HMAC
secret in n8n in any form -- including ``$vars`` and including an
exported workflow's JSON. So the proof is inverted: the orchestrator
forwards the signing headers and the exact raw body back here, and this
process, which already holds the secret, performs the comparison.

The secret therefore never leaves the platform secret store. That is
strictly stronger than any arrangement in which the orchestrator holds
it.

**This service is deliberately inert.** It performs no product action,
touches no tenant data, writes no database row, dispatches no workflow
and returns no signing material. It answers one boolean. Everything it
could otherwise be asked to do is absent from its dependencies -- it has
none beyond a key ring and a clock -- so the property is structural
rather than a rule someone must keep obeying.

**One generic failure.** Internally the verifier distinguishes a bad
signature from an expired timestamp from an unknown key id, because an
operator debugging a rotation needs that. Externally all three collapse
to one answer. Returning "unsupported key id" would turn this endpoint
into an oracle for which key ids exist, and returning "timestamp out of
window" would confirm that a captured signature was otherwise valid.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping
from uuid import UUID

from app.domain.aios.contracts import (
    GENERIC_VERIFICATION_FAILURE,
    AIOSErrorCategory,
)
from app.domain.aios.workflows import resolve_workflow
from app.infrastructure.aios.internal_signature import (
    SignatureError,
    SigningKeyRing,
    decode_body_base64,
    log_verification_failure,
    verify_signed_request,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VerificationOutcome:
    """The only thing this service will say about a request."""

    valid: bool
    request_id: UUID | None
    #: Always :data:`GENERIC_VERIFICATION_FAILURE` when invalid. Present
    #: so the API layer never has to invent a category of its own.
    category: AIOSErrorCategory | None


class RequestVerificationService:
    """Verifies one signed orchestration request. Holds no other power."""

    def __init__(
        self,
        key_ring: SigningKeyRing,
        *,
        max_clock_skew_seconds: int,
        max_body_bytes: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._key_ring = key_ring
        self._max_clock_skew_seconds = max_clock_skew_seconds
        self._max_body_bytes = max_body_bytes
        self._clock: Callable[[], datetime] = clock or (
            lambda: datetime.now(timezone.utc)
        )

    def verify(
        self,
        *,
        workflow: str,
        headers: Mapping[str, str],
        body_base64: str,
        key_id_header: str,
        timestamp_header: str,
        request_id_header: str,
        signature_header: str,
    ) -> VerificationOutcome:
        """Verify a forwarded request. Never raises for an invalid one."""

        try:
            # The workflow identifier participates in the signature, so a
            # request signed for one workflow cannot be replayed against
            # another even with a valid signature. Checking it against the
            # allowlist first also means an unregistered name never
            # reaches the HMAC path at all.
            registered = resolve_workflow(workflow)
            if registered is None:
                raise SignatureError(
                    AIOSErrorCategory.WORKFLOW_NOT_ALLOWED,
                    "workflow is not in the allowlist",
                )

            body = decode_body_base64(body_base64, max_bytes=self._max_body_bytes)

            request_id = verify_signed_request(
                key_ring=self._key_ring,
                key_id=headers.get(key_id_header),
                timestamp=headers.get(timestamp_header),
                request_id=headers.get(request_id_header),
                workflow=registered.identifier,
                signature=headers.get(signature_header),
                body=body,
                now=self._clock(),
                max_clock_skew_seconds=self._max_clock_skew_seconds,
            )
        except SignatureError as error:
            log_verification_failure(error, direction="fastapi->n8n")
            return VerificationOutcome(
                valid=False,
                request_id=None,
                category=GENERIC_VERIFICATION_FAILURE,
            )

        return VerificationOutcome(valid=True, request_id=request_id, category=None)
