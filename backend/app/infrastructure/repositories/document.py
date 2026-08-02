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

``get_read_model_for_organization``/``list_read_models_for_organization``/
``count_for_organization`` (Sprint 3, Document Read API Foundation) use
raw ``text()`` SQL with ``LEFT JOIN LATERAL`` -- mirroring
``SQLAlchemyAnalysisRunRepository``'s established use of ``text()`` for
queries a Core ``select()`` cannot express cleanly. Each lateral
subquery correlates on the outer document row (``d.id``) and returns at
most one row (an aggregate, or a ``LIMIT 1``), so none of the three
joins can fan out a document into duplicate rows -- this is what keeps
embedding/chunk counts from ever being multiplied by the join, and lets
tenant scope, filters, ordering, and ``LIMIT``/``OFFSET`` all live in
this one statement rather than being applied per-row in Python. Bind
parameters that may be ``NULL`` are always wrapped ``CAST(:param AS
type)``, never a bare ``::type`` shorthand -- see
``SQLAlchemyAnalysisRunRepository``'s docstring for why asyncpg needs
this.

The embedding lateral join additionally filters on
``(provider, model, model_version)`` -- the app's one currently
configured embedding identity, passed in by the caller (ultimately
``Settings``/``deps.py``), never inferred from the data. Without this
filter, a document that was ever embedded under a since-changed
provider/model configuration (e.g. switching from direct OpenAI to
OpenRouter, whose model names take a different vendor-prefixed form)
would have its old, now-irrelevant attempt rows summed together with
its current ones under ``uq_document_chunk_embeddings_identity``'s
per-(chunk, provider, model, model_version) uniqueness -- inflating
``total_chunks`` and resurrecting long-since-superseded ``FAILED`` rows
into the live status. The old rows are never deleted or modified here;
they simply fall outside this scope, exactly as intended attempt
history should.
"""

from typing import Any, Sequence
from uuid import UUID

import asyncpg.exceptions as pg_exceptions  # type: ignore[import-untyped]
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, InvalidStateTransitionError, NotFoundError, PersistenceError
from app.domain.entities.document import Document
from app.domain.entities.document_read_model import AnalysisSummary, DocumentReadModel, EmbeddingSummary
from app.domain.repositories.document import IDocumentRepository
from app.infrastructure.db.models.document import DocumentModel

_READ_MODEL_COLUMNS = """
    d.id AS id,
    d.engagement_id AS engagement_id,
    d.filename AS filename,
    d.processing_status AS processing_status,
    d.created_at AS created_at,
    d.updated_at AS updated_at,
    et.has_extracted_text AS has_extracted_text,
    ca.chunk_count AS chunk_count,
    ea.total_chunks AS embedding_total_chunks,
    ea.processing AS embedding_processing,
    ea.completed AS embedding_completed,
    ea.failed AS embedding_failed,
    ra.id AS analysis_id,
    ra.status AS analysis_status,
    ra.analysis_type AS analysis_type,
    ra.created_at AS analysis_created_at,
    ra.completed_at AS analysis_completed_at,
    ra.structured_output AS analysis_structured_output
"""

_READ_MODEL_FROM_JOINS = """
    FROM documents d
    JOIN engagements e ON e.id = d.engagement_id
    LEFT JOIN LATERAL (
        SELECT (COUNT(*) > 0) AS has_extracted_text
        FROM extracted_text et
        WHERE et.document_id = d.id AND et.extracted_content IS NOT NULL
    ) et ON true
    LEFT JOIN LATERAL (
        SELECT COUNT(*) AS chunk_count
        FROM document_chunks dc
        WHERE dc.document_id = d.id
    ) ca ON true
    LEFT JOIN LATERAL (
        SELECT
            COUNT(*) AS total_chunks,
            COUNT(*) FILTER (WHERE dce.status = 'PROCESSING') AS processing,
            COUNT(*) FILTER (WHERE dce.status = 'COMPLETED') AS completed,
            COUNT(*) FILTER (WHERE dce.status = 'FAILED') AS failed
        FROM document_chunk_embeddings dce
        WHERE dce.document_id = d.id AND dce.organization_id = e.organization_id
          AND dce.provider = :embedding_provider
          AND dce.model = :embedding_model
          AND dce.model_version = :embedding_model_version
    ) ea ON true
    LEFT JOIN LATERAL (
        SELECT ar.id, ar.status, ar.analysis_type, ar.created_at, ar.completed_at,
               ar.structured_output
        FROM analysis_runs ar
        WHERE ar.document_id = d.id AND ar.organization_id = e.organization_id
        ORDER BY ar.created_at DESC, ar.id DESC
        LIMIT 1
    ) ra ON true
"""

_TENANT_AND_FILTER_WHERE = """
    WHERE e.organization_id = :organization_id
      AND (CAST(:engagement_id AS uuid) IS NULL OR d.engagement_id = CAST(:engagement_id AS uuid))
      AND (
        CAST(:processing_status AS varchar) IS NULL
        OR d.processing_status = CAST(:processing_status AS varchar)
      )
"""


def _read_model_from_row(row: Any) -> DocumentReadModel:
    embedding_summary = EmbeddingSummary(
        total_chunks=row.embedding_total_chunks,
        processing=row.embedding_processing,
        completed=row.embedding_completed,
        failed=row.embedding_failed,
        is_complete=(
            row.embedding_total_chunks > 0
            and row.embedding_failed == 0
            and row.embedding_processing == 0
            and row.embedding_completed == row.embedding_total_chunks
        ),
    )

    latest_analysis_summary: AnalysisSummary | None = None
    if row.analysis_id is not None:
        overall_confidence: float | None = None
        if row.analysis_status == "COMPLETED" and row.analysis_structured_output is not None:
            raw_confidence = row.analysis_structured_output.get("overall_confidence")
            if isinstance(raw_confidence, (int, float)):
                overall_confidence = float(raw_confidence)
        latest_analysis_summary = AnalysisSummary(
            id=row.analysis_id,
            status=row.analysis_status,
            analysis_type=row.analysis_type,
            created_at=row.analysis_created_at,
            completed_at=row.analysis_completed_at,
            overall_confidence=overall_confidence,
        )

    return DocumentReadModel(
        id=row.id,
        engagement_id=row.engagement_id,
        filename=row.filename,
        processing_status=row.processing_status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        has_extracted_text=bool(row.has_extracted_text),
        chunk_count=row.chunk_count,
        embedding_summary=embedding_summary,
        latest_analysis_summary=latest_analysis_summary,
    )

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
        # `updated_at`'s `onupdate=func.now()` is a server-evaluated SQL
        # expression, so SQLAlchemy marks it expired after flush rather
        # than knowing its new value -- refresh() re-reads it (still
        # within this uncommitted transaction) so _to_domain() below can
        # read it directly instead of triggering an unawaited lazy load,
        # which raises MissingGreenlet under the async engine.
        await self._session.refresh(model)
        return _to_domain(model)

    async def get_read_model_for_organization(
        self,
        document_id: UUID,
        *,
        organization_id: UUID,
        embedding_provider: str,
        embedding_model: str,
        embedding_model_version: str,
    ) -> DocumentReadModel | None:
        stmt = text(
            f"SELECT {_READ_MODEL_COLUMNS} {_READ_MODEL_FROM_JOINS} "
            f"{_TENANT_AND_FILTER_WHERE} AND d.id = :document_id"
        )
        result = await self._session.execute(
            stmt,
            {
                "organization_id": organization_id,
                "engagement_id": None,
                "processing_status": None,
                "document_id": document_id,
                "embedding_provider": embedding_provider,
                "embedding_model": embedding_model,
                "embedding_model_version": embedding_model_version,
            },
        )
        row = result.mappings().first()
        return _read_model_from_row(row) if row is not None else None

    async def list_read_models_for_organization(
        self,
        *,
        organization_id: UUID,
        engagement_id: UUID | None = None,
        processing_status: str | None = None,
        limit: int,
        offset: int,
        embedding_provider: str,
        embedding_model: str,
        embedding_model_version: str,
    ) -> Sequence[DocumentReadModel]:
        stmt = text(
            f"SELECT {_READ_MODEL_COLUMNS} {_READ_MODEL_FROM_JOINS} "
            f"{_TENANT_AND_FILTER_WHERE} "
            "ORDER BY d.created_at DESC, d.id DESC "
            "LIMIT :limit OFFSET :offset"
        )
        result = await self._session.execute(
            stmt,
            {
                "organization_id": organization_id,
                "engagement_id": engagement_id,
                "processing_status": processing_status,
                "limit": limit,
                "offset": offset,
                "embedding_provider": embedding_provider,
                "embedding_model": embedding_model,
                "embedding_model_version": embedding_model_version,
            },
        )
        return [_read_model_from_row(row) for row in result.mappings().all()]

    async def count_for_organization(
        self,
        *,
        organization_id: UUID,
        engagement_id: UUID | None = None,
        processing_status: str | None = None,
    ) -> int:
        stmt = text(
            "SELECT COUNT(*) "
            "FROM documents d "
            "JOIN engagements e ON e.id = d.engagement_id "
            f"{_TENANT_AND_FILTER_WHERE}"
        )
        result = await self._session.execute(
            stmt,
            {
                "organization_id": organization_id,
                "engagement_id": engagement_id,
                "processing_status": processing_status,
            },
        )
        return result.scalar_one()
