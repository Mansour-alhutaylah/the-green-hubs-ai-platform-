import { createContext } from 'react';
import type { LoginResult } from './services/AuthService';
import type { AuthStatus, DemoUser, SessionKind } from './types';

export interface AuthContextValue {
  status: AuthStatus;
  user: DemoUser | null;
  activeOrgId: string | null;
  /** `null` when unauthenticated. Every business page that must not mix
   * mock and live data branches on this — `'live'` only when a real
   * Supabase-backed session resolved; everything else (including no
   * session at all) is treated as the safe, mock-data default. */
  sessionKind: SessionKind | null;
  /** Resolves to `{kind: 'otpRequired', ...}` (mock two-step login — the
   * UI must then call `verifyOtp`) or `{kind: 'authenticated'}` (live
   * Supabase login — the session is already established). */
  requestLogin: (email: string, password: string) => Promise<LoginResult>;
  verifyOtp: (challengeId: string, code: string) => Promise<void>;
  resendOtp: (challengeId: string) => Promise<void>;
  /** Non-null only when the explicit development bypass flag is enabled. */
  enterDemoWorkspace: (() => Promise<void>) | null;
  logout: () => Promise<void>;
  setActiveOrg: (orgId: string) => void;
  /** Present only when the active AuthService is a dev-mode mock — a real
   * implementation has no `getDevOtpHint`, so this is simply `null` and
   * the OTP screen's hint banner stops rendering with no code change. */
  devOtpHint: string | null;
  /** Dev-mode-only OTP check for flows with no backing challenge (e.g.
   * invite-accept). Always `false` against a real AuthService. */
  checkDevOtpCode: (code: string) => boolean;
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
