import type { AuthService, LoginResult } from '@/features/auth/services/AuthService';
import type { Session } from '@/features/auth/types';
import { Role } from '@/features/rbac/roles';

/**
 * A `kind: 'live'` session and the auth service that restores it.
 *
 * The shared `buildTestSession` helper produces a `kind: 'preview'`
 * session, which is right for the F1 tests that only need *somebody*
 * signed in. F2A's Live tests need the other kind: the pages branch on the
 * build mode for their data source, but the identity they send — above all
 * the `organization_id` a create request carries — comes from the session,
 * and a test that seeds the wrong kind would be exercising a combination a
 * real Live build cannot produce.
 *
 * The organization id is deliberately distinctive so a test can prove the
 * value that reached the wire came from *here* and not from a URL, a route
 * parameter, or storage.
 */
export const LIVE_ORGANIZATION_ID = 'org-authenticated-from-auth-me';
export const LIVE_ORGANIZATION_NAME = 'Authenticated Live Organization';
export const LIVE_USER_EMAIL = 'live.admin@example.test';
export const LIVE_USER_NAME = 'Live Administrator';

export function buildLiveSession(role: Role = Role.Admin): Session {
  return {
    kind: 'live',
    user: {
      id: 'user-live-1',
      name: LIVE_USER_NAME,
      email: LIVE_USER_EMAIL,
      role,
      orgIds: [LIVE_ORGANIZATION_ID],
    },
    token: 'supabase-session',
    expiresAt: Date.now() + 60 * 60 * 1000,
    // Set once from `GET /auth/me`'s `organization_id`. The live auth
    // service's `setActiveOrg` is a no-op, so nothing can change it.
    activeOrgId: LIVE_ORGANIZATION_ID,
  };
}

export function buildLiveAuthService(role: Role = Role.Admin): AuthService {
  const session = buildLiveSession(role);
  return {
    async requestLogin(): Promise<LoginResult> {
      throw new Error('unused in this test');
    },
    async logout(): Promise<void> {},
    getSession: () => null,
    // Mirrors the real live service: tenant scope is not client-settable.
    setActiveOrg: () => null,
    restoreSession: async () => session,
  };
}
