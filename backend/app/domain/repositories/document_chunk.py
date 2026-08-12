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

MVP Slice 3 (Organization Data Isolation): ``document_chunks`` carries no
``organization_id`` of its own, so ``get_by_document`` now takes a
mandatory keyword-only ``organization_id`` and resolves ownership inside
the query along the full ``document_chunks -> documents -> engagements``
chain. Chunk text is the raw content of a tenant's uploaded document and
is what retrieval ultimately returns, so an unscoped read here would leak
another tenant's document body given only a chunk's parent document id.

``create_many`` needs no scope parameter: each chunk's ``document_id``
comes from a Document the caller already resolved through
``IDocumentRepository.get_for_organization``, and the table's foreign key
to ``documents`` is what binds the row to that lineage.
"""

from abc import ABC, abstractmethod
from typing import Sequence
from uuid import UUID

from app.domain.entities.document_chunk import DocumentChunk


class IDocumentChunkRepository(ABC):
    @abstractmethod
    async def create_many(self, entities: Sequence[DocumentChunk]) -> Sequence[DocumentChunk]: ...

    @abstractmethod
    async def get_by_document(
        self, document_id: UUID, *, organization_id: UUID
    ) -> Sequence[DocumentChunk]:
        """Tenant-scoped chunk read, ordered by ``chunk_index``. A
        document owned by another organization yields an empty sequence,
        indistinguishable from a document that has no chunks."""
        ...

    @abstractmethod
    async def delete(self, entity: DocumentChunk) -> None: ...
