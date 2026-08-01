"""OpenAI chat completions via narrow ``httpx`` calls -- not the
``openai`` SDK, mirroring ``OpenAIEmbeddingProvider``'s precedent for
keeping this codebase's dependency tree small.

Validates configuration at construction time (fail fast, matching
``OpenAIEmbeddingProvider``): a missing API key, model, or invalid
timeout/max-tokens/temperature setting raises immediately, never
lazily on first use.

Retry policy: a small, bounded number of attempts for transient
failures only (timeout, network error, 429, 5xx); authentication and
malformed-response failures are never retried at that layer. Separately,
if the caller supplies a ``validator`` and it rejects the first
successfully-parsed JSON object, exactly one additional full attempt is
made -- a deliberate, distinct retry budget from the transient one,
since chat completions are less mechanically reliable in JSON mode than
the embeddings endpoint even at low temperature.
"""

import json
import logging
from typing import Callable

import httpx

from app.core.config import Settings, resolve_ai_credentials
from app.domain.llm_gateway import (
    LLMAuthenticationError,
    LLMGateway,
    LLMMalformedResponseError,
    LLMProviderUnavailableError,
    LLMStructuredResult,
    LLMValidationError,
)

logger = logging.getLogger(__name__)

_MAX_TRANSIENT_ATTEMPTS = 2


class OpenAILLMGateway(LLMGateway):
    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        api_key, base_url = resolve_ai_credentials(settings)
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY or OPENROUTER_API_KEY is required to construct OpenAILLMGateway"
            )
        if not settings.openai_model:
            raise RuntimeError("openai_model is required to construct OpenAILLMGateway")
        if settings.llm_provider_timeout_seconds <= 0:
            raise RuntimeError("llm_provider_timeout_seconds must be positive")
        if settings.llm_max_tokens <= 0:
            raise RuntimeError("llm_max_tokens must be positive")
        if not (0.0 <= settings.llm_temperature <= 2.0):
            raise RuntimeError("llm_temperature must be between 0.0 and 2.0")

        self._api_key = api_key
        self._chat_completions_url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = settings.openai_model
        self._timeout = settings.llm_provider_timeout_seconds
        self._max_tokens = settings.llm_max_tokens
        self._temperature = settings.llm_temperature
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    async def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        validator: Callable[[dict], bool] | None = None,
    ) -> LLMStructuredResult:
        if not system_prompt.strip() or not user_prompt.strip():
            raise LLMValidationError("system_prompt and user_prompt must not be empty")

        result = await self._call_once(system_prompt, user_prompt)
        if validator is not None and not validator(result.parsed):
            logger.warning("LLM response failed caller validation, retrying once")
            result = await self._call_once(system_prompt, user_prompt)
        return result

    async def _call_once(self, system_prompt: str, user_prompt: str) -> LLMStructuredResult:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_exc: Exception | None = None
        for _attempt in range(_MAX_TRANSIENT_ATTEMPTS):
            try:
                async with self._client() as client:
                    response = await client.post(
                        self._chat_completions_url, json=payload, headers=headers
                    )
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning("LLM gateway request failed, will retry: %r", exc)
                continue

            if response.status_code in (401, 403):
                raise LLMAuthenticationError("LLM provider rejected the request")
            if response.status_code == 429 or response.status_code >= 500:
                last_exc = LLMProviderUnavailableError(
                    f"LLM provider returned status {response.status_code}"
                )
                logger.warning(
                    "LLM provider returned status %s, will retry", response.status_code
                )
                continue
            if response.status_code >= 400:
                raise LLMMalformedResponseError(
                    f"LLM provider returned status {response.status_code}"
                )

            return self._parse_response(response)

        raise LLMProviderUnavailableError(
            "LLM provider unavailable after retries"
        ) from last_exc

    def _parse_response(self, response: httpx.Response) -> LLMStructuredResult:
        try:
            body = response.json()
            choice = body["choices"][0]
            content = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMMalformedResponseError(
                "LLM provider returned an unexpected response shape"
            ) from exc

        try:
            parsed = json.loads(content)
        except (ValueError, TypeError) as exc:
            raise LLMMalformedResponseError(
                "LLM provider did not return valid JSON content"
            ) from exc

        if not isinstance(parsed, dict):
            raise LLMMalformedResponseError("LLM provider JSON content was not an object")

        usage = body.get("usage") or {}
        return LLMStructuredResult(
            raw_text=content,
            parsed=parsed,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            model=body.get("model", self._model),
            finish_reason=choice.get("finish_reason"),
        )
