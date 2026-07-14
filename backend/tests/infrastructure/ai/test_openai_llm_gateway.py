"""Unit tests for ``OpenAILLMGateway`` -- every HTTP call is intercepted
via ``httpx.MockTransport``. No real network call, no live OpenAI
account required.
"""

import json

import httpx
import pytest

from app.core.config import Settings
from app.domain.llm_gateway import (
    LLMAuthenticationError,
    LLMMalformedResponseError,
    LLMProviderUnavailableError,
    LLMValidationError,
)
from app.infrastructure.ai.openai_llm_gateway import OpenAILLMGateway


def _settings(**overrides: object) -> Settings:
    defaults: dict = {
        "openai_api_key": "test-api-key",
        "openai_model": "gpt-4o-mini",
        "llm_provider_timeout_seconds": 5.0,
        "llm_max_tokens": 1500,
        "llm_temperature": 0.1,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _chat_response(content: dict, *, model: str = "gpt-4o-mini") -> dict:
    return {
        "model": model,
        "choices": [
            {"message": {"content": json.dumps(content)}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


# ---------------------------------------------------------------------------
# Construction / configuration validation
# ---------------------------------------------------------------------------


def test_raises_when_api_key_missing() -> None:
    with pytest.raises(RuntimeError):
        OpenAILLMGateway(_settings(openai_api_key=None))


def test_raises_when_model_missing() -> None:
    with pytest.raises(RuntimeError):
        OpenAILLMGateway(_settings(openai_model=""))


def test_raises_when_timeout_invalid() -> None:
    with pytest.raises(RuntimeError):
        OpenAILLMGateway(_settings(llm_provider_timeout_seconds=0))


def test_raises_when_max_tokens_invalid() -> None:
    with pytest.raises(RuntimeError):
        OpenAILLMGateway(_settings(llm_max_tokens=0))


def test_raises_when_temperature_out_of_range() -> None:
    with pytest.raises(RuntimeError):
        OpenAILLMGateway(_settings(llm_temperature=3.0))


# ---------------------------------------------------------------------------
# Successful completion
# ---------------------------------------------------------------------------


async def test_complete_structured_returns_parsed_json_and_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_chat_response({"executive_summary": "ok"}))

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    result = await gateway.complete_structured(system_prompt="sys", user_prompt="user")

    assert result.parsed == {"executive_summary": "ok"}
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 20
    assert result.total_tokens == 30
    assert result.finish_reason == "stop"


async def test_sends_expected_request_shape() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_chat_response({"ok": True}))

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    await gateway.complete_structured(system_prompt="system rules", user_prompt="the question")

    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer test-api-key"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["body"]["messages"] == [
        {"role": "system", "content": "system rules"},
        {"role": "user", "content": "the question"},
    ]
    assert "test-api-key" not in json.dumps(captured["body"])  # key never leaks into the payload


# ---------------------------------------------------------------------------
# Input validation -- never a network call
# ---------------------------------------------------------------------------


async def test_empty_system_prompt_rejected_without_network_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call the network for empty prompts")

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(LLMValidationError):
        await gateway.complete_structured(system_prompt="  ", user_prompt="question")


async def test_empty_user_prompt_rejected_without_network_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call the network for empty prompts")

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(LLMValidationError):
        await gateway.complete_structured(system_prompt="system", user_prompt="   ")


# ---------------------------------------------------------------------------
# Failure mapping and transient-retry policy
# ---------------------------------------------------------------------------


async def test_timeout_is_retried_then_raises_provider_unavailable() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        raise httpx.TimeoutException("timed out")

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(LLMProviderUnavailableError):
        await gateway.complete_structured(system_prompt="sys", user_prompt="user")

    assert call_count == 2  # small, bounded retry -- not unlimited


async def test_authentication_failure_is_never_retried() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(401, json={"error": "invalid api key"})

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(LLMAuthenticationError):
        await gateway.complete_structured(system_prompt="sys", user_prompt="user")

    assert call_count == 1


async def test_forbidden_response_maps_to_authentication_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "forbidden"})

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(LLMAuthenticationError):
        await gateway.complete_structured(system_prompt="sys", user_prompt="user")


async def test_rate_limited_429_is_retried_then_raises() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(429, json={"error": "rate limited"})

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(LLMProviderUnavailableError):
        await gateway.complete_structured(system_prompt="sys", user_prompt="user")

    assert call_count == 2


async def test_unavailable_5xx_is_retried_then_raises() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(503, json={"error": "server error"})

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(LLMProviderUnavailableError):
        await gateway.complete_structured(system_prompt="sys", user_prompt="user")

    assert call_count == 2


async def test_non_json_content_is_malformed_and_never_transient_retried() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, content=b"not valid json")

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(LLMMalformedResponseError):
        await gateway.complete_structured(system_prompt="sys", user_prompt="user")

    assert call_count == 1


async def test_non_json_message_content_is_malformed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "gpt-4o-mini",
                "choices": [{"message": {"content": "not JSON at all"}, "finish_reason": "stop"}],
                "usage": {},
            },
        )

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(LLMMalformedResponseError):
        await gateway.complete_structured(system_prompt="sys", user_prompt="user")


async def test_non_object_json_content_is_malformed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "gpt-4o-mini",
                "choices": [{"message": {"content": "[1, 2, 3]"}, "finish_reason": "stop"}],
                "usage": {},
            },
        )

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(LLMMalformedResponseError):
        await gateway.complete_structured(system_prompt="sys", user_prompt="user")


async def test_missing_choices_key_is_malformed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(LLMMalformedResponseError):
        await gateway.complete_structured(system_prompt="sys", user_prompt="user")


async def test_generic_400_maps_to_malformed_response_and_is_not_retried() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(400, json={"error": "bad request"})

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(LLMMalformedResponseError):
        await gateway.complete_structured(system_prompt="sys", user_prompt="user")

    assert call_count == 1


# ---------------------------------------------------------------------------
# Validator-driven one-time retry
# ---------------------------------------------------------------------------


async def test_validator_rejection_triggers_exactly_one_more_attempt() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        payload = {"attempt": call_count}
        return httpx.Response(200, json=_chat_response(payload))

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    result = await gateway.complete_structured(
        system_prompt="sys", user_prompt="user", validator=lambda parsed: parsed["attempt"] == 2
    )

    assert call_count == 2
    assert result.parsed == {"attempt": 2}


async def test_validator_rejecting_both_attempts_returns_last_result_without_raising() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_chat_response({"attempt": call_count}))

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    result = await gateway.complete_structured(
        system_prompt="sys", user_prompt="user", validator=lambda parsed: False
    )

    assert call_count == 2
    assert result.parsed == {"attempt": 2}


async def test_no_validator_makes_exactly_one_call() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_chat_response({"ok": True}))

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    await gateway.complete_structured(system_prompt="sys", user_prompt="user")

    assert call_count == 1


async def test_validator_accepting_first_attempt_makes_exactly_one_call() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_chat_response({"ok": True}))

    gateway = OpenAILLMGateway(_settings(), transport=httpx.MockTransport(handler))

    await gateway.complete_structured(
        system_prompt="sys", user_prompt="user", validator=lambda parsed: True
    )

    assert call_count == 1
