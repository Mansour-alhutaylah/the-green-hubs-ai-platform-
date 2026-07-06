"""Concrete async repository for the ``Document`` aggregate.

Implements ``IDocumentRepository`` directly rather than subclassing the
generic ``SQLAlchemyRepository`` in this package: that generic class hands
back whatever ``ModelType`` it is parameterized with straight from the
session, which is only correct when the ORM model itself is what callers
expect. Here, callers expect the pure ``Document`` domain entity, so every
method maps explicitly between ``DocumentModel`` (ORM) and ``Document``
(domain) via ``_to_domain`` -- the ORM type never crosses the repository
boundary.
"""

from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domain.entities.document import Document
from app.domain.repositories.document import IDocumentRepository
from app.infrastructure.db.models.document import DocumentModel


def _to_domain(model: DocumentModel) -> Document:
    return Document(
        id=model.id,
        filename=model.filename,
        storage_path=model.storage_path,
        processing_status=model.processing_status,
        engagement_id=model.engagement_id,
        created_at=model.created_at,
    )


class SQLAlchemyDocumentRepository(IDocumentRepository):
    """Async, PostgreSQL-backed implementation of ``IDocumentRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: UUID) -> Document | None:
        model = await self._session.get(DocumentModel, entity_id)
        return _to_domain(model) if model is not None else None

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[Document]:
        stmt = select(DocumentModel).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [_to_domain(model) for model in result.scalars().all()]

    async def create(self, entity: Document) -> Document:
        model = DocumentModel(
            id=entity.id,
            filename=entity.filename,
            storage_path=entity.storage_path,
            processing_status=entity.processing_status,
            engagement_id=entity.engagement_id,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def update(self, entity: Document) -> Document:
        model = await self._session.get(DocumentModel, entity.id)
        if model is None:
            raise NotFoundError(f"Document {entity.id} not found")
        model.filename = entity.filename
        model.storage_path = entity.storage_path
        model.processing_status = entity.processing_status
        model.engagement_id = entity.engagement_id
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def delete(self, entity: Document) -> None:
        model = await self._session.get(DocumentModel, entity.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.commit()

    async def get_by_engagement(self, engagement_id: UUID) -> Sequence[Document]:
        stmt = select(DocumentModel).where(DocumentModel.engagement_id == engagement_id)
        result = await self._session.execute(stmt)
        return [_to_domain(model) for model in result.scalars().all()]

    async def update_status(self, document_id: UUID, status: str) -> Document:
        model = await self._session.get(DocumentModel, document_id)
        if model is None:
            raise NotFoundError(f"Document {document_id} not found")
        model.processing_status = status
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)
