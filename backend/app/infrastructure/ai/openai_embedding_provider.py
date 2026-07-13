"""OpenAI embeddings via narrow ``httpx`` calls -- not the ``openai`` SDK,
mirroring ``SupabaseDocumentStorage``'s existing precedent for keeping
this codebase's dependency tree small.

Validates configuration at construction time (fail fast, matching
``SupabaseDocumentStorage.__init__``): a missing API key, an unsupported
dimension, or an invalid batch/timeout/input-size setting raises
immediately, never lazily on first use.

Retry policy: a small, bounded number of attempts, and only for
transient failures (timeout, network error, 429, 5xx) -- authentication,
validation, malformed-response, and count/dimension-mismatch failures
are never retried (see ``app.domain.embedding_provider``'s exception
hierarchy for which is which).
"""

import logging
from typing import Sequence

import httpx

from app.core.config import Settings
from app.domain.embedding_provider import (
    EmbeddingAuthenticationError,
    EmbeddingDimensionMismatchError,
    EmbeddingMalformedResponseError,
    EmbeddingProvider,
    EmbeddingProviderUnavailableError,
    EmbeddingResult,
    EmbeddingResultCountMismatchError,
    EmbeddingValidationError,
)

logger = logging.getLogger(__name__)

_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
_MAX_ATTEMPTS = 2


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required to construct OpenAIEmbeddingProvider")
        if settings.embedding_dimension != 1536:
            raise RuntimeError(
                f"Unsupported embedding_dimension {settings.embedding_dimension}: "
                f"only 1536 is supported this sprint"
            )
        if settings.embedding_max_batch_size <= 0:
            raise RuntimeError("embedding_max_batch_size must be positive")
        if settings.embedding_provider_timeout_seconds <= 0:
            raise RuntimeError("embedding_provider_timeout_seconds must be positive")
        if settings.embedding_max_input_characters <= 0:
            raise RuntimeError("embedding_max_input_characters must be positive")

        self._api_key = settings.openai_api_key
        self._model = settings.embedding_model
        self._dimension = settings.embedding_dimension
        self._timeout = settings.embedding_provider_timeout_seconds
        self._max_input_characters = settings.embedding_max_input_characters
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    async def embed_texts(self, texts: Sequence[str]) -> Sequence[EmbeddingResult]:
        if not texts:
            raise EmbeddingValidationError("texts must not be empty")
        for value in texts:
            if len(value) > self._max_input_characters:
                raise EmbeddingValidationError(
                    f"input exceeds maximum of {self._max_input_characters} characters"
                )

        payload = {"model": self._model, "input": list(texts)}
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_exc: Exception | None = None
        for _attempt in range(_MAX_ATTEMPTS):
            try:
                async with self._client() as client:
                    response = await client.post(_EMBEDDINGS_URL, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning("Embedding provider request failed, will retry: %r", exc)
                continue

            if response.status_code in (401, 403):
                raise EmbeddingAuthenticationError("Embedding provider rejected the request")
            if response.status_code == 429 or response.status_code >= 500:
                last_exc = EmbeddingProviderUnavailableError(
                    f"Embedding provider returned status {response.status_code}"
                )
                logger.warning(
                    "Embedding provider returned status %s, will retry", response.status_code
                )
                continue
            if response.status_code >= 400:
                raise EmbeddingMalformedResponseError(
                    f"Embedding provider returned status {response.status_code}"
                )

            return self._parse_response(response, texts)

        raise EmbeddingProviderUnavailableError(
            "Embedding provider unavailable after retries"
        ) from last_exc

    def _parse_response(
        self, response: httpx.Response, texts: Sequence[str]
    ) -> Sequence[EmbeddingResult]:
        try:
            body = response.json()
            data = body["data"]
        except (ValueError, KeyError, TypeError) as exc:
            raise EmbeddingMalformedResponseError(
                "Embedding provider returned an unexpected response shape"
            ) from exc

        if not isinstance(data, list) or len(data) != len(texts):
            raise EmbeddingResultCountMismatchError(
                f"Expected {len(texts)} embeddings, got "
                f"{len(data) if isinstance(data, list) else 'a malformed response'}"
            )

        try:
            ordered = sorted(data, key=lambda item: item["index"])
        except (KeyError, TypeError) as exc:
            raise EmbeddingMalformedResponseError(
                "Embedding provider response is missing a positional index"
            ) from exc

        results: list[EmbeddingResult] = []
        for text_value, item in zip(texts, ordered):
            vector = item.get("embedding")
            if not isinstance(vector, list) or len(vector) != self._dimension:
                actual = len(vector) if isinstance(vector, list) else "invalid"
                raise EmbeddingDimensionMismatchError(
                    f"Expected a {self._dimension}-dimensional vector, got {actual}"
                )
            results.append(
                EmbeddingResult(text=text_value, vector=vector, dimension=len(vector))
            )
        return results
