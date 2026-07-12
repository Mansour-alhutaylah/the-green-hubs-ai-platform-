"""Shared FastAPI dependency providers.

This is the single seam where concrete infrastructure gets bound to the
abstractions that routers/services depend on -- idiomatic FastAPI
``Depends``-based DI, chosen over a separate IoC container library since it
fully satisfies the project's Dependency Injection requirement without extra
machinery. Future tasks add further per-entity providers here following the
same shape as ``get_document_repository``.
"""

from typing import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.organization import IOrganizationRepository
from app.infrastructure.db.session import get_db as _get_db
from app.infrastructure.repositories.document import SQLAlchemyDocumentRepository
from app.infrastructure.repositories.organization import SQLAlchemyOrganizationRepository
from app.services.organization import OrganizationService


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in _get_db():
        yield session


def get_app_settings() -> Settings:
    return get_settings()


def get_document_repository(
    session: AsyncSession = Depends(get_db),
) -> IDocumentRepository:
    return SQLAlchemyDocumentRepository(session)


def get_organization_repository(
    session: AsyncSession = Depends(get_db),
) -> IOrganizationRepository:
    return SQLAlchemyOrganizationRepository(session)


def get_organization_service(
    repository: IOrganizationRepository = Depends(get_organization_repository),
) -> OrganizationService:
    return OrganizationService(repository)
