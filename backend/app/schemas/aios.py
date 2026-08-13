"""Pydantic models for the AIOS API boundary.

Every inbound model sets ``extra="forbid"``. An unexpected field is an
error, not something silently ignored -- silently ignoring it is how a
client comes to believe that ``{"organization_id": ...}`` in the payload
did something.

That is the second line of defence, not the first: the route scans the
raw payload for forbidden authority fields at any depth before these
models are reached, so a nested attempt gets a specific answer rather
than a generic schema complaint. See
``app.domain.aios.contracts.find_forbidden_field``.
"""

from typing import Any, Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HealthCheckInput(BaseModel):
    """The health check's payload: empty, and required to stay empty.

    A model with no fields and ``extra="forbid"`` accepts exactly ``{}``.
    That is the contract -- a deterministic health check that took input
    would not be deterministic.
    """

    model_config = ConfigDict(extra="forbid")


class HealthCheckInvokeRequest(BaseModel):
    """What a client may send to invoke the health check."""

    model_config = ConfigDict(extra="forbid")

    input: HealthCheckInput = Field(default_factory=HealthCheckInput)


class AIOSResponseMetadata(BaseModel):
    """Execution metadata echoed from the orchestrator.

    Observability and traceability -- deliberately **not** described as
    an audit trail. Nothing here is append-only or tamper-evident, and
    tamper-evident audit remains a separate future control.
    """

    model_config = ConfigDict(extra="ignore")

    execution_id: str | None = None
    workflow_version: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class AIOSInvokeResponse(BaseModel):
    """The product-facing response for one orchestration request."""

    contract_version: str
    request_id: UUID
    correlation_id: UUID
    workflow: str
    status: str
    output: Mapping[str, Any] = Field(default_factory=dict)
    metadata: AIOSResponseMetadata = Field(default_factory=AIOSResponseMetadata)


class VerifyRequestPayload(BaseModel):
    """What the orchestrator forwards for verification.

    ``body_base64`` carries the *exact* bytes the orchestrator received.
    Base64 because raw bytes cannot survive a JSON field, and because a
    re-serialized parsed object would not reproduce the digest that was
    signed.
    """

    model_config = ConfigDict(extra="forbid")

    workflow: str = Field(max_length=128)
    key_id: str = Field(max_length=64)
    timestamp: str = Field(max_length=32)
    request_id: str = Field(max_length=64)
    signature: str = Field(max_length=128)
    body_base64: str


class VerifyRequestResponse(BaseModel):
    """The entire verification answer.

    Two fields when valid, two when not. Nothing here reveals a secret,
    an expected signature, a canonical string, a body digest, whether a
    key id exists, or why verification failed beyond one generic
    category.
    """

    valid: bool
    request_id: UUID | None = None
    category: str | None = None
