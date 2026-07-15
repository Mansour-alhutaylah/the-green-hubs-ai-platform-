import type { Session } from '../types';
import type { AuthService, LoginResult } from './AuthService';
import { mockAuthService } from './mockAuthService';
import { liveAuthService } from './liveAuthService';

/**
 * The app's real default `AuthService` (wired in via `AuthContext.tsx`'s
 * `service` parameter default — every test injects its own service or a
 * seeded stub instead, so this is never exercised in tests). Demo
 * capabilities delegate to `mockAuthService` unchanged; real
 * authentication delegates to `liveAuthService`. The two never overlap: a
 * demo session lives only in `ghp:session` (localStorage), a live session
 * lives only in Supabase's own client-managed storage — `logout` clears
 * both unconditionally since at most one is ever actually populated.
 *
 * `enterDemoWorkspace`/`getDevOtpHint`/`checkDevOtpCode` are always
 * delegated (not conditionally omitted): `AuthContext`'s existing
 * `isDevAuthBypassEnabled()` gate already hides them from the UI in a
 * production build regardless of what a service exposes, so re-checking
 * the flag here would be redundant.
 */
class ResolvedAuthService implements AuthService {
  requestLogin(email: string, password: string): Promise<LoginResult> {
    return liveAuthService.requestLogin(email, password);
  }

  verifyOtp(challengeId: string, code: string): Promise<Session> {
    return mockAuthService.verifyOtp(challengeId, code);
  }

  resendOtp(challengeId: string): Promise<void> {
    return mockAuthService.resendOtp(challengeId);
  }

  enterDemoWorkspace(): Promise<Session> {
    return mockAuthService.enterDemoWorkspace!();
  }

  async logout(): Promise<void> {
    await Promise.all([mockAuthService.logout(), liveAuthService.logout()]);
  }

  getSession(): Session | null {
    return mockAuthService.getSession();
  }

  setActiveOrg(orgId: string): Session | null {
    return mockAuthService.setActiveOrg(orgId);
  }

  getDevOtpHint(): string | null {
    return mockAuthService.getDevOtpHint!();
  }

  checkDevOtpCode(code: string): boolean {
    return mockAuthService.checkDevOtpCode!(code);
  }

  restoreSession(): Promise<Session | null> {
    return liveAuthService.restoreSession!();
  }

  subscribe(onChange: (session: Session | null) => void): () => void {
    return liveAuthService.subscribe!(onChange);
  }
}

export const resolvedAuthService: AuthService = new ResolvedAuthService();
