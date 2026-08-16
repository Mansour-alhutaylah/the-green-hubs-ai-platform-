import type { Role } from '@/features/rbac/roles';

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: Role;
  /** Organization ids this user belongs to. A live backend user belongs to
   * exactly one, or none (`organization_id: null`) — see `mapBackendUser.ts`.
   * The Preview workspace user belongs to one synthetic organization. */
  orgIds: string[];
}

/**
 * Which backing service produced this session.
 *
 * `'preview'` sessions exist **only** in a Preview build: they are created
 * by `previewAuthService`, which asserts the build-time mode before it will
 * produce one. A Live build has exactly one way to become authenticated —
 * the real Supabase password sign-in — so `'preview'` is unreachable there.
 */
export type SessionKind = 'preview' | 'live';

export interface Session {
  kind: SessionKind;
  user: AuthUser;
  /** Never the real Supabase access token: the API client reads that
   * fresh from the Supabase SDK on every request instead (§ live token
   * handling), so nothing here can go stale or leak through app state,
   * devtools, or this object's own persistence. A Preview session's token
   * is likewise never a real or fake JWT — just an opaque local marker. */
  token: string;
  /** Epoch millis. */
  expiresAt: number;
  /** Active organization for this session. `null` only for a live user
   * with no `organization_id` yet assigned on the backend. */
  activeOrgId: string | null;
}

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';
