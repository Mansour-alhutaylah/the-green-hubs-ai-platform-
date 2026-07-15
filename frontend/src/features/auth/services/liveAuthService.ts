import { getSupabaseClient } from '@/lib/supabase/client';
import { getMe } from '@/lib/api/endpoints/auth';
import { ForbiddenError } from '@/lib/api/errors';
import type { UserProfileResponse } from '@/lib/api/types';
import type { Session } from '../types';
import {
  ChallengeExpiredError,
  InvalidCredentialsError,
  ProfileNotProvisionedError,
  RateLimitedError,
  type AuthService,
  type LoginResult,
} from './AuthService';
import { mapBackendUser } from './mapBackendUser';

/** Supabase does not always report a precise retry window for password-
 * grant throttling via the JS client — this is a reasonable fixed fallback
 * for the UI's countdown, not a value read from any response. */
const RATE_LIMIT_FALLBACK_RETRY_SEC = 30;
const SESSION_TTL_FALLBACK_MS = 60 * 60 * 1000;

/** Resolves the current Supabase session (if any) into the app's `Session`
 * shape by calling `GET /api/v1/auth/me`. Returns `null` — never throws —
 * for "no session" and for any transient resolution failure that isn't a
 * genuine "no profile" case, so callers never get stuck retrying a
 * half-formed state. A confirmed missing-profile case (`ForbiddenError`)
 * signs the Supabase session back out before surfacing
 * `ProfileNotProvisionedError`: a valid Supabase session with no
 * application profile must never be left half-authenticated. */
async function resolveLiveSession(): Promise<Session | null> {
  const supabase = getSupabaseClient();
  if (!supabase) return null;

  const { data } = await supabase.auth.getSession();
  const supabaseSession = data.session;
  if (!supabaseSession) return null;

  let profile: UserProfileResponse;
  try {
    profile = await getMe();
  } catch (error) {
    if (error instanceof ForbiddenError) {
      await supabase.auth.signOut();
      throw new ProfileNotProvisionedError();
    }
    return null;
  }

  return {
    kind: 'live',
    user: mapBackendUser(profile),
    // Deliberately not the real access token — see Session.token's
    // docstring. The API client reads the live token fresh from the
    // Supabase SDK on every request instead.
    token: 'supabase-session',
    expiresAt: supabaseSession.expires_at
      ? supabaseSession.expires_at * 1000
      : Date.now() + SESSION_TTL_FALLBACK_MS,
    activeOrgId: profile.organization_id,
  };
}

class LiveAuthService implements AuthService {
  async requestLogin(email: string, password: string): Promise<LoginResult> {
    const supabase = getSupabaseClient();
    if (!supabase) {
      throw new Error(
        'Supabase is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.',
      );
    }

    const { error } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password,
    });

    if (error) {
      if (error.status === 429) {
        throw new RateLimitedError(RATE_LIMIT_FALLBACK_RETRY_SEC);
      }
      throw new InvalidCredentialsError();
    }

    const session = await resolveLiveSession();
    if (!session) {
      throw new InvalidCredentialsError();
    }
    return { kind: 'authenticated', session };
  }

  /** Never reached: a live `requestLogin` result is never `otpRequired`. */
  async verifyOtp(): Promise<Session> {
    throw new ChallengeExpiredError();
  }

  async resendOtp(): Promise<void> {}

  async logout(): Promise<void> {
    const supabase = getSupabaseClient();
    if (supabase) await supabase.auth.signOut();
  }

  /** Live sessions never resolve synchronously — see `restoreSession`. */
  getSession(): Session | null {
    return null;
  }

  /** Single-organization model: nothing to switch to. */
  setActiveOrg(): Session | null {
    return null;
  }

  async restoreSession(): Promise<Session | null> {
    try {
      return await resolveLiveSession();
    } catch {
      return null;
    }
  }

  subscribe(onChange: (session: Session | null) => void): () => void {
    const supabase = getSupabaseClient();
    if (!supabase) return () => {};

    const { data } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'SIGNED_OUT') {
        onChange(null);
        return;
      }
      if (event === 'SIGNED_IN' || event === 'TOKEN_REFRESHED' || event === 'USER_UPDATED') {
        void resolveLiveSession()
          .then(onChange)
          .catch(() => onChange(null));
      }
    });

    return () => data.subscription.unsubscribe();
  }
}

export const liveAuthService: AuthService = new LiveAuthService();
