import { apiRequest } from '../client';
import type { EngagementListResponse } from '../types';

/** GET /api/v1/engagements — the caller's own Engagements. `organization_id`
 * is never sent: tenant scope is derived server-side from the bearer token. */
export function listEngagements(
  params: { page?: number; page_size?: number } = {},
  signal?: AbortSignal,
): Promise<EngagementListResponse> {
  return apiRequest<EngagementListResponse>('/api/v1/engagements', {
    query: { page: params.page ?? 1, page_size: params.page_size ?? 100 },
    signal,
  });
}
