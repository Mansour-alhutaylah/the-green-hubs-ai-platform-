"""Request-local correlation and trusted identity context."""

import logging
from contextvars import ContextVar, Token
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CORRELATION_HEADER_NAME = "X-Correlation-ID"
REQUEST_CONTEXT_STATE_KEY = "request_context"

_CORRELATION_HEADER_BYTES = CORRELATION_HEADER_NAME.lower().encode("ascii")
_CANONICAL_UUID_LENGTH = 36
_request_context: ContextVar["RequestContext | None"] = ContextVar(
    "request_context", default=None
)
_request_state: ContextVar[dict[str, Any] | None] = ContextVar(
    "request_state", default=None
)

logger = logging.getLogger("app.request")


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Safe request-local identifiers; never an authorization input."""

    correlation_id: str
    user_id: UUID | None = None
    organization_id: UUID | None = None


def get_request_context() -> RequestContext | None:
    """Return the active request context, or ``None`` outside a request."""

    return _request_context.get()


def enrich_request_context(
    *, user_id: UUID, organization_id: UUID | None
) -> RequestContext | None:
    """Add trusted server-resolved identity values to the active context.

    The correlation ID is intentionally not accepted here, so enrichment
    cannot replace it. Calls outside a request are safe no-ops.
    """

    current = get_request_context()
    if current is None:
        return None

    enriched = replace(current, user_id=user_id, organization_id=organization_id)
    _request_context.set(enriched)
    state = _request_state.get()
    if state is not None:
        state[REQUEST_CONTEXT_STATE_KEY] = enriched
    return enriched


def request_context_log_fields() -> dict[str, str]:
    """Return formatter-safe request fields for a log record."""

    context = get_request_context()
    if context is None:
        return {"correlation_id": "-", "user_id": "-", "organization_id": "-"}
    return {
        "correlation_id": context.correlation_id,
        "user_id": str(context.user_id) if context.user_id is not None else "-",
        "organization_id": (
            str(context.organization_id) if context.organization_id is not None else "-"
        ),
    }


def _new_correlation_id(headers: list[tuple[bytes, bytes]]) -> str:
    values = [
        value for name, value in headers if name.lower() == _CORRELATION_HEADER_BYTES
    ]
    if len(values) != 1 or len(values[0]) != _CANONICAL_UUID_LENGTH:
        return str(uuid4())

    try:
        supplied = values[0].decode("ascii")
    except UnicodeDecodeError:
        return str(uuid4())

    if any(
        character.isspace() or ord(character) < 32 or ord(character) == 127
        for character in supplied
    ):
        return str(uuid4())

    try:
        normalized = str(UUID(supplied))
    except ValueError:
        return str(uuid4())
    if supplied.lower() != normalized:
        return str(uuid4())
    return normalized


class RequestContextMiddleware:
    """Create, expose, log, and reliably reset per-request context."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = list(scope.get("headers", []))
        context = RequestContext(correlation_id=_new_correlation_id(headers))
        state = scope.setdefault("state", {})
        state[REQUEST_CONTEXT_STATE_KEY] = context
        context_token: Token[RequestContext | None] = _request_context.set(context)
        state_token: Token[dict[str, Any] | None] = _request_state.set(state)
        status_code: int | None = None
        started_at = perf_counter()

        async def send_with_correlation(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != _CORRELATION_HEADER_BYTES
                ]
                response_headers.append(
                    (_CORRELATION_HEADER_BYTES, context.correlation_id.encode("ascii"))
                )
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation)
        finally:
            duration_ms = (perf_counter() - started_at) * 1000
            logger.info(
                "HTTP request completed method=%s path=%s status_code=%s duration_ms=%.2f",
                scope.get("method", "-"),
                scope.get("path", "-"),
                status_code if status_code is not None else "-",
                duration_ms,
            )
            _request_state.reset(state_token)
            _request_context.reset(context_token)
