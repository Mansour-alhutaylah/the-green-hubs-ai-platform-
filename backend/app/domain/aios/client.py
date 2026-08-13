"""Provider-neutral port for dispatching an orchestration request.

Framework- and vendor-independent: no ``httpx`` type and no n8n concept
crosses this boundary, only ``bytes`` in and a parsed mapping out.
Concrete implementations live in ``infrastructure/aios``.

Mirrors ``app.domain.llm_gateway``'s exception hierarchy and its
retry-classification philosophy deliberately: *which* exception an
implementation raises determines its own bounded-retry behaviour, rather
than callers inspecting status codes and deciding for themselves. A
service catching :class:`AIOSTimeoutError` knows the request may have
been delivered; one catching :class:`AIOSUnavailableError` knows the
attempt budget is spent. Neither needs to know what an HTTP 429 is.

The port takes **bytes**, not a dictionary, and that is the single most
important thing about it. The envelope is serialized exactly once, by
the caller, and those same bytes are both signed and transmitted. An
implementation that accepted a mapping would have to serialize it again,
and two serializations of one object are not guaranteed to be the same
bytes across languages or library versions -- which is precisely the
class of bug this signing scheme exists to make impossible.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping
from uuid import UUID

from app.domain.aios.workflows import RegisteredWorkflow


class AIOSClientError(Exception):
    """Base class for every orchestration-dispatch failure."""


class AIOSTimeoutError(AIOSClientError):
    """The orchestrator did not respond within the bounded timeout.

    Transient. The attempt budget is already spent by the time this is
    raised -- callers must not retry it themselves.
    """


class AIOSUnavailableError(AIOSClientError):
    """Network-level failure, or a 5xx after the retry budget is spent.

    Transient in nature, terminal by the time a caller sees it.
    """


class AIOSUnexpectedResponseError(AIOSClientError):
    """The orchestrator answered, and the answer cannot be trusted.

    Covers a 4xx (the orchestrator rejected *our* request -- a
    configuration or signature problem that retrying cannot fix), a
    non-JSON body, and a well-formed body whose identifiers do not match
    the request that was sent. Never retried.
    """


@dataclass(frozen=True, slots=True)
class AIOSDispatch:
    """One signed, ready-to-transmit orchestration request."""

    workflow: RegisteredWorkflow
    #: The exact bytes that were signed and will be transmitted.
    envelope_bytes: bytes
    request_id: UUID
    correlation_id: UUID


class AIOSClient(ABC):
    """Dispatches a signed envelope to the orchestration layer."""

    @abstractmethod
    async def invoke(self, dispatch: AIOSDispatch) -> Mapping[str, Any]:
        """Send ``dispatch`` and return the parsed response body.

        Returns the orchestrator's response as a plain mapping. Judging
        whether that response is a *valid* contract is the caller's job,
        not the transport's.

        Raises:
            AIOSTimeoutError: no response within the bounded timeout.
            AIOSUnavailableError: network failure or 5xx after retries.
            AIOSUnexpectedResponseError: 4xx, unparseable body, or a body
                that is not a JSON object.
        """
        ...
