import { assertPreviewMode } from '@/lib/data/source';
import type { Session } from '../types';
import type { AuthService, LoginResult } from './AuthService';
import { PREVIEW_ORGANIZATION_ID, PREVIEW_USER } from './previewUsers';
import { clearPersistedSession, readPersistedSession, writePersistedSession } from './sessionStorage';

/**
 * Authentication for a Preview build.
 *
 * Everything about it is local and inert:
 *
 * - It never touches Supabase. It does not import the Supabase client, so
 *   there is no code path — reachable or otherwise — from a Preview sign-in
 *   to a real auth provider.
 * - It never calls `apiRequest`, `fetch`, or any endpoint module.
 * - It accepts no credentials. `requestLogin` is not part of the Preview
 *   flow at all; it throws rather than pretending to validate something.
 *   That closes the fall-through the audit called out: a Preview build
 *   cannot reach real authentication by submitting the password form.
 * - The session it mints is `kind: 'preview'` and carries an opaque marker
 *   in place of a token, so nothing downstream can mistake it for a
 *   credential.
 *
 * `assertPreviewMode` guards every session-producing path: in a Live build
 * this service is not wired in at all (see `resolvedAuthService`), and if
 * it somehow were, it would throw instead of fabricating a session.
 */
const PREVIEW_SESSION_TOKEN = 'preview-workspace-session';
const PREVIEW_SESSION_TTL_MS = 12 * 60 * 60 * 1000;

class PreviewAuthService implements AuthService {
  /** Preview has no credential flow. Reaching this means a caller tried to
   * sign in with an email and password inside a Preview build. */
  async requestLogin(): Promise<LoginResult> {
    throw new Error('Preview mode has no credential sign-in. Use the Preview workspace entry.');
  }

  async enterPreviewWorkspace(): Promise<Session> {
    assertPreviewMode('Preview workspace sign-in');

    const session: Session = {
      kind: 'preview',
      user: PREVIEW_USER,
      token: PREVIEW_SESSION_TOKEN,
      expiresAt: Date.now() + PREVIEW_SESSION_TTL_MS,
      activeOrgId: PREVIEW_ORGANIZATION_ID,
    };
    writePersistedSession(session);
    return session;
  }

  async logout(): Promise<void> {
    clearPersistedSession();
  }

  getSession(): Session | null {
    assertPreviewMode('Preview session restore');
    const session = readPersistedSession();
    // A persisted session that is not a Preview session is not ours to
    // restore — refuse it rather than adopting a shape from elsewhere.
    return session?.kind === 'preview' ? session : null;
  }

  setActiveOrg(orgId: string): Session | null {
    const session = this.getSession();
    if (!session) return null;
    const updated: Session = { ...session, activeOrgId: orgId };
    writePersistedSession(updated);
    return updated;
  }
}

export const previewAuthService: AuthService = new PreviewAuthService();
