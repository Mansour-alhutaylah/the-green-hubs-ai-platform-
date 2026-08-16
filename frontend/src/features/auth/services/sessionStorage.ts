import type { Session } from '../types';

/**
 * Persistence for the **Preview** session only.
 *
 * `previewAuthService` is the sole writer: it mints a local synthetic
 * session that carries an opaque marker rather than a token, so nothing
 * stored here is or resembles a credential. A live Supabase session is
 * never written here — the Supabase SDK manages its own storage, and the
 * API client reads the real access token from it fresh on every request.
 *
 * `localStorage` (not the browser's `sessionStorage` API, despite this
 * module's name) so a Preview reviewer stays signed in across tab closes
 * and restarts, which is the whole point of a one-click demonstration
 * workspace.
 *
 * These three functions are plain storage: `readPersistedSession` drops an
 * expired or unparseable entry, but it does not judge what kind of session
 * it read. `previewAuthService.getSession()` is what refuses a stored
 * value whose `kind` is not `'preview'`, so a record left over from an
 * earlier build — or planted by hand — is never adopted.
 */
const SESSION_KEY = 'ghp:session';

export function readPersistedSession(): Session | null {
  const raw = window.localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const session = JSON.parse(raw) as Session;
    if (session.expiresAt < Date.now()) {
      window.localStorage.removeItem(SESSION_KEY);
      return null;
    }
    return session;
  } catch {
    window.localStorage.removeItem(SESSION_KEY);
    return null;
  }
}

export function writePersistedSession(session: Session): void {
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearPersistedSession(): void {
  window.localStorage.removeItem(SESSION_KEY);
}
