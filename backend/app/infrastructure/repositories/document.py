"""Concrete async repository for the ``Document`` aggregate.

Implements ``IDocumentRepository`` directly rather than subclassing the
generic ``SQLAlchemyRepository`` in this package: that generic class hands
back whatever ``ModelType`` it is parameterized with straight from the
session, which is only correct when the ORM model itself is what callers
expect. Here, callers expect the pure ``Document`` domain entity, so every
method maps explicitly between ``DocumentModel`` (ORM) and ``Document``
(domain) via ``_to_domain`` -- the ORM type never crosses the repository
boundary.

``create()`` distinguishes two real constraint-violation causes (Sprint
3.4, Document Upload Foundation): a foreign-key violation on
``engagement_id`` (the Engagement was deleted concurrently, between the
caller's own existence check and this insert) maps to ``NotFoundError``
(404) -- the same status the caller's earlier check would have produced
had it observed the deletion in time. A unique-constraint violation on
``storage_path``, or any other integrity error, maps to ``PersistenceError``
(500) -- a generic, non-leaking failure, never a raw DB exception. This
mapping is done here, in the SQL-aware repository layer, specifically so
the service layer never needs to import SQLAlchemy or asyncpg to
distinguish these cases.

``begin_processing()`` (Sprint 3.5) is the sole mechanism preventing two
concurrent requests from both claiming the same Document: a single
``UPDATE ... WHERE processing_status = 'PENDING' RETURNING ...``,
committed immediately. Verified empirically against this project's real
database during planning: a second, identical conditional UPDATE against
an already-claimed row matches zero rows under Postgres's default READ
COMMITTED isolation, because the two UPDATEs serialize via row-level
locking and the second one re-evaluates the WHERE clause against the
freshly committed value. A prior read followed by an unconditional write
would not provide this guarantee.
"""

from typing import Sequence
from uuid import UUID

import asyncpg.exceptions as pg_exceptions  # type: ignore[import-untyped]
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, InvalidStateTransitionError, NotFoundError, PersistenceError
from app.domain.entities.document import Document
from app.domain.repositories.document import IDocumentRepository
from app.infrastructure.db.models.document import DocumentModel

_STATE_TRANSITION_MESSAGES = {
    "PROCESSING": "Document is already being processed.",
    "PROCESSED": "Document has already been processed.",
    "FAILED": "Failed documents cannot be reprocessed in this sprint.",
}


def _to_domain(model: DocumentModel) -> Document:
    return Document(
        id=model.id,
        filename=model.filename,
        storage_path=model.storage_path,
        processing_status=model.processing_status,
        engagement_id=model.engagement_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _map_integrity_error(exc: IntegrityError, entity: Document) -> AppError:
    # SQLAlchemy's asyncpg dialect wraps the real asyncpg exception at
    # exc.orig.__cause__ (verified empirically against this project's
    # actual database during Sprint 3.4 planning), not at exc.orig
    # directly -- checking both keeps this correct even if that wrapping
    # detail changes across SQLAlchemy versions.
    candidates = (exc.orig, getattr(exc.orig, "__cause__", None))
    for candidate in candidates:
        if isinstance(candidate, pg_exceptions.ForeignKeyViolationError):
            return NotFoundError(f"Engagement {entity.engagement_id} not found")
        if isinstance(candidate, pg_exceptions.UniqueViolationError):
            return PersistenceError("A document with this storage path already exists")
    return PersistenceError("Unable to persist the document")


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
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise _map_integrity_error(exc, entity) from exc
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

    async def begin_processing(self, document_id: UUID) -> Document:
        stmt = (
            update(DocumentModel)
            .where(DocumentModel.id == document_id, DocumentModel.processing_status == "PENDING")
            .values(processing_status="PROCESSING")
            .returning(DocumentModel)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        await self._session.commit()
        if model is not None:
            return _to_domain(model)

        existing = await self._session.get(DocumentModel, document_id)
        if existing is None:
            raise NotFoundError(f"Document {document_id} not found")
        message = _STATE_TRANSITION_MESSAGES.get(
            existing.processing_status,
            f"Document is not in a PENDING state (current state: {existing.processing_status}).",
        )
        raise InvalidStateTransitionError(message)

    async def complete_processing(self, document_id: UUID) -> Document:
        model = await self._session.get(DocumentModel, document_id)
        if model is None:
            raise NotFoundError(f"Document {document_id} not found")
        model.processing_status = "PROCESSED"
        await self._session.flush()
        return _to_domain(model)
