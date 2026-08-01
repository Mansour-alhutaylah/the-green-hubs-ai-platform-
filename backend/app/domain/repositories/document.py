"""Abstract repository interface for ``Document`` entities.

Extends the generic ``IRepository`` CRUD contract with query shapes that a
generic interface cannot express: filtering documents by engagement, and
transitioning processing status without forcing callers to hand-construct a
full entity first. Concrete persistence (SQLAlchemy) lives in
``infrastructure/repositories`` and will implement this interface -- nothing
here may depend on a database or web framework.

``begin_processing``/``complete_processing`` (Sprint 3.5) are a
deliberate pair with different transaction behavior, documented on each:
``begin_processing`` is an atomic, immediately-committed conditional
transition (the sole mechanism preventing two concurrent processors from
both claiming the same Document); ``complete_processing`` flushes only,
as part of ``DocumentProcessingService``'s own transaction via
``IProcessingUnitOfWork``.

``get_read_model_for_organization``/``list_read_models_for_organization``/
``count_for_organization`` (Sprint 3, Document Read API Foundation) are
the tenant-scoped read methods behind ``GET /api/v1/documents`` and
``GET /api/v1/documents/{document_id}``. ``documents`` has no
``organization_id`` column of its own -- these methods derive tenant
scope through ``engagement_id -> engagements.organization_id`` inside
the query itself (never an unscoped fetch followed by an
in-application comparison), mirroring ``IEngagementRepository``'s
``get_for_organization`` convention.
"""

from abc import ABC, abstractmethod
from typing import Sequence
from uuid import UUID

from app.domain.entities.document import Document
from app.domain.entities.document_read_model import DocumentReadModel
from app.domain.repositories.base import IRepository


class IDocumentRepository(IRepository[Document], ABC):
    """Repository contract for retrieving and updating ``Document`` entities."""

    @abstractmethod
    async def get_by_engagement(self, engagement_id: UUID) -> Sequence[Document]: ...

    @abstractmethod
    async def update_status(self, document_id: UUID, status: str) -> Document: ...

    @abstractmethod
    async def begin_processing(self, document_id: UUID) -> Document:
        """Atomically transitions PENDING -> PROCESSING via a single
        conditional ``UPDATE ... WHERE processing_status = 'PENDING'``,
        committed immediately. Raises ``NotFoundError`` if the document
        does not exist, or ``InvalidStateTransitionError`` if it exists
        but is not currently PENDING."""
        ...

    @abstractmethod
    async def complete_processing(self, document_id: UUID) -> Document:
        """Sets processing_status to PROCESSED via flush only -- part of
        the caller's own transaction (see ``IProcessingUnitOfWork``), not
        committed here. Raises ``NotFoundError`` if the document no
        longer exists."""
        ...

    @abstractmethod
    async def get_read_model_for_organization(
        self,
        document_id: UUID,
        *,
        organization_id: UUID,
        embedding_provider: str,
        embedding_model: str,
        embedding_model_version: str,
    ) -> DocumentReadModel | None:
        """Tenant-scoped single-document read, with the derived fields
        the Document detail API needs. Returns ``None`` for a
        nonexistent or foreign-tenant document -- indistinguishable, by
        design.

        ``embedding_provider``/``embedding_model``/``embedding_model_version``
        scope the returned ``embedding_summary`` to that one (provider,
        model, model_version) identity -- the app's currently configured
        one, passed by the caller, never inferred here. A document can
        carry ``document_chunk_embeddings`` rows under other, historical
        identities (e.g. a prior provider/model before a configuration
        change); those rows are real attempt history worth keeping, but
        must never be summed into the *current* embedding status, or a
        stale FAILED attempt under an old identity would forever mark an
        otherwise fully-embedded document as failed/incomplete."""
        ...

    @abstractmethod
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
        """Tenant-scoped, paginated, newest-first (``created_at`` desc,
        ``id`` desc tiebreak) document listing with derived fields.
        ``engagement_id``/``processing_status`` are optional
        already-validated filters applied at query time.
        ``embedding_provider``/``embedding_model``/``embedding_model_version``
        scope each item's ``embedding_summary`` exactly as documented on
        ``get_read_model_for_organization`` above."""
        ...

    @abstractmethod
    async def count_for_organization(
        self,
        *,
        organization_id: UUID,
        engagement_id: UUID | None = None,
        processing_status: str | None = None,
    ) -> int:
        """Total row count for the same tenant scope and filters as
        ``list_read_models_for_organization``, for pagination."""
        ...
