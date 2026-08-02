"""Application factory.

Sprint 1 scope: boots a FastAPI app with logging, an explicit CORS
allow-list (never Hemaya's ``allow_origins=["*"]``), the standardized
``AppError`` -> JSON error envelope, and the v1 health-check router. No
business logic, no AI/RAG, no authentication.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, install_request_context_logging
from app.core.request_context import CORRELATION_HEADER_NAME, RequestContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    install_request_context_logging()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    register_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[CORRELATION_HEADER_NAME],
    )

    # Starlette prepends user middleware, so registering this last makes it
    # the outer request wrapper while preserving CORS -> unexpected-error.
    app.add_middleware(RequestContextMiddleware)

    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
