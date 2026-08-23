import { apiRequest } from '../client';
import type {
  EngagementCreateRequest,
  EngagementListResponse,
  EngagementResponse,
  EngagementUpdateRequest,
} from '../types';

/**
 * GET /api/v1/engagements — the caller's own Engagements.
 *
 * The route accepts an optional `organization_id` **filter**, and this
 * client deliberately never sends it. The backend already scopes the query
 * to the caller's organization from the bearer token; a client-chosen id
 * could only narrow a scope the server already decided, while making the
 * request look as though the client were asserting tenancy. Scope stays a
 * server concern.
 */
export function listEngagements(
  params: { page?: number; page_size?: number } = {},
  signal?: AbortSignal,
): Promise<EngagementListResponse> {
  return apiRequest<EngagementListResponse>('/api/v1/engagements', {
    query: { page: params.page ?? 1, page_size: params.page_size ?? 100 },
    signal,
  });
}

/** GET /api/v1/engagements/{id} — 404 for anything outside the caller's
 * own organization. */
export function getEngagement(
  engagementId: string,
  signal?: AbortSignal,
): Promise<EngagementResponse> {
  return apiRequest<EngagementResponse>(`/api/v1/engagements/${engagementId}`, { signal });
}

/**
 * POST /api/v1/engagements — requires `engagement.manage`.
 *
 * This is the one place the Frontend sends an `organization_id`, and only
 * because the verified contract **requires** it in the body
 * (`EngagementCreateRequest`). It is not a scope assertion: the service
 * compares it against the caller's own organization and answers 403
 * ("Cannot create an Engagement for another organization") on a mismatch.
 * The value comes from `GET /auth/me` — never from a URL, query string,
 * route parameter, or stored preference.
 */
export function createEngagement(
  payload: EngagementCreateRequest,
  signal?: AbortSignal,
): Promise<EngagementResponse> {
  return apiRequest<EngagementResponse>('/api/v1/engagements', {
    method: 'POST',
    json: payload,
    signal,
  });
}

/** PATCH /api/v1/engagements/{id} — requires `engagement.manage`. Sends
 * only the fields actually edited. `organization_id` is omitted: moving an
 * engagement to another organization is refused server-side, and the UI
 * offers no such control. */
export function updateEngagement(
  engagementId: string,
  payload: EngagementUpdateRequest,
  signal?: AbortSignal,
): Promise<EngagementResponse> {
  return apiRequest<EngagementResponse>(`/api/v1/engagements/${engagementId}`, {
    method: 'PATCH',
    json: payload,
    signal,
  });
}
