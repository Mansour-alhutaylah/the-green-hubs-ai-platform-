"""Async SQLAlchemy engine and per-request session dependency.

Hemaya's ``database.py`` used a synchronous engine with a single global
``SessionLocal`` reused across the whole process. Here every request gets
its own ``AsyncSession`` via ``get_db()``, matching the project's async
programming requirement and avoiding any shared, global session state.

Supabase's ``DATABASE_URL`` points at its PgBouncer pooler in transaction
mode, which does not preserve server-side prepared statements across a
logical connection's lifetime. asyncpg's default statement cache assumes it
does, so it raises ``DuplicatePreparedStatementError`` once two sessions
share a physical backend connection. ``NullPool`` plus disabling asyncpg's
prepared-statement cache and using randomized statement names is the fix
documented directly in SQLAlchemy's asyncpg dialect docs for this exact
PgBouncer scenario.
"""

from typing import AsyncIterator
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url or "postgresql+asyncpg://",
    pool_pre_ping=True,
    future=True,
    poolclass=NullPool,
    connect_args={
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
