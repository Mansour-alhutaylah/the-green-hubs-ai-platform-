"""The NORA Health Check use case.

Deliberately framework-independent -- no FastAPI import anywhere in this
module -- and deliberately the *whole* orchestration surface for the
foundation phase. It proves one property end to end: that an
authenticated, authorized, contract-validated request can travel from
this trusted gateway to the orchestrator and back, carrying a signature
the orchestrator can have verified, and nothing else happens.

What this service does **not** do is the specification, not an omission:
no database access, no document retrieval, no evidence review, no file
operation, no model-provider call, no external message, no application
mutation. It holds one dependency -- the transport port -- and that is
the entire reason it is safe to be the first thing built.

**Where the trusted context comes from.** ``current_user`` is the
profile resolved server-side by ``get_current_user`` from a verified
JWT. The actor block is built from it here, inside the service, so no
route signature and no request body can supply one. ``organization_id``
is required and fails closed when absent, matching
``DocumentUploadService`` and ``DocumentProcessingService``: a profile
with no organization has no tenant scope, and there is no default or
first-organization fallback anywhere in this codebase.

Once forwarded, those actor fields are execution context. The
orchestrator may label a log with them; it may not decide anything with
them.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Final, Mapping
from uuid import UUID, uuid4

from app.core.exceptions import AuthorizationError
from app.domain.aios.client import AIOSClient, AIOSDispatch, AIOSUnexpectedResponseError
from app.domain.aios.contracts import (
    CONTRACT_VERSION,
    AIOSStatus,
    is_supported_contract_version,
    parse_status,
)
from app.domain.aios.workflows import (
    NORA_HEALTH_CHECK,
    RegisteredWorkflow,
    is_dispatchable,
    resolve_workflow,
)
from app.domain.entities.user import User
from app.infrastructure.aios.internal_signature import TIMESTAMP_FORMAT

logger = logging.getLogger(__name__)

#: The envelope is serialized once, with these exact options, and the
#: resulting bytes are both signed and transmitted. `separators` removes
#: the whitespace `json.dumps` would otherwise insert, and
#: `ensure_ascii=False` keeps non-ASCII as UTF-8 rather than `\uXXXX`
#: escapes -- the difference that makes an Arabic payload digest
#: identically on both sides. These are not cosmetic preferences; they
#: are pinned by the cross-language vector fixture.
_JSON_SEPARATORS: Final = (",", ":")


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    """The validated orchestrator response, ready for the API layer."""

    contract_version: str
    request_id: UUID
    correlation_id: UUID
    workflow: str
    status: AIOSStatus
    output: Mapping[str, Any]
    metadata: Mapping[str, Any]


class HealthCheckService:
    """Dispatches ``nora.health_check`` and validates what comes back."""

    def __init__(
        self,
        client: AIOSClient,
        *,
        clock: Callable[[], datetime] | None = None,
        request_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._client = client
        self._clock: Callable[[], datetime] = clock or (
            lambda: datetime.now(timezone.utc)
        )
        # Injected so tests can pin an id; never client-supplied. The
        # request id is an authoritative field -- it is the signature's
        # replay anchor and the deduplication key a future mutating
        # workflow will claim on.
        self._request_id_factory = request_id_factory

    async def invoke(
        self, current_user: User, *, correlation_id: UUID
    ) -> HealthCheckResult:
        """Run the health check on behalf of ``current_user``."""

        workflow = self._require_dispatchable_workflow()
        organization_id = self._require_user_organization(current_user)

        request_id = self._request_id_factory()
        envelope_bytes = self._build_envelope(
            request_id=request_id,
            correlation_id=correlation_id,
            workflow=workflow,
            user_id=current_user.id,
            organization_id=organization_id,
        )

        body = await self._client.invoke(
            AIOSDispatch(
                workflow=workflow,
                envelope_bytes=envelope_bytes,
                request_id=request_id,
                correlation_id=correlation_id,
            )
        )
        return self._validate_response(
            body, request_id=request_id, correlation_id=correlation_id, workflow=workflow
        )

    # -- internals ---------------------------------------------------------

    def _require_dispatchable_workflow(self) -> RegisteredWorkflow:
        workflow = resolve_workflow(NORA_HEALTH_CHECK)
        # Both conditions are re-checked at the point of use rather than
        # trusted from import time, so deactivating NORA in the role
        # registry actually stops dispatch instead of only documenting it.
        if workflow is None or not is_dispatchable(workflow):
            raise AIOSUnexpectedResponseError(
                "The health check workflow is not currently dispatchable"
            )
        return workflow

    def _require_user_organization(self, current_user: User) -> UUID:
        # Fail closed: a profile with no organization has no tenant scope,
        # so there is no context under which it may orchestrate.
        if current_user.organization_id is None:
            raise AuthorizationError("User has no organization")
        return current_user.organization_id

    def _build_envelope(
        self,
        *,
        request_id: UUID,
        correlation_id: UUID,
        workflow: RegisteredWorkflow,
        user_id: UUID,
        organization_id: UUID,
    ) -> bytes:
        envelope = {
            "contract_version": CONTRACT_VERSION,
            "request_id": str(request_id),
            "correlation_id": str(correlation_id),
            "requested_at": self._clock()
            .astimezone(timezone.utc)
            .strftime(TIMESTAMP_FORMAT),
            "actor": {
                "user_id": str(user_id),
                "organization_id": str(organization_id),
            },
            "workflow": workflow.identifier,
            "input": {},
        }
        return json.dumps(
            envelope, separators=_JSON_SEPARATORS, ensure_ascii=False
        ).encode("utf-8")

    def _validate_response(
        self,
        body: Mapping[str, Any],
        *,
        request_id: UUID,
        correlation_id: UUID,
        workflow: RegisteredWorkflow,
    ) -> HealthCheckResult:
        """Judge whether the orchestrator answered *this* request, well.

        Every check here fails closed. An unrecognized status becomes
        ``FAILED`` rather than an optimistic ``COMPLETED``; a mismatched
        identifier is refused outright rather than reported as this
        caller's result.
        """

        if not is_supported_contract_version(body.get("contract_version")):
            raise AIOSUnexpectedResponseError(
                "orchestrator response declares an unsupported contract version"
            )
        if body.get("request_id") != str(request_id):
            raise AIOSUnexpectedResponseError(
                "orchestrator response does not match the dispatched request id"
            )
        if body.get("workflow") != workflow.identifier:
            raise AIOSUnexpectedResponseError(
                "orchestrator response does not match the dispatched workflow"
            )

        status = parse_status(body.get("status"))
        if status is None:
            logger.warning(
                "AIOS orchestrator returned an unrecognized status for workflow=%s",
                workflow.identifier,
            )
            status = AIOSStatus.FAILED

        output = body.get("output")
        metadata = body.get("metadata")
        return HealthCheckResult(
            contract_version=CONTRACT_VERSION,
            request_id=request_id,
            # Always this request's own correlation id, never the value
            # echoed back: a correlation id is for tracing *our* request,
            # and adopting an upstream's copy would let a misrouted
            # response silently rename this trace.
            correlation_id=correlation_id,
            workflow=workflow.identifier,
            status=status,
            output=output if isinstance(output, Mapping) else {},
            metadata=metadata if isinstance(metadata, Mapping) else {},
        )
