"""Abstract, narrowly-scoped transaction boundary for
``DocumentProcessingService``'s multi-write persistence step: an
``extracted_text`` insert, a bulk ``document_chunks`` insert, and the
Document's status update to ``PROCESSED`` must all land in one
transaction, or none of them do.

This is a deliberate, small, explicit deviation from "the service
depends only on repository interfaces" -- scoped to this one
orchestration, not a general pattern applied elsewhere in this
codebase. ``IExtractedTextRepository.create()`` and
``IDocumentChunkRepository.create_many()`` flush rather than commit
specifically so this interface's ``commit()``/``rollback()`` govern
their durability, not the repositories themselves.
"""

from abc import ABC, abstractmethod


class IProcessingUnitOfWork(ABC):
    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
