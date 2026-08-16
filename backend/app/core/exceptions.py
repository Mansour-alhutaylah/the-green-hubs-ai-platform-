"""Application-wide exception hierarchy and FastAPI error-handler registration.

Every domain/service-layer error should subclass ``AppError`` rather than
raising ``HTTPException`` directly outside the API layer -- this keeps
``domain/`` and ``services/`` free of FastAPI imports.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app")

_UNEXPECTED_ERROR_DETAIL = "An unexpected error occurred. Please try again later."


class AppError(Exception):
    """Base class for all application-raised errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED


class ProfileNotProvisionedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN


class AuthorizationError(AppError):
    status_code = status.HTTP_403_FORBIDDEN


class PersistenceError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class InvalidStateTransitionError(AppError):
    status_code = status.HTTP_409_CONFLICT


class PayloadTooLargeError(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE


class UpstreamTimeoutError(AppError):
    """An approved upstream service did not answer within its budget.

    504 rather than 500: the failure is attributable and the request may
    be safely retried by the caller. Its message is one of the fixed safe
    sentences in ``app.domain.aios.contracts`` -- never an upstream's own
    error text, which can carry hostnames and stack frames.
    """

    status_code = status.HTTP_504_GATEWAY_TIMEOUT


class UpstreamUnavailableError(AppError):
    """An approved upstream service could not be reached, or refused.

    Also covers a reachable upstream whose answer cannot be trusted --
    a caller cannot act differently on "unreachable" than on "answered
    incoherently", so both map here.
    """

    status_code = status.HTTP_502_BAD_GATEWAY


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class AIOSNotConfiguredError(AppError):
    """AIOS is switched off, or has no signing key ring on this deployment.

    503 rather than 500: nothing is broken, the capability is simply not
    available here. This is what a caller sees after the documented
    rollback -- disable the flag, or revoke the credentials -- so it must
    be a clean, honest answer rather than an error.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


class UnexpectedErrorMiddleware:
    """Convert unexpected HTTP exceptions into a safe response.

    Starlette treats handlers registered for ``Exception`` as 500 handlers
    on its outer ``ServerErrorMiddleware``.  Such responses bypass user
    middleware, including CORS.  This middleware is instead installed below
    ``CORSMiddleware`` so its response follows the normal outbound middleware
    path and keeps the configured CORS headers.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_with_state(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_with_state)
        except Exception as exc:
            logger.exception("Unhandled exception", exc_info=exc)
            if response_started:
                raise
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": _UNEXPECTED_ERROR_DETAIL},
            )
            await response(scope, receive, send)


def register_exception_handlers(app: FastAPI) -> None:
    # Must be registered before CORSMiddleware. Starlette prepends each user
    # middleware, so adding CORS afterwards makes it the outer wrapper and
    # lets it decorate the safe 500 response produced here.
    app.add_middleware(UnexpectedErrorMiddleware)

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, AuthenticationError) else None
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.message}, headers=headers
        )
