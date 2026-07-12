"""Organization Management endpoints: create, retrieve, list, update.

No authentication/authorization is applied yet (scheduled for Sprint 3.3).
Every route depends only on ``OrganizationService`` via
``get_organization_service`` -- a future ``Depends(get_current_user)`` can
be added at the router or route level without touching any handler body,
the service, the repository, or these schemas.

Hard deletion is intentionally not exposed here -- see
``IOrganizationRepository``'s and ``OrganizationService``'s docstrings.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_organization_service
from app.domain.entities.organization import Organization
from app.schemas.organization import (
    OrganizationCreateRequest,
    OrganizationListResponse,
    OrganizationResponse,
    OrganizationUpdateRequest,
)
from app.services.organization import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _to_response(organization: Organization) -> OrganizationResponse:
    # Every organization reaching this router came from the repository
    # (create/get/list/update all return persisted rows), so id is always
    # populated here even though the domain entity types it as optional
    # to also cover the pre-persistence state.
    assert organization.id is not None
    return OrganizationResponse(
        id=organization.id, name=organization.name, created_at=organization.created_at
    )


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an organization",
)
async def create_organization(
    payload: OrganizationCreateRequest,
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationResponse:
    organization = await service.create(payload.name)
    return _to_response(organization)


@router.get("", response_model=OrganizationListResponse, summary="List organizations")
async def list_organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationListResponse:
    items, total = await service.list(page=page, page_size=page_size)
    return OrganizationListResponse(
        items=[_to_response(o) for o in items], page=page, page_size=page_size, total=total
    )


@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
    responses={404: {"description": "Organization not found"}},
    summary="Retrieve an organization by id",
)
async def get_organization(
    organization_id: UUID,
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationResponse:
    organization = await service.get(organization_id)
    return _to_response(organization)


@router.patch(
    "/{organization_id}",
    response_model=OrganizationResponse,
    responses={404: {"description": "Organization not found"}},
    summary="Update an organization",
)
async def update_organization(
    organization_id: UUID,
    payload: OrganizationUpdateRequest,
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationResponse:
    organization = await service.update(organization_id, payload.name)
    return _to_response(organization)
