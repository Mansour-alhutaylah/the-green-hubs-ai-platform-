"""Pure domain entity for one citation grounding an analysis run's result
in a real, retrieved chunk.

Framework-independent. Never independently constructed by application
code from untrusted input -- ``document_id``/``engagement_id``/
``organization_id`` only ever arrive already-derived from ``chunk_id``'s
real ownership chain (see ``IAnalysisRunRepository.add_citations``),
mirroring ``DocumentChunkEmbedding``'s own lineage-derivation
invariant. ``citation_order`` is the integer suffix of the temporary
``SOURCE_<n>`` key this chunk was assigned during context assembly
(see ``app.services.analysis.rag_analysis``) -- never LLM-supplied.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass
class AnalysisSourceReference:
    id: UUID | None
    analysis_run_id: UUID
    chunk_id: UUID
    document_id: UUID
    engagement_id: UUID
    organization_id: UUID
    chunk_index: int
    char_start: int
    char_end: int
    quoted_snippet: str
    citation_order: int
    relevance_score: Decimal
    created_at: datetime | None
