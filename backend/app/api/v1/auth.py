"""Authenticated-user profile endpoint.

Only ``GET /api/v1/auth/me`` -- Supabase Auth owns login, sessions, and
token issuance entirely. This router only ever verifies an already-issued
Supabase access token and resolves it to the application's
``public.users`` profile. See
``app/infrastructure/security/supabase_jwt.py`` and ``app/api/deps.py``
for the verification/dependency chain this depends on.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.domain.entities.user import User
from app.schemas.auth import UserProfileResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get the authenticated user's profile",
)
async def get_me(current_user: User = Depends(get_current_user)) -> UserProfileResponse:
    return UserProfileResponse(
        id=current_user.id,
        organization_id=current_user.organization_id,
        full_name=current_user.full_name,
        email=current_user.email,
        role=current_user.role,
    )
