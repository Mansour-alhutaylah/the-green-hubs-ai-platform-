"""Direct tests for the safe RequestContext API."""

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from app.core.request_context import (
    RequestContext,
    enrich_request_context,
    get_request_context,
)


def test_context_is_absent_and_enrichment_is_safe_outside_request() -> None:
    assert get_request_context() is None
    assert enrich_request_context(user_id=uuid4(), organization_id=uuid4()) is None
    assert get_request_context() is None


def test_request_context_is_immutable_and_slotted() -> None:
    context = RequestContext(correlation_id=str(uuid4()))

    with pytest.raises(FrozenInstanceError):
        context.user_id = uuid4()  # type: ignore[misc]

    assert not hasattr(context, "__dict__")
