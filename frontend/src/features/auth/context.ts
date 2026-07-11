import { createContext } from 'react';
import type { LoginChallenge } from './services/AuthService';
import type { AuthStatus, DemoUser } from './types';

export interface AuthContextValue {
  status: AuthStatus;
  user: DemoUser | null;
  activeOrgId: string | null;
  requestLogin: (email: string, password: string) => Promise<LoginChallenge>;
  verifyOtp: (challengeId: string, code: string) => Promise<void>;
  resendOtp: (challengeId: string) => Promise<void>;
  logout: () => Promise<void>;
  setActiveOrg: (orgId: string) => void;
  /** Present only when the active AuthService is a dev-mode mock — a real
   * implementation has no `getDevOtpHint`, so this is simply `null` and
   * the OTP screen's hint banner stops rendering with no code change. */
  devOtpHint: string | null;
  /** Dev-mode-only OTP check for flows with no backing challenge (e.g.
   * invite-accept). Always `false` against a real AuthService. */
  checkDevOtpCode: (code: string) => boolean;
}

/**
 * Kept in its own module (not alongside AuthProvider) so AuthContext.tsx
 * only ever exports the component — mixing a plain `createContext()`
 * value into a component file breaks React Fast Refresh.
 */
export const AuthContext = createContext<AuthContextValue | null>(null);
