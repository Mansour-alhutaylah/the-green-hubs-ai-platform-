"""Engagement Management endpoints: create, retrieve, list, update.

Every Engagement must belong to an existing Organization -- enforced in
``EngagementService`` (see its docstring), never here and never in
``IEngagementRepository``.

Sprint 3.5.1 (Tenant Isolation & API Security): every route now requires
``Depends(get_current_user)`` and passes the resulting ``User`` straight
through to ``EngagementService`` -- this router performs no tenant
authorization itself and never trusts a client-supplied
``organization_id`` (whether from the body or the list query parameter)
as the tenant authority; the service always re-derives scope from
``current_user``.

Hard deletion is intentionally not exposed here -- see
``IEngagementRepository``'s and ``EngagementService``'s docstrings.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, get_engagement_service
from app.domain.entities.engagement import Engagement
from app.domain.entities.user import User
from app.schemas.engagement import (
    EngagementCreateRequest,
    EngagementListResponse,
    EngagementResponse,
    EngagementUpdateRequest,
)
from app.services.engagement import EngagementService

router = APIRouter(prefix="/engagements", tags=["engagements"])


def _to_response(engagement: Engagement) -> EngagementResponse:
    # Every engagement reaching this router came from the repository
    # (create/get/list/update all return persisted rows), so id is always
    # populated here even though the domain entity types it as optional
    # to also cover the pre-persistence state.
    assert engagement.id is not None
    return EngagementResponse(
        id=engagement.id,
        organization_id=engagement.organization_id,
        title=engagement.title,
        status=engagement.status,
        created_at=engagement.created_at,
    )


@router.post(
    "",
    response_model=EngagementResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Cannot create an Engagement for another organization"},
        404: {"description": "Organization not found"},
    },
    summary="Create an engagement in the caller's own organization",
)
async def create_engagement(
    payload: EngagementCreateRequest,
    current_user: User = Depends(get_current_user),
    service: EngagementService = Depends(get_engagement_service),
) -> EngagementResponse:
    engagement = await service.create(
        payload.organization_id, payload.title, payload.status, current_user
    )
    return _to_response(engagement)


@router.get(
    "", response_model=EngagementListResponse, summary="List the caller's own Engagements"
)
async def list_engagements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    organization_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    service: EngagementService = Depends(get_engagement_service),
) -> EngagementListResponse:
    items, total = await service.list(
        current_user, page=page, page_size=page_size, organization_id=organization_id
    )
    return EngagementListResponse(
        items=[_to_response(e) for e in items], page=page, page_size=page_size, total=total
    )


@router.get(
    "/{engagement_id}",
    response_model=EngagementResponse,
    responses={404: {"description": "Engagement not found"}},
    summary="Retrieve an Engagement belonging to the caller's own organization",
)
async def get_engagement(
    engagement_id: UUID,
    current_user: User = Depends(get_current_user),
    service: EngagementService = Depends(get_engagement_service),
) -> EngagementResponse:
    engagement = await service.get(engagement_id, current_user)
    return _to_response(engagement)


@router.patch(
    "/{engagement_id}",
    response_model=EngagementResponse,
    responses={
        403: {"description": "Cannot reassign an Engagement to another organization"},
        404: {"description": "Engagement or Organization not found"},
    },
    summary="Update an Engagement belonging to the caller's own organization",
)
async def update_engagement(
    engagement_id: UUID,
    payload: EngagementUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: EngagementService = Depends(get_engagement_service),
) -> EngagementResponse:
    engagement = await service.update(
        engagement_id,
        title=payload.title,
        status=payload.status,
        organization_id=payload.organization_id,
        current_user=current_user,
    )
    return _to_response(engagement)
