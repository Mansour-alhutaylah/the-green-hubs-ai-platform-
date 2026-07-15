import { apiRequest } from '../client';
import type { OrganizationListResponse } from '../types';

/** GET /api/v1/organizations — always the caller's own single
 * organization (tenant scope is derived server-side from the bearer
 * token, never from a client-supplied id). */
export function listOrganizations(signal?: AbortSignal): Promise<OrganizationListResponse> {
  return apiRequest<OrganizationListResponse>('/api/v1/organizations', {
    query: { page: 1, page_size: 1 },
    signal,
  });
}
