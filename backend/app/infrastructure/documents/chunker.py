"""Boundary-aware text chunking for embedding and retrieval pipelines.

Framework-agnostic: no FastAPI, SQLAlchemy, OpenAI, RAG, or vector-store
imports. Given plain text, returns ordered chunks -- nothing more.

Migrated from the Hemaya reference project's ``backend/chunker.py``. The
splitting algorithm (paragraph -> line -> sentence -> word -> hard cut) is
preserved as-is: it has no compliance-specific behaviour, so it applies
unchanged to sustainability documents. Two Hemaya functions were intentionally
left behind: ``prepare_chunks_for_storage`` (assigns DB-facing policy/chunk
ids -- persistence concern, not chunking) and ``chunk_text_segments``
(attributes chunks back to page/paragraph numbers -- it needs an extractor
that returns per-page segments, which this platform's text_extractor does not
yet produce).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 100

_BOUNDARY_SEPARATORS = ("\n\n", "\n", ". ", " ")
_HARD_SPLIT_LOOKAHEAD = 50
_HARD_SPLIT_WHITESPACE = " \n\t"


@dataclass(frozen=True)
class TextChunk:
    """A single ordered slice of a larger document."""

    chunk_index: int
    text: str
    char_start: int
    char_end: int


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[TextChunk]:
    """Split ``text`` into overlapping chunks of ~``chunk_size`` characters.

    Splits preferentially at paragraph, then line, then sentence, then word
    boundaries, so sentences are only broken when no better boundary exists
    within the window. Text content is never modified (no lowercasing, no
    stripping).

    Args:
        text: Plain text to split. Empty or whitespace-only text yields no
            chunks.
        chunk_size: Target maximum size of each chunk, in characters.
        chunk_overlap: Number of characters each chunk repeats from the tail
            of the previous chunk, to preserve context across boundaries.

    Returns:
        Ordered list of :class:`TextChunk`, sequentially indexed from 0.

    Raises:
        ValueError: ``chunk_size`` is not positive, or ``chunk_overlap`` is
            negative or not smaller than ``chunk_size``.
    """
    _validate_chunk_config(chunk_size, chunk_overlap)

    if not text or not text.strip():
        return []

    if len(text) <= chunk_size:
        return [TextChunk(chunk_index=0, text=text, char_start=0, char_end=len(text))]

    raw_chunks: list[tuple[str, int, int]] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            tail = text[start:]
            if tail.strip():
                raw_chunks.append((tail, start, len(text)))
            break

        # The split point must be strictly past (start + chunk_overlap) so
        # the next window's start (= split_point - chunk_overlap) is always
        # greater than start, guaranteeing forward progress.
        min_advance = start + chunk_overlap + 1
        split_point = _find_split_point(text, start, end, min_advance)

        chunk = text[start:split_point]
        if chunk.strip():
            raw_chunks.append((chunk, start, split_point))

        next_start = split_point - chunk_overlap
        if next_start <= start:
            next_start = split_point
        start = next_start

    logger.debug(
        "Split %d-character document into %d chunk(s) (chunk_size=%d, chunk_overlap=%d)",
        len(text),
        len(raw_chunks),
        chunk_size,
        chunk_overlap,
    )

    return [
        TextChunk(chunk_index=i, text=chunk_text_value, char_start=char_start, char_end=char_end)
        for i, (chunk_text_value, char_start, char_end) in enumerate(raw_chunks)
    ]


def _validate_chunk_config(chunk_size: int, chunk_overlap: int) -> None:
    """Fail loudly on a nonsensical configuration instead of degrading silently."""
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")
    if chunk_overlap < 0:
        raise ValueError(f"chunk_overlap must be non-negative, got {chunk_overlap}")
    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) must be smaller than chunk_size ({chunk_size})"
        )


def _find_split_point(text: str, start: int, end: int, min_advance: int) -> int:
    """Return the best index to split at within ``text[start:end]``.

    Priority (highest to lowest):
        1. Paragraph boundary  ("\\n\\n")
        2. Line boundary       ("\\n")
        3. Sentence boundary   (". ")
        4. Word boundary       (" ")
        5. Hard cut at ``end`` -- last resort, walks forward to the next
           whitespace so a split rarely lands mid-word.

    The returned index is always greater than ``min_advance`` so the caller
    always advances.
    """
    window = text[start:end]

    for separator in _BOUNDARY_SEPARATORS:
        pos = window.rfind(separator)
        if pos == -1:
            continue
        split_at = start + pos + len(separator)
        if split_at > min_advance:
            return split_at

    # Hard fallback: scan forward from `end` for the next whitespace so we
    # never split inside a word (handles URLs, long unbroken tokens, etc.).
    for i in range(end, min(end + _HARD_SPLIT_LOOKAHEAD, len(text))):
        if text[i] in _HARD_SPLIT_WHITESPACE:
            return i + 1

    return end  # Absolute last resort: unavoidable mid-word split.
