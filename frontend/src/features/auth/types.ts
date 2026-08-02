import type { Role } from '@/features/rbac/roles';

export interface DemoUser {
  id: string;
  name: string;
  email: string;
  role: Role;
  /** Organization ids this user belongs to. Demo users may belong to
   * several (§0.5); a live backend user belongs to exactly one, or none
   * (`organization_id: null`) — see `mapBackendUser.ts`. */
  orgIds: string[];
}

/** Which backing service produced this session — the one explicit
 * discriminant every consumer (OrgSwitcher, the API client's callers, the
 * document pages) branches on to keep mock and live data from ever mixing
 * on the same page. */
export type SessionKind = 'demo' | 'live';

export interface Session {
  kind: SessionKind;
  user: DemoUser;
  /** Never the real Supabase access token: the API client reads that
   * fresh from the Supabase SDK on every request instead (§ live token
   * handling), so nothing here can go stale or leak through app state,
   * devtools, or this object's own persistence. A demo session's token is
   * likewise never a real/fake JWT — just an opaque local marker. */
  token: string;
  /** Epoch millis. */
  expiresAt: number;
  /** Active organization for this session. `null` only for a live user
   * with no `organization_id` yet assigned on the backend. */
  activeOrgId: string | null;
}

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';
