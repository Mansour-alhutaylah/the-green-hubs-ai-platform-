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
"""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.extracted_text import ExtractedText


class IExtractedTextRepository(ABC):
    @abstractmethod
    async def create(self, entity: ExtractedText) -> ExtractedText: ...

    @abstractmethod
    async def get_by_document(self, document_id: UUID) -> ExtractedText | None: ...

    @abstractmethod
    async def delete(self, entity: ExtractedText) -> None: ...
