import type { Session } from '../types';

/**
 * Session persistence — deliberately `localStorage` (survives browser
 * restarts), distinct from the *browser* `sessionStorage` API used
 * elsewhere (router guards) to track "has /dashboard been visited this
 * browser session" for the landing rule. Conflating the two would either
 * log users out every tab close, or make the dashboard-first bounce never
 * re-trigger — both wrong per spec.
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
