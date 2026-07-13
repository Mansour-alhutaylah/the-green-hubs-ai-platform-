"""Unit tests for ``OpenAIEmbeddingProvider`` -- every HTTP call is
intercepted via ``httpx.MockTransport``. No real network call, no live
OpenAI account required.
"""

import httpx
import pytest

from app.core.config import Settings
from app.domain.embedding_provider import (
    EmbeddingAuthenticationError,
    EmbeddingDimensionMismatchError,
    EmbeddingMalformedResponseError,
    EmbeddingProviderUnavailableError,
    EmbeddingResultCountMismatchError,
    EmbeddingValidationError,
)
from app.infrastructure.ai.openai_embedding_provider import OpenAIEmbeddingProvider

DIMENSION = 1536


def _settings(**overrides: object) -> Settings:
    defaults: dict = {
        "openai_api_key": "test-api-key",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimension": DIMENSION,
        "embedding_provider_timeout_seconds": 5.0,
        "embedding_max_batch_size": 100,
        "embedding_max_input_characters": 8000,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _vector(fill: float = 0.001) -> list[float]:
    return [fill] * DIMENSION


def _embeddings_response(texts: list[str], *, shuffle: bool = False) -> dict:
    indexes = list(range(len(texts)))
    if shuffle:
        indexes = indexes[::-1]
    return {
        "data": [
            {"index": i, "embedding": _vector(0.001 * (i + 1)), "object": "embedding"}
            for i in indexes
        ],
        "usage": {"total_tokens": 10 * len(texts)},
        "model": "text-embedding-3-small",
    }


# ---------------------------------------------------------------------------
# Construction / configuration validation
# ---------------------------------------------------------------------------


def test_raises_when_api_key_missing() -> None:
    with pytest.raises(RuntimeError):
        OpenAIEmbeddingProvider(_settings(openai_api_key=None))


def test_raises_when_dimension_is_not_1536() -> None:
    with pytest.raises(RuntimeError):
        OpenAIEmbeddingProvider(_settings(embedding_dimension=768))


def test_raises_when_batch_size_invalid() -> None:
    with pytest.raises(RuntimeError):
        OpenAIEmbeddingProvider(_settings(embedding_max_batch_size=0))


def test_raises_when_timeout_invalid() -> None:
    with pytest.raises(RuntimeError):
        OpenAIEmbeddingProvider(_settings(embedding_provider_timeout_seconds=0))


def test_raises_when_max_input_characters_invalid() -> None:
    with pytest.raises(RuntimeError):
        OpenAIEmbeddingProvider(_settings(embedding_max_input_characters=0))


# ---------------------------------------------------------------------------
# Successful embedding
# ---------------------------------------------------------------------------


async def test_embed_texts_preserves_positional_ordering() -> None:
    texts = ["alpha", "beta", "gamma"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_embeddings_response(texts, shuffle=True))

    provider = OpenAIEmbeddingProvider(_settings(), transport=httpx.MockTransport(handler))

    results = await provider.embed_texts(texts)

    assert [r.text for r in results] == texts
    assert results[0].vector[0] == pytest.approx(0.001)
    assert results[1].vector[0] == pytest.approx(0.002)
    assert results[2].vector[0] == pytest.approx(0.003)


async def test_embed_texts_sends_expected_request_shape() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = request.content
        return httpx.Response(200, json=_embeddings_response(["hello"]))

    provider = OpenAIEmbeddingProvider(_settings(), transport=httpx.MockTransport(handler))

    await provider.embed_texts(["hello"])

    assert captured["url"] == "https://api.openai.com/v1/embeddings"
    assert captured["headers"]["authorization"] == "Bearer test-api-key"
    assert b"hello" in captured["body"]
    assert b"test-api-key" not in captured["body"]  # key never leaks into the payload


async def test_every_vector_has_exactly_the_configured_dimension() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_embeddings_response(["a", "b"]))

    provider = OpenAIEmbeddingProvider(_settings(), transport=httpx.MockTransport(handler))

    results = await provider.embed_texts(["a", "b"])

    assert all(len(r.vector) == DIMENSION for r in results)
    assert all(r.dimension == DIMENSION for r in results)


# ---------------------------------------------------------------------------
# Input validation -- never a network call
# ---------------------------------------------------------------------------


async def test_empty_input_rejected_without_network_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call the network for empty input")

    provider = OpenAIEmbeddingProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(EmbeddingValidationError):
        await provider.embed_texts([])


async def test_oversized_input_rejected_without_network_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call the network for oversized input")

    provider = OpenAIEmbeddingProvider(
        _settings(embedding_max_input_characters=10), transport=httpx.MockTransport(handler)
    )

    with pytest.raises(EmbeddingValidationError):
        await provider.embed_texts(["this text is definitely longer than ten characters"])


async def test_oversized_input_is_never_silently_truncated() -> None:
    """A companion to the rejection test above: confirms the failure is a
    raised error, not silent truncation to a shorter, still-sent string."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=_embeddings_response(["x"]))

    provider = OpenAIEmbeddingProvider(
        _settings(embedding_max_input_characters=10), transport=httpx.MockTransport(handler)
    )

    with pytest.raises(EmbeddingValidationError):
        await provider.embed_texts(["this text is definitely longer than ten characters"])

    assert calls == []


# ---------------------------------------------------------------------------
# Failure mapping and retry policy
# ---------------------------------------------------------------------------


async def test_timeout_is_retried_then_raises_provider_unavailable() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        raise httpx.TimeoutException("timed out")

    provider = OpenAIEmbeddingProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(EmbeddingProviderUnavailableError):
        await provider.embed_texts(["hello"])

    assert call_count == 2  # small, bounded retry -- not unlimited


async def test_authentication_failure_is_never_retried() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(401, json={"error": "invalid api key"})

    provider = OpenAIEmbeddingProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(EmbeddingAuthenticationError):
        await provider.embed_texts(["hello"])

    assert call_count == 1  # never retried


async def test_forbidden_response_maps_to_authentication_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "forbidden"})

    provider = OpenAIEmbeddingProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(EmbeddingAuthenticationError):
        await provider.embed_texts(["hello"])


async def test_unavailable_5xx_is_retried_then_raises() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(503, json={"error": "server error"})

    provider = OpenAIEmbeddingProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(EmbeddingProviderUnavailableError):
        await provider.embed_texts(["hello"])

    assert call_count == 2


async def test_rate_limited_429_is_retried_then_raises() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(429, json={"error": "rate limited"})

    provider = OpenAIEmbeddingProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(EmbeddingProviderUnavailableError):
        await provider.embed_texts(["hello"])

    assert call_count == 2


async def test_malformed_response_is_never_retried() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, content=b"not valid json")

    provider = OpenAIEmbeddingProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(EmbeddingMalformedResponseError):
        await provider.embed_texts(["hello"])

    assert call_count == 1


async def test_missing_data_key_maps_to_malformed_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    provider = OpenAIEmbeddingProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(EmbeddingMalformedResponseError):
        await provider.embed_texts(["hello"])


async def test_result_count_mismatch_is_never_retried() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_embeddings_response(["a"]))  # only 1, for 2 inputs

    provider = OpenAIEmbeddingProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(EmbeddingResultCountMismatchError):
        await provider.embed_texts(["a", "b"])

    assert call_count == 1


async def test_dimension_mismatch_is_never_retried() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}],  # wrong dimension
                "usage": {"total_tokens": 5},
            },
        )

    provider = OpenAIEmbeddingProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(EmbeddingDimensionMismatchError):
        await provider.embed_texts(["hello"])


async def test_generic_400_maps_to_malformed_response_and_is_not_retried() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(400, json={"error": "bad request"})

    provider = OpenAIEmbeddingProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(EmbeddingMalformedResponseError):
        await provider.embed_texts(["hello"])

    assert call_count == 1
