"""Provider-neutral LLM gateway interface for structured completions.

Framework- and SDK-independent: no provider-specific response types
cross this boundary, only ``LLMStructuredResult``. Concrete
implementations (e.g. ``OpenAILLMGateway``) live in
``infrastructure/ai``.

Mirrors ``app.domain.embedding_provider``'s exception hierarchy and
retry-classification philosophy: which exception a concrete
implementation raises determines its own bounded-retry behavior, not a
decision made by callers.

The gateway deliberately carries no knowledge of any caller-specific
output schema (that is a RAG-analysis-domain concern, not a generic-LLM
concern). Schema-level acceptance is expressed via an optional
``validator`` callback passed into ``complete_structured`` -- if it
rejects the first successfully-parsed JSON object, the gateway makes
exactly one additional attempt with the same prompts, then returns
whatever it last received. The gateway makes no further judgment about
whether that final result is acceptable; only the caller (which knows
the real target schema) decides that.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable


class LLMGatewayError(Exception):
    """Base class for all LLM-gateway failures."""


class LLMValidationError(LLMGatewayError):
    """Raised for invalid input (empty prompt) before any provider call.
    Never retried."""


class LLMAuthenticationError(LLMGatewayError):
    """Raised when the provider rejects credentials/configuration. Never
    retried -- retrying an auth failure cannot succeed."""


class LLMProviderTimeoutError(LLMGatewayError):
    """Raised when the provider does not respond within the configured
    timeout. Transient -- eligible for a small bounded retry."""


class LLMProviderUnavailableError(LLMGatewayError):
    """Raised for network-level failures, 429, or 5xx responses.
    Transient -- eligible for a small bounded retry."""


class LLMMalformedResponseError(LLMGatewayError):
    """Raised when the provider's response cannot be parsed into valid
    JSON at all -- distinct from well-formed JSON that fails a caller's
    schema. Never retried by the gateway itself (schema-triggered retry
    is a separate, one-time mechanism -- see ``validator`` above)."""


@dataclass(frozen=True)
class LLMStructuredResult:
    raw_text: str
    parsed: dict
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    model: str
    finish_reason: str | None


class LLMGateway(ABC):
    @abstractmethod
    async def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        validator: Callable[[dict], bool] | None = None,
    ) -> LLMStructuredResult:
        """Requests a JSON-object completion from the provider.

        Raises ``LLMMalformedResponseError`` if the response is not
        valid JSON even after the transient-failure retry budget is
        exhausted. If ``validator`` is supplied and rejects the first
        successfully-parsed JSON object, makes exactly one additional
        attempt with the same prompts before returning whatever it
        received last.
        """
        ...
