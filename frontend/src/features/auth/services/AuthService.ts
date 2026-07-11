import type { Session } from '../types';

/**
 * Clean seam between the UI and whatever actually authenticates a user.
 * `mockAuthService` is the only implementation in Phase 1 — swapping in
 * real Supabase auth later means writing one new class that satisfies this
 * interface; no UI code changes.
 */
export interface AuthService {
  /** Step 1 of login: validate credentials, dispatch (mock) OTP. */
  requestLogin(email: string, password: string): Promise<LoginChallenge>;
  /** Step 2 of login: verify the OTP code, establish a session. */
  verifyOtp(challengeId: string, code: string): Promise<Session>;
  resendOtp(challengeId: string): Promise<void>;
  logout(): Promise<void>;
  getSession(): Session | null;
  setActiveOrg(orgId: string): Session | null;
  /** Dev-mode-only convenience, intentionally optional: a mock
   * implementation can surface a hint (e.g. "enter 123456") for the OTP
   * screen to display. A real implementation simply omits this and the
   * hint stops rendering — no UI code change required. */
  getDevOtpHint?(): string | null;
  /** Dev-mode-only convenience for flows with no backing challenge to
   * verify against yet (e.g. invite-accept, which has no seeded invite
   * token in Phase 1). A real implementation omits this. */
  checkDevOtpCode?(code: string): boolean;
}

export interface LoginChallenge {
  challengeId: string;
  /** e.g. "f•••@co.sa" — the OTP screen never shows the full address. */
  maskedContact: string;
}

export class InvalidCredentialsError extends Error {
  constructor() {
    // Deliberately generic — spec §11.1: never reveal which field was wrong.
    super('Invalid email or password.');
    this.name = 'InvalidCredentialsError';
  }
}

export class RateLimitedError extends Error {
  readonly retryAfterSec: number;

  constructor(retryAfterSec: number) {
    super('Too many attempts.');
    this.name = 'RateLimitedError';
    this.retryAfterSec = retryAfterSec;
  }
}

export class InvalidOtpError extends Error {
  constructor() {
    super('Invalid verification code.');
    this.name = 'InvalidOtpError';
  }
}

export class ChallengeExpiredError extends Error {
  constructor() {
    super('This login attempt has expired.');
    this.name = 'ChallengeExpiredError';
  }
}
