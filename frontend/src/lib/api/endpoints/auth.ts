import { apiRequest } from '../client';
import type { UserProfileResponse } from '../types';

/** GET /api/v1/auth/me — resolves the Supabase-authenticated caller to the
 * backend's application user profile. */
export function getMe(signal?: AbortSignal): Promise<UserProfileResponse> {
  return apiRequest<UserProfileResponse>('/api/v1/auth/me', { signal });
}
