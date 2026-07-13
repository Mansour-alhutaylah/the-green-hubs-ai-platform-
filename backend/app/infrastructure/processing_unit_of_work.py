"""SQLAlchemy-backed ``IProcessingUnitOfWork``.

Wraps the same ``AsyncSession`` instance the request's other processing
-scoped repositories share (via FastAPI's per-request dependency caching
of ``get_db()`` -- see ``app/api/deps.py``), so ``commit()``/``rollback()``
here govern exactly the writes those repositories made via ``flush()``.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.processing_unit_of_work import IProcessingUnitOfWork


class SQLAlchemyProcessingUnitOfWork(IProcessingUnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
