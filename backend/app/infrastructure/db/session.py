"""Async SQLAlchemy engine and per-request session dependency.

Hemaya's ``database.py`` used a synchronous engine with a single global
``SessionLocal`` reused across the whole process. Here every request gets
its own ``AsyncSession`` via ``get_db()``, matching the project's async
programming requirement and avoiding any shared, global session state.
"""

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url or "postgresql+asyncpg://",
    pool_pre_ping=True,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
