"""Application-wide exception hierarchy and FastAPI error-handler registration.

Every domain/service-layer error should subclass ``AppError`` rather than
raising ``HTTPException`` directly outside the API layer -- this keeps
``domain/`` and ``services/`` free of FastAPI imports.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


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


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
