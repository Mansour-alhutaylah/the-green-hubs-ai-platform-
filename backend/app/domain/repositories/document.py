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
"""

from abc import ABC, abstractmethod
from typing import Sequence
from uuid import UUID

from app.domain.entities.document import Document
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
