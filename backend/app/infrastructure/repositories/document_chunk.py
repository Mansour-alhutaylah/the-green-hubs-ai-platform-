"""Concrete async repository for the ``DocumentChunk`` aggregate.

``create_many()`` deliberately flushes rather than commits -- see
``SQLAlchemyExtractedTextRepository``'s docstring for the same
transaction-ownership rationale. Bulk-inserts via ``session.add_all``,
a single round-trip rather than one commit per chunk. A
unique-constraint violation (duplicate ``(document_id, chunk_index)``)
is mapped to ``PersistenceError`` rather than a raw DB exception.
"""

from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PersistenceError
from app.domain.entities.document_chunk import DocumentChunk
from app.domain.repositories.document_chunk import IDocumentChunkRepository
from app.infrastructure.db.models.document_chunk import DocumentChunkModel


def _to_domain(model: DocumentChunkModel) -> DocumentChunk:
    return DocumentChunk(
        id=model.id,
        document_id=model.document_id,
        chunk_index=model.chunk_index,
        content=model.content,
        created_at=model.created_at,
    )


class SQLAlchemyDocumentChunkRepository(IDocumentChunkRepository):
    """Async, PostgreSQL-backed implementation of ``IDocumentChunkRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, entities: Sequence[DocumentChunk]) -> Sequence[DocumentChunk]:
        models = [
            DocumentChunkModel(
                document_id=entity.document_id,
                chunk_index=entity.chunk_index,
                content=entity.content,
            )
            for entity in entities
        ]
        self._session.add_all(models)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise PersistenceError("Unable to persist document chunks") from exc
        return [_to_domain(model) for model in models]

    async def get_by_document(self, document_id: UUID) -> Sequence[DocumentChunk]:
        stmt = (
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == document_id)
            .order_by(DocumentChunkModel.chunk_index.asc())
        )
        result = await self._session.execute(stmt)
        return [_to_domain(model) for model in result.scalars().all()]

    async def delete(self, entity: DocumentChunk) -> None:
        if entity.id is None:
            return
        model = await self._session.get(DocumentChunkModel, entity.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.commit()
