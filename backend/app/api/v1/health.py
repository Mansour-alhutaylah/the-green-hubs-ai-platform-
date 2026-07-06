"""Liveness and DB-connectivity health checks.

These are the only endpoints this sprint ships -- they exist purely to
prove the application boots and the async DB wiring works end-to-end
against a real Supabase connection, with no domain/business logic involved.
"""

import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_db
from app.core.config import Settings
from app.schemas.health import DBHealthResponse, HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_app_settings)) -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name, version="0.1.0")


@router.get("/health/db", response_model=DBHealthResponse)
async def health_db(
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> DBHealthResponse:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Database health check failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return DBHealthResponse(status="error", database="unreachable")
    return DBHealthResponse(status="ok", database="reachable")
