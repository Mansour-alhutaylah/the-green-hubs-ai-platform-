import type { Session } from '../types';

/**
 * Clean seam between the UI and whatever actually authenticates a user.
 *
 * There are exactly two implementations and they never coexist:
 * `liveAuthService` (the real Supabase email/password sign-in, the only
 * authentication a Production build has) and `previewAuthService` (a local,
 * credential-free Preview workspace entry that touches no network).
 * `resolvedAuthService` picks one at build time.
 *
 * The OTP members that used to live here are gone. Supabase's password
 * grant has no second factor, so `verifyOtp`/`resendOtp` were only ever
 * satisfiable by the mock — keeping them in the interface presented MFA as
 * a working capability that does not exist. Real MFA is a later dedicated
 * security phase; when it lands it will be modelled against whatever
 * Supabase actually implements, not against this placeholder.
 */
export interface AuthService {
  /** Real credential sign-in. Live: performs the Supabase sign-in and
   * resolves the backend profile in one step. Preview: rejects — a Preview
   * build has no credential flow to fall through to. */
  requestLogin(email: string, password: string): Promise<LoginResult>;
  /** Preview-only: enters the local synthetic workspace. Absent from the
   * live service, so the UI simply does not render the entry point in a
   * Live build. */
  enterPreviewWorkspace?(): Promise<Session>;
  logout(): Promise<void>;
  /** Synchronous session lookup — used only for the Preview service's
   * localStorage-backed session, which is available instantly with no
   * network round trip. The live service returns `null` here and
   * implements `restoreSession`/`subscribe` below instead. */
  getSession(): Session | null;
  setActiveOrg(orgId: string): Session | null;
  /** Live-only: asynchronously restores a Supabase session that survived a
   * page refresh (Supabase's own SDK persists it) and resolves the backend
   * profile. */
  restoreSession?(): Promise<Session | null>;
  /** Live-only: subscribes to out-of-band session changes (token refresh,
   * expiry, sign-out from another tab). Returns an unsubscribe function. */
  subscribe?(onChange: (session: Session | null) => void): () => void;
}

/** A successful `requestLogin` always establishes the session directly —
 * there is no intermediate challenge step in any implementation. */
export type LoginResult = { kind: 'authenticated'; session: Session };

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
