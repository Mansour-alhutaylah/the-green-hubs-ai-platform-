"""Abstract repository interface for ``ExtractedText`` records.

Deliberately does not extend the generic ``IRepository`` CRUD contract
used by aggregate roots (Organization, Engagement, Document, User):
extracted text is a write-once child record attached to a Document (the
new ``UNIQUE(document_id)`` constraint enforces exactly one per
Document), not an independently manageable aggregate -- a full CRUD
surface (``list``, ``update``, a generic ``get``-by-own-id) would be
speculative, unused code for this sprint's scope. ``get_by_document`` is
the only read this sprint needs; ``delete`` exists solely for
integration-test cleanup.

``create()`` must flush, not commit: it is written into the same
processing transaction as the accompanying ``document_chunks``, owned by
``DocumentProcessingService`` via ``IProcessingUnitOfWork`` -- see
``SQLAlchemyExtractedTextRepository``'s docstring.

MVP Slice 3 (Organization Data Isolation): ``get_by_document`` takes a
mandatory keyword-only ``organization_id`` and resolves ownership inside
the query via ``extracted_text -> documents -> engagements``. This row
holds the full normalized text of a tenant's document -- the single
largest disclosure on this table -- so it is scoped even though no
current use case reads it; leaving the one read path unscoped would make
the first future caller a cross-tenant leak by default.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.extracted_text import ExtractedText


class IExtractedTextRepository(ABC):
    @abstractmethod
    async def create(self, entity: ExtractedText) -> ExtractedText: ...

    @abstractmethod
    async def get_by_document(
        self, document_id: UUID, *, organization_id: UUID
    ) -> ExtractedText | None:
        """Tenant-scoped read. Returns ``None`` for a document owned by
        another organization, indistinguishable from one that has no
        extracted text yet."""
        ...

    @abstractmethod
    async def delete(self, entity: ExtractedText) -> None: ...
