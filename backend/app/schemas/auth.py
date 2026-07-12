"""Pydantic response model for the authenticated-user profile endpoint."""

from uuid import UUID

from pydantic import BaseModel


class UserProfileResponse(BaseModel):
    id: UUID
    organization_id: UUID | None
    full_name: str
    email: str
    role: str | None
