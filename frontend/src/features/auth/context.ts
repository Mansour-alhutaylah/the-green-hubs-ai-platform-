import { createContext } from 'react';
import type { LoginResult } from './services/AuthService';
import type { AuthStatus, AuthUser, SessionKind } from './types';

export interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  activeOrgId: string | null;
  /** `null` when unauthenticated. Every business page that must not mix
   * synthetic and live data branches on this — `'live'` only when a real
   * Supabase-backed session resolved. `'preview'` is reachable only in a
   * Preview build. */
  sessionKind: SessionKind | null;
  /** Real credential sign-in. Always resolves to an established session or
   * throws; there is no intermediate challenge step. */
  requestLogin: (email: string, password: string) => Promise<LoginResult>;
  /** Non-null only in a Preview build, where it enters the local synthetic
   * workspace. `null` in every Live build, so the entry point does not
   * render there. */
  enterPreviewWorkspace: (() => Promise<void>) | null;
  logout: () => Promise<void>;
  setActiveOrg: (orgId: string) => void;
  /** True only after a previously-authenticated live session was found
   * invalid out of band (a 401 from the API client, or Supabase reporting
   * a sign-out/expiry this tab didn't initiate) — never set by an
   * explicit user-triggered logout. `ProtectedRoute` reads this to route
   * through the existing session-expired page instead of the plain login
   * redirect. Reset to `false` on the next successful sign-in. */
  sessionExpired: boolean;
}

/**
 * Kept in its own module (not alongside AuthProvider) so AuthContext.tsx
 * only ever exports the component — mixing a plain `createContext()`
 * value into a component file breaks React Fast Refresh.
 */
export const AuthContext = createContext<AuthContextValue | null>(null);
