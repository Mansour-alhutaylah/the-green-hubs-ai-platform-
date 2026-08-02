import type { Session } from '../types';

/**
 * Clean seam between the UI and whatever actually authenticates a user.
 * `mockAuthService` (demo-shaped, two-step OTP) and the live
 * Supabase-backed service (`liveAuthService.ts`, single-step
 * email/password — Supabase has no OTP step for a password grant) are
 * both implementations of this one interface; LoginPage branches on
 * `LoginResult.kind` instead of assuming a step always follows.
 */
export interface AuthService {
  /** Starts a login attempt. Mock: validates credentials and dispatches a
   * (mock) OTP challenge the UI must then verify. Live: performs the real
   * Supabase sign-in and resolves the backend profile in one step — there
   * is no second factor to collect, so the session is already established
   * when this resolves. */
  requestLogin(email: string, password: string): Promise<LoginResult>;
  /** Step 2 of the mock's two-step login: verify the OTP code, establish a
   * session. Never called for a live `requestLogin` (its result never has
   * `kind: 'otpRequired'`). */
  verifyOtp(challengeId: string, code: string): Promise<Session>;
  resendOtp(challengeId: string): Promise<void>;
  /** Explicit local-session entry point exposed only by a development mock. */
  enterDemoWorkspace?(): Promise<Session>;
  logout(): Promise<void>;
  /** Synchronous session lookup — used only for the mock's localStorage-
   * backed demo/OTP sessions, which are available instantly with no
   * network round trip. A live service returns `null` here and instead
   * implements `restoreSession`/`subscribe` below. */
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
  /** Live-only: asynchronously restores a Supabase session that survived a
   * page refresh (Supabase's own SDK persists it) and resolves the backend
   * profile. Omitted by the mock, which restores synchronously via
   * `getSession` instead. */
  restoreSession?(): Promise<Session | null>;
  /** Live-only: subscribes to out-of-band session changes (token refresh,
   * expiry, sign-out from another tab). Returns an unsubscribe function. */
  subscribe?(onChange: (session: Session | null) => void): () => void;
}

export interface LoginChallenge {
  challengeId: string;
  /** e.g. "f•••@co.sa" — the OTP screen never shows the full address. */
  maskedContact: string;
}

export type LoginResult =
  | ({ kind: 'otpRequired' } & LoginChallenge)
  | { kind: 'authenticated'; session: Session };

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

/** Thrown when Supabase authentication succeeds but the backend has no
 * `public.users` profile for this account (backend's `GET /auth/me`
 * returns 403 `ProfileNotProvisionedError`). The live service always signs
 * the Supabase session back out before this reaches the caller — a
 * half-authenticated state (valid Supabase session, no application
 * profile) must never persist. */
export class ProfileNotProvisionedError extends Error {
  constructor() {
    super('This account is not yet set up. Contact your administrator.');
    this.name = 'ProfileNotProvisionedError';
  }
}
