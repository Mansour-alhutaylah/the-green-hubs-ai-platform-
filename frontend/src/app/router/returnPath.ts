import { ROUTES } from '../navigation/routePaths';
import { isKnownProtectedPath } from './routeRegistry';

/**
 * The post-login return path.
 *
 * `ProtectedRoute` stores the attempted location in the redirect's router
 * state; after a successful sign-in the login page sends the user there
 * instead of always dumping them on /dashboard.
 *
 * Router state is not attacker-controlled in the same way a query
 * parameter is, but it is still untrusted input (it survives history
 * entries and can be crafted by anything that can call `navigate`), so the
 * candidate is validated rather than trusted:
 *
 * - it must be a same-document absolute path (`/…`), never a full URL and
 *   never protocol-relative (`//evil.example`), so it cannot become an
 *   open redirect;
 * - backslashes are rejected outright, since some browsers normalize `/\`
 *   to `//`;
 * - it must match a known protected route, so it cannot be used to bounce
 *   the user back onto a public auth screen or an unknown URL.
 *
 * Anything that fails falls back to /dashboard. This grants no access:
 * the destination still renders behind `ProtectedRoute` and `RoleGuard`.
 */
export const DEFAULT_POST_LOGIN_PATH: string = ROUTES.dashboard;

interface StoredLocation {
  pathname?: unknown;
  search?: unknown;
  hash?: unknown;
}

function isStoredLocation(value: unknown): value is StoredLocation {
  return typeof value === 'object' && value !== null;
}

export function resolveReturnPath(state: unknown): string {
  if (!isStoredLocation(state)) return DEFAULT_POST_LOGIN_PATH;
  const from = (state as { from?: unknown }).from;
  if (!isStoredLocation(from)) return DEFAULT_POST_LOGIN_PATH;

  const { pathname, search, hash } = from;
  if (typeof pathname !== 'string') return DEFAULT_POST_LOGIN_PATH;
  if (!pathname.startsWith('/') || pathname.startsWith('//')) return DEFAULT_POST_LOGIN_PATH;
  if (pathname.includes('\\')) return DEFAULT_POST_LOGIN_PATH;
  if (!isKnownProtectedPath(pathname)) return DEFAULT_POST_LOGIN_PATH;

  const suffix = `${typeof search === 'string' ? search : ''}${typeof hash === 'string' ? hash : ''}`;
  return suffix.includes('\\') ? pathname : `${pathname}${suffix}`;
}
