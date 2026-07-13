"""Provider-neutral embedding interface.

Framework- and SDK-independent: no provider-specific response types cross
this boundary, only ``EmbeddingResult``. Concrete implementations (e.g.
``OpenAIEmbeddingProvider``) live in ``infrastructure/ai``.

Exception hierarchy distinguishes retryable transient failures
(``EmbeddingProviderTimeoutError``, ``EmbeddingProviderUnavailableError``)
from failures a concrete implementation must never retry
(``EmbeddingAuthenticationError``, ``EmbeddingMalformedResponseError``,
``EmbeddingResultCountMismatchError``, ``EmbeddingDimensionMismatchError``,
``EmbeddingValidationError``) -- which class an implementation raises is
what determines its own bounded-retry behavior, not a decision made by
callers of this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence


class EmbeddingProviderError(Exception):
    """Base class for all embedding-provider failures."""


class EmbeddingValidationError(EmbeddingProviderError):
    """Raised for invalid input (empty batch, oversized individual text)
    before any provider call is made. Never retried."""


class EmbeddingAuthenticationError(EmbeddingProviderError):
    """Raised when the provider rejects credentials/configuration. Never
    retried -- retrying an auth failure cannot succeed."""


class EmbeddingProviderTimeoutError(EmbeddingProviderError):
    """Raised when the provider does not respond within the configured
    timeout. Transient -- eligible for a small bounded retry."""


class EmbeddingProviderUnavailableError(EmbeddingProviderError):
    """Raised for network-level failures, 429, or 5xx responses.
    Transient -- eligible for a small bounded retry."""


class EmbeddingMalformedResponseError(EmbeddingProviderError):
    """Raised when the provider's response cannot be parsed into the
    expected shape. Never retried -- the response is a proven bad shape,
    not a transient condition."""


class EmbeddingResultCountMismatchError(EmbeddingProviderError):
    """Raised when the provider returns a different number of embeddings
    than texts requested. Never retried; fails the whole batch."""


class EmbeddingDimensionMismatchError(EmbeddingProviderError):
    """Raised when a returned vector's length does not match the
    configured embedding dimension. Never retried."""


@dataclass(frozen=True)
class EmbeddingResult:
    text: str
    vector: Sequence[float]
    dimension: int
    token_count: int | None = None


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed_texts(self, texts: Sequence[str]) -> Sequence[EmbeddingResult]:
        """Embeds ``texts`` in as few provider requests as the
        implementation's configured batch size allows. Results are
        returned in the exact same order as ``texts`` (positional
        correspondence, not provider-reported order alone -- an
        implementation must re-sort by the provider's own declared index
        if it exposes one). Raises ``EmbeddingValidationError`` for an
        empty ``texts`` sequence or any individually oversized entry,
        before any network call is made."""
        ...
