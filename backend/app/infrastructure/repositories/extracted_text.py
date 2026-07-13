"""Concrete async repository for the ``ExtractedText`` child record.

``create()`` deliberately flushes rather than commits: it is one of
three writes (extracted_text insert, document_chunks bulk insert, the
Document's PROCESSED status update) that must land in a single database
transaction, committed once by ``DocumentProcessingService`` via
``IProcessingUnitOfWork`` -- never here. A unique-constraint violation
(more than one extracted-text row per Document) is mapped to
``PersistenceError`` rather than a raw DB exception, mirroring
``SQLAlchemyDocumentRepository.create()``'s integrity-error handling.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PersistenceError
from app.domain.entities.extracted_text import ExtractedText
from app.domain.repositories.extracted_text import IExtractedTextRepository
from app.infrastructure.db.models.extracted_text import ExtractedText as ExtractedTextModel


def _to_domain(model: ExtractedTextModel) -> ExtractedText:
    return ExtractedText(
        id=model.id,
        document_id=model.document_id,
        extracted_content=model.extracted_content,
        created_at=model.created_at,
    )


class SQLAlchemyExtractedTextRepository(IExtractedTextRepository):
    """Async, PostgreSQL-backed implementation of ``IExtractedTextRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, entity: ExtractedText) -> ExtractedText:
        model = ExtractedTextModel(
            document_id=entity.document_id, extracted_content=entity.extracted_content
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise PersistenceError("Unable to persist extracted text for this document") from exc
        return _to_domain(model)

    async def get_by_document(self, document_id: UUID) -> ExtractedText | None:
        stmt = select(ExtractedTextModel).where(ExtractedTextModel.document_id == document_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    async def delete(self, entity: ExtractedText) -> None:
        if entity.id is None:
            return
        model = await self._session.get(ExtractedTextModel, entity.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.commit()
