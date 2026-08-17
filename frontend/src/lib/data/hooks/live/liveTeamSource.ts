import { useCallback } from 'react';
import { getMe } from '@/lib/api/endpoints/auth';
import { toCurrentTeamMember } from '../../adapters/teamAdapter';
import type { TeamDirectory } from '../../contracts/team';
import { useAsyncResource, type AsyncResource } from '../useAsyncResource';

/**
 * The Live team directory: `GET /api/v1/auth/me`, and only that.
 *
 * There is no organization-wide user endpoint on this backend, and
 * `app/domain/security/permissions.py` says so in as many words ("There is
 * no `user.manage` permission because no user-management route exists
 * yet"). The caller's own profile is therefore the entire set of real
 * identities the product can obtain, so the directory contains exactly one
 * member and reports `isCompleteDirectory: false` — which is what drives
 * the page's disclosure instead of an implied "this is everyone".
 *
 * Supabase is never queried here: no table read, no Admin API, no
 * service-role credential. The browser client holds only the public anon
 * key and is used for the bearer token, nothing else. Enumerating
 * `auth.users` from a browser is exactly the shortcut this refuses to take.
 *
 * Imports no fixture module, so a failure resolves to `error` rather than
 * to a synthetic directory.
 */
export function useLiveTeamDirectory(enabled: boolean): AsyncResource<TeamDirectory> {
  const load = useCallback(
    async (signal: AbortSignal): Promise<TeamDirectory> => ({
      members: [toCurrentTeamMember(await getMe(signal))],
      isCompleteDirectory: false,
    }),
    [],
  );

  return useAsyncResource(enabled, load);
}
