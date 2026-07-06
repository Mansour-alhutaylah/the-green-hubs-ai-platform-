"""Shared FastAPI dependency providers.

This is the single seam where concrete infrastructure gets bound to the
abstractions that routers/services depend on -- idiomatic FastAPI
``Depends``-based DI, chosen over a separate IoC container library since it
fully satisfies the project's Dependency Injection requirement without extra
machinery. Future tasks add per-entity providers here, e.g.:

    async def get_document_repository(
        session: AsyncSession = Depends(get_db),
    ) -> IRepository[Document]:
        return DocumentRepository(session)
"""

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.infrastructure.db.session import get_db as _get_db


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in _get_db():
        yield session


def get_app_settings() -> Settings:
    return get_settings()
