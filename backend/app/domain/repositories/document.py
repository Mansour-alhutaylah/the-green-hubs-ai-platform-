"""Abstract repository interface for ``Document`` entities.

Extends the generic ``IRepository`` CRUD contract with query shapes that a
generic interface cannot express: filtering documents by engagement, and
transitioning processing status without forcing callers to hand-construct a
full entity first. Concrete persistence (SQLAlchemy) lives in
``infrastructure/repositories`` and will implement this interface -- nothing
here may depend on a database or web framework.
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
