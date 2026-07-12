"""Pydantic request/response models for Engagement Management endpoints.

``EngagementCreateRequest`` requires ``organization_id``/``title`` and
makes ``status`` optional with a ``"planning"`` default -- omitting
``status`` uses the default untouched (Pydantic v2 does not validate
defaults unless ``validate_default`` is set), while an explicit
``{"status": null}`` fails ``status``'s plain-``str`` type check with 422,
correctly distinguishing "omitted" from "explicitly null" without any
extra machinery.

``EngagementUpdateRequest`` needs the same distinction for three fields at
once, plus "no field supplied at all" rejected outright. Each field is
declared ``X | None = None`` so an omission is silently accepted (default,
unvalidated) while an explicitly supplied ``null`` is validated and
rejected by that field's validator. ``model_fields_set`` (populated from
exactly the keys present in the request body) is checked in an
``model_validator(mode="after")`` to reject an empty ``{}`` body -- since
a field validator failure short-circuits model-level validation, a
`{"title": null}` body still 422s on `title`'s own null-check rather than
the "at least one field" check, which is the correct, more specific error.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


def _strip_or_raise(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank")
    return stripped


class EngagementCreateRequest(BaseModel):
    organization_id: UUID
    title: str = Field(min_length=1, max_length=255)
    status: str = Field(default="planning", max_length=50)

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return _strip_or_raise(value, "title")

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        return _strip_or_raise(value, "status")


class EngagementUpdateRequest(BaseModel):
    organization_id: UUID | None = None
    title: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, max_length=50)

    @field_validator("organization_id")
    @classmethod
    def _validate_organization_id(cls, value: UUID | None) -> UUID:
        if value is None:
            raise ValueError("organization_id must not be null")
        return value

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("title must not be null")
        return _strip_or_raise(value, "title")

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("status must not be null")
        return _strip_or_raise(value, "status")

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> "EngagementUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("at least one field must be supplied")
        return self


class EngagementResponse(BaseModel):
    id: UUID
    organization_id: UUID | None
    title: str
    status: str | None
    created_at: datetime | None


class EngagementListResponse(BaseModel):
    items: list[EngagementResponse]
    page: int
    page_size: int
    total: int
