"""Abstract repository interface for ``DocumentChunk`` records.

Deliberately does not extend the generic ``IRepository`` CRUD contract --
same reasoning as ``IExtractedTextRepository``: chunks are write-once
children of a Document, not an independently manageable aggregate.
``create_many`` is bulk by design (one round-trip for all of a
Document's chunks, not one commit per chunk); ``get_by_document`` is the
only read this sprint needs; ``delete`` exists solely for
integration-test cleanup.

``create_many()`` must flush, not commit -- see
``SQLAlchemyDocumentChunkRepository``'s docstring.
"""

from abc import ABC, abstractmethod
from typing import Sequence
from uuid import UUID

from app.domain.entities.document_chunk import DocumentChunk


class IDocumentChunkRepository(ABC):
    @abstractmethod
    async def create_many(self, entities: Sequence[DocumentChunk]) -> Sequence[DocumentChunk]: ...

    @abstractmethod
    async def get_by_document(self, document_id: UUID) -> Sequence[DocumentChunk]: ...

    @abstractmethod
    async def delete(self, entity: DocumentChunk) -> None: ...
