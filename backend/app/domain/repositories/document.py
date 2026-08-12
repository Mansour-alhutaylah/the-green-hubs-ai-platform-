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

MVP Slice 3 (Organization Data Isolation) extends that convention to
*every* Document access path. ``get_for_organization`` is added, and
``get_by_engagement``/``update_status``/``begin_processing``/
``complete_processing`` each gain a mandatory keyword-only
``organization_id``. These four are bespoke to this interface -- none of
them is declared by ``IRepository[Document]`` -- so unlike ``list``/
``get``/``update`` (see ``IEngagementRepository``'s docstring for the
Liskov constraint that forces those to stay unscoped) the tenant scope
can be made outright mandatory here without breaking substitutability.

The invariant every implementation must satisfy: the caller's trusted
``organization_id`` is part of the same SQL predicate that locates the
row. A cross-tenant ``document_id`` must therefore behave exactly like a
nonexistent one -- no row returned, no row mutated, and no distinguishable
error -- rather than being fetched first and rejected afterward by an
in-application comparison a later refactor could drop.
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
    async def get_for_organization(
        self, document_id: UUID, *, organization_id: UUID
    ) -> Document | None:
        """Tenant-scoped lookup of the Document aggregate itself.

        Ownership is resolved inside the query, through
        ``documents.engagement_id -> engagements.organization_id``.
        Returns ``None`` for a nonexistent document, for a document owned
        by another organization, and for a document whose engagement has
        no organization at all -- all three indistinguishable by design,
        so a valid foreign ``document_id`` is not an existence oracle.

        This is the only Document read a tenant-facing use case may
        perform; the inherited, unscoped ``get(entity_id)`` exists solely
        to satisfy ``IRepository``'s contract and for test cleanup."""
        ...

    @abstractmethod
    async def get_by_engagement(
        self, engagement_id: UUID, *, organization_id: UUID
    ) -> Sequence[Document]:
        """Tenant-scoped listing of one engagement's Documents. An
        engagement belonging to another organization yields an empty
        sequence rather than its rows."""
        ...

    @abstractmethod
    async def update_status(
        self, document_id: UUID, status: str, *, organization_id: UUID
    ) -> Document:
        """Tenant-scoped status write. The ``organization_id`` predicate
        is part of the statement that selects the row to mutate, so this
        can never update another organization's Document even if called
        with a foreign ``document_id``. Raises ``NotFoundError`` when no
        row matches both."""
        ...

    @abstractmethod
    async def begin_processing(self, document_id: UUID, *, organization_id: UUID) -> Document:
        """Atomically transitions PENDING -> PROCESSING via a single
        conditional, tenant-scoped ``UPDATE ... WHERE processing_status =
        'PENDING' AND <owned by organization_id>``, committed immediately.
        Raises ``NotFoundError`` if no Document matches both the id and
        the organization -- the cross-tenant case is deliberately
        indistinguishable from the nonexistent one -- or
        ``InvalidStateTransitionError`` if the caller's own Document
        exists but is not currently PENDING."""
        ...

    @abstractmethod
    async def complete_processing(self, document_id: UUID, *, organization_id: UUID) -> Document:
        """Sets processing_status to PROCESSED via flush only -- part of
        the caller's own transaction (see ``IProcessingUnitOfWork``), not
        committed here. Tenant-scoped exactly as ``update_status``.
        Raises ``NotFoundError`` if no matching row exists."""
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
