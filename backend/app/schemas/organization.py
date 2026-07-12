"""Pydantic request/response models for Organization Management endpoints.

``_OrganizationNameField`` is the single source of truth for name
validation, shared by create and update requests so the rule (strip, then
reject blank) is defined once. Because ``name`` is declared as a required,
plain ``str`` (never ``Optional[str]``) on both requests, ordinary Pydantic
v2 validation alone -- with no extra branching -- already rejects an
omitted field, an explicit ``null``, and a blank/whitespace-only string,
all with 422: a field with no default is required (rejects omission), a
``str`` field rejects ``None`` (rejects explicit null), and the field
validator rejects a value that strips down to nothing (rejects blank/
whitespace-only).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class _OrganizationNameField(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def _strip_and_reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped


class OrganizationCreateRequest(_OrganizationNameField):
    pass


class OrganizationUpdateRequest(_OrganizationNameField):
    pass


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime | None


class OrganizationListResponse(BaseModel):
    items: list[OrganizationResponse]
    page: int
    page_size: int
    total: int
