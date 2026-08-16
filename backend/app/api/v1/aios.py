"""The trusted product entry point for AIOS orchestration.

One route, one workflow. ``organization_id`` is never a request field --
it is resolved from ``current_user`` inside ``HealthCheckService``, the
same convention every tenant-scoped endpoint in this codebase follows.

The payload is read as raw bytes and inspected before Pydantic sees it,
for two reasons that a model alone cannot satisfy: a size ceiling must be
applied *before* parsing, and a forbidden authority field nested at any
depth deserves a specific answer rather than a generic schema complaint.
"""

import json
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, status
from pydantic import ValidationError as PydanticValidationError

from app.api.deps import (
    get_app_settings,
    get_health_check_service,
    read_bounded_body,
    require_permission,
)
from app.core.config import Settings
from app.core.exceptions import (
    AppError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
    ValidationError,
)
from app.core.request_context import get_request_context
from app.domain.aios.client import (
    AIOSTimeoutError,
    AIOSUnavailableError,
    AIOSUnexpectedResponseError,
)
from app.domain.aios.contracts import (
    AIOSErrorCategory,
    find_forbidden_field,
    safe_message_for,
)
from app.domain.aios.workflows import NORA_HEALTH_CHECK
from app.domain.entities.user import User
from app.domain.security import Permission
from app.schemas.aios import (
    AIOSInvokeResponse,
    AIOSResponseMetadata,
    HealthCheckInvokeRequest,
)
from app.services.aios.health_check import HealthCheckResult, HealthCheckService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/aios", tags=["aios"])


def _require_correlation_id() -> UUID:
    """The active request's correlation id, reused rather than minted.

    ``RequestContextMiddleware`` already established one for this request
    and already validated any client-supplied value, so the orchestration
    envelope inherits a trace that the API response header
    (``X-Correlation-ID``) also carries. Falling back to a fresh id keeps
    the service usable outside a request (in tests) without ever letting
    a caller choose it.
    """

    context = get_request_context()
    if context is None:
        return uuid4()
    try:
        return UUID(context.correlation_id)
    except ValueError:  # pragma: no cover - middleware guarantees canonical form
        return uuid4()


async def _read_validated_payload(
    request: Request, settings: Settings
) -> HealthCheckInvokeRequest:
    """Read, bound, scan and validate the request body, in that order."""

    raw = await read_bounded_body(request, max_bytes=settings.aios_max_payload_bytes)

    if not raw.strip():
        # An empty body is the ordinary way to invoke a workflow whose
        # input is empty. Treated as `{}` rather than rejected.
        payload: object = {}
    else:
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise ValidationError(
                safe_message_for(AIOSErrorCategory.CONTRACT_INVALID)
            ) from exc

    forbidden = find_forbidden_field(payload)
    if forbidden is not None:
        # Refused, never stripped. Naming the field is safe -- the client
        # sent it -- and telling them plainly is what stops the next
        # request repeating it. Nothing about the server's own actor
        # resolution is revealed.
        logger.warning(
            "AIOS request rejected: client supplied authority field %s", forbidden
        )
        raise ValidationError(
            f"The field '{forbidden}' may not be supplied by a client. "
            "Actor context is resolved server-side."
        )

    try:
        return HealthCheckInvokeRequest.model_validate(payload)
    except PydanticValidationError as exc:
        raise ValidationError(
            safe_message_for(AIOSErrorCategory.CONTRACT_INVALID)
        ) from exc


def _to_response(result: HealthCheckResult) -> AIOSInvokeResponse:
    metadata = result.metadata
    return AIOSInvokeResponse(
        contract_version=result.contract_version,
        request_id=result.request_id,
        correlation_id=result.correlation_id,
        workflow=result.workflow,
        status=result.status.value,
        output=dict(result.output),
        metadata=AIOSResponseMetadata(
            execution_id=_as_optional_str(metadata.get("execution_id")),
            workflow_version=_as_optional_str(metadata.get("workflow_version")),
            started_at=_as_optional_str(metadata.get("started_at")),
            completed_at=_as_optional_str(metadata.get("completed_at")),
        ),
    )


def _as_optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


@router.post(
    f"/workflows/{NORA_HEALTH_CHECK}",
    response_model=AIOSInvokeResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Unauthenticated"},
        403: {"description": "Missing aios.invoke, or user has no organization"},
        413: {"description": "Payload too large"},
        422: {"description": "Invalid contract or a client-supplied authority field"},
        502: {"description": "Orchestrator unavailable or answered incoherently"},
        504: {"description": "Orchestrator did not respond in time"},
    },
    summary="Run the deterministic NORA health check through the AIOS orchestrator",
)
async def invoke_nora_health_check(
    request: Request,
    current_user: User = Depends(require_permission(Permission.AIOS_INVOKE)),
    service: HealthCheckService = Depends(get_health_check_service),
    settings: Settings = Depends(get_app_settings),
) -> AIOSInvokeResponse:
    await _read_validated_payload(request, settings)

    try:
        result = await service.invoke(
            current_user, correlation_id=_require_correlation_id()
        )
    except AIOSTimeoutError as exc:
        raise UpstreamTimeoutError(
            safe_message_for(AIOSErrorCategory.UPSTREAM_TIMEOUT)
        ) from exc
    except AIOSUnavailableError as exc:
        raise UpstreamUnavailableError(
            safe_message_for(AIOSErrorCategory.UPSTREAM_UNAVAILABLE)
        ) from exc
    except AIOSUnexpectedResponseError as exc:
        # Deliberately mapped to the same 502 as "unavailable": a caller
        # cannot act differently on "unreachable" than on "answered
        # incoherently", and distinguishing them in the response would
        # describe the orchestrator's internal state to a product client.
        raise UpstreamUnavailableError(
            safe_message_for(AIOSErrorCategory.UPSTREAM_UNEXPECTED_RESPONSE)
        ) from exc
    except AppError:
        raise

    return _to_response(result)
