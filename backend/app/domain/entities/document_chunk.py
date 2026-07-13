"""Pure domain entity for a single chunk of a Document's extracted text.

Framework-independent. Unlike ``ExtractedText`` (which mirrors an older,
nullable reconciled schema), ``document_chunks`` is a brand-new table
(Sprint 3.5 migration ``81a7fdde2d19``) with no historical data to
honor -- ``document_id``, ``chunk_index``, and ``content`` are all
genuinely ``NOT NULL`` at the database level, so they are typed
non-Optional here too. ``id``/``created_at`` remain ``Optional``: both
are server-generated, so ``None`` before persistence.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class DocumentChunk:
    id: UUID | None
    document_id: UUID
    chunk_index: int
    content: str
    created_at: datetime | None
