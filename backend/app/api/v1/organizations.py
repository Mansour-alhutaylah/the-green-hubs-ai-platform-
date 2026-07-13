"""Organization Management endpoints: create, retrieve, list, update.

Sprint 3.5.1 (Tenant Isolation & API Security): every route now requires
``Depends(get_current_user)`` and passes the resulting ``User`` straight
through to ``OrganizationService`` -- this router performs no tenant
authorization itself (that lives in the service, see its docstring) and
never trusts a client-supplied id as the tenant authority.

Hard deletion is intentionally not exposed here -- see
``IOrganizationRepository``'s and ``OrganizationService``'s docstrings.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, get_organization_service
from app.domain.entities.organization import Organization
from app.domain.entities.user import User
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
    responses={403: {"description": "Organization creation is not available in this phase"}},
    summary="Create an organization (temporarily disabled)",
)
async def create_organization(
    payload: OrganizationCreateRequest,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationResponse:
    organization = await service.create(payload.name, current_user)
    return _to_response(organization)


@router.get("", response_model=OrganizationListResponse, summary="List the caller's organization")
async def list_organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationListResponse:
    items, total = await service.list(current_user, page=page, page_size=page_size)
    return OrganizationListResponse(
        items=[_to_response(o) for o in items], page=page, page_size=page_size, total=total
    )


@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
    responses={404: {"description": "Organization not found"}},
    summary="Retrieve the caller's own organization by id",
)
async def get_organization(
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationResponse:
    organization = await service.get(organization_id, current_user)
    return _to_response(organization)


@router.patch(
    "/{organization_id}",
    response_model=OrganizationResponse,
    responses={404: {"description": "Organization not found"}},
    summary="Update the caller's own organization",
)
async def update_organization(
    organization_id: UUID,
    payload: OrganizationUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationResponse:
    organization = await service.update(organization_id, payload.name, current_user)
    return _to_response(organization)
