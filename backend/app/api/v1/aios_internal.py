"""The internal signature-verification endpoint used by n8n Cloud.

Kept in its own module, separate from the product-facing AIOS router, so
that "this endpoint cannot execute a workflow or reach product data" is
visible in the imports rather than asserted in a comment. It depends on
one service, and that service depends on a key ring and a clock.

**Why it exists.** On n8n Cloud a Code node cannot read a credential
value and ``$env`` is unavailable, and Founder decision (Gate 1) forbids
placing the HMAC secret in n8n in any form -- ``$vars`` and workflow JSON
included. So the orchestrator forwards what it received and asks this
application, which already holds the secret, whether the signature is
good. The secret never leaves the platform secret store.

**Why it is unauthenticated by end-user token.** The orchestrator has no
end-user token to present -- it is verifying one of *our* requests, not
acting for a person. The endpoint is therefore protected by what it
cannot do rather than by who is calling: it performs no product action,
touches no tenant data, writes no row, and answers one boolean. A
bounded payload size and a rate limit keep it from being an unbounded
compute surface.
"""

import logging

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    get_aios_verification_rate_limiter,
    get_app_settings,
    get_request_verification_service,
    read_bounded_body,
)
from app.core.config import Settings
from app.core.exceptions import RateLimitedError
from app.domain.aios.contracts import GENERIC_VERIFICATION_FAILURE
from app.infrastructure.aios.internal_signature import (
    HEADER_KEY_ID_LOWER,
    HEADER_REQUEST_ID_LOWER,
    HEADER_SIGNATURE_LOWER,
    HEADER_TIMESTAMP_LOWER,
)
from app.infrastructure.aios.rate_limit import FixedWindowRateLimiter
from app.schemas.aios import VerifyRequestPayload, VerifyRequestResponse
from app.services.aios.request_verification import RequestVerificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/aios", tags=["aios-internal"])

#: One bucket for the whole endpoint. Deliberately not keyed by client IP:
#: the only legitimate caller is the orchestrator, an IP-keyed limit would
#: be trivially evaded by a distributed caller, and a single global brake
#: is the honest expression of "this endpoint should see roughly one call
#: per orchestration request".
_RATE_LIMIT_KEY = "aios-verify-request"


@router.post(
    "/verify-request",
    response_model=VerifyRequestResponse,
    status_code=status.HTTP_200_OK,
    responses={
        413: {"description": "Payload too large"},
        429: {"description": "Rate limited"},
    },
    summary="Verify the HMAC signature of a forwarded orchestration request",
)
async def verify_request(
    request: Request,
    service: RequestVerificationService = Depends(get_request_verification_service),
    limiter: FixedWindowRateLimiter = Depends(get_aios_verification_rate_limiter),
    settings: Settings = Depends(get_app_settings),
) -> VerifyRequestResponse:
    if not limiter.allow(_RATE_LIMIT_KEY):
        raise RateLimitedError("Too many verification requests. Please retry shortly.")

    raw = await read_bounded_body(request, max_bytes=settings.aios_max_payload_bytes)

    # A malformed verification request is answered exactly like a failed
    # verification: `{"valid": false}`. Distinguishing "your JSON was
    # bad" from "your signature was bad" would let a caller probe the
    # endpoint's parsing without ever holding a key.
    try:
        payload = VerifyRequestPayload.model_validate_json(raw)
    except ValueError:
        logger.warning("AIOS verification request rejected: malformed payload")
        return VerifyRequestResponse(
            valid=False, request_id=None, category=GENERIC_VERIFICATION_FAILURE.value
        )

    # The signing headers are forwarded inside the payload rather than
    # replayed as real headers, because a proxy may legitimately rewrite
    # headers in transit and the signature must be checked against what
    # the orchestrator actually received. Lowercase keys throughout: n8n
    # normalizes header names, and a verifier written against the
    # mixed-case spelling would read nothing and fail every request.
    outcome = service.verify(
        workflow=payload.workflow,
        headers={
            HEADER_KEY_ID_LOWER: payload.key_id,
            HEADER_TIMESTAMP_LOWER: payload.timestamp,
            HEADER_REQUEST_ID_LOWER: payload.request_id,
            HEADER_SIGNATURE_LOWER: payload.signature,
        },
        body_base64=payload.body_base64,
        key_id_header=HEADER_KEY_ID_LOWER,
        timestamp_header=HEADER_TIMESTAMP_LOWER,
        request_id_header=HEADER_REQUEST_ID_LOWER,
        signature_header=HEADER_SIGNATURE_LOWER,
    )

    if not outcome.valid:
        return VerifyRequestResponse(
            valid=False,
            request_id=None,
            category=(outcome.category or GENERIC_VERIFICATION_FAILURE).value,
        )
    return VerifyRequestResponse(valid=True, request_id=outcome.request_id)
