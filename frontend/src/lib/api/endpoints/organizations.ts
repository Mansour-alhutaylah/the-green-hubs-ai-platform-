import { apiRequest } from '../client';
import type {
  OrganizationListResponse,
  OrganizationResponse,
  OrganizationUpdateRequest,
} from '../types';

/** GET /api/v1/organizations — always the caller's own single
 * organization (tenant scope is derived server-side from the bearer
 * token, never from a client-supplied id). */
export function listOrganizations(signal?: AbortSignal): Promise<OrganizationListResponse> {
  return apiRequest<OrganizationListResponse>('/api/v1/organizations', {
    query: { page: 1, page_size: 1 },
    signal,
  });
}

/** GET /api/v1/organizations/{id} — the backend answers 404 for any id
 * outside the caller's own organization, so passing an id here reveals
 * nothing and grants nothing. */
export function getOrganization(
  organizationId: string,
  signal?: AbortSignal,
): Promise<OrganizationResponse> {
  return apiRequest<OrganizationResponse>(`/api/v1/organizations/${organizationId}`, { signal });
}

/**
 * PATCH /api/v1/organizations/{id} — requires `organization.manage`
 * (admin/owner). `name` is the only mutable field the contract exposes.
 *
 * There is deliberately no `createOrganization` client here. `POST
 * /api/v1/organizations` exists, but `OrganizationService.create`
 * unconditionally raises `AuthorizationError("Organization creation is not
 * available in this phase.")` — shipping a client for an endpoint that can
 * only ever fail would invite a Live affordance guaranteed to 403.
 */
export function updateOrganization(
  organizationId: string,
  payload: OrganizationUpdateRequest,
  signal?: AbortSignal,
): Promise<OrganizationResponse> {
  return apiRequest<OrganizationResponse>(`/api/v1/organizations/${organizationId}`, {
    method: 'PATCH',
    json: payload,
    signal,
  });
}
