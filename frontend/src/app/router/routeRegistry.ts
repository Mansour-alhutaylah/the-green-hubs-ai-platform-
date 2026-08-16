import { matchPath } from 'react-router';
import { ROUTES, type RouteKey } from '../navigation/routePaths';

/**
 * The one classification of every route path in the app.
 *
 * `ROUTES` (routePaths.ts) already owns the path strings; this module owns
 * the question "which guard branch does each path belong to". Both
 * `routes.tsx` (which renders the tree) and the two consumers that need to
 * recognize a protected URL — `ProtectedRoute`, to tell "sign in to see
 * this" apart from "this does not exist", and the post-login return-path
 * validator — read the same definitions.
 *
 * The key property is that **protected is the derived default**, not a
 * hand-maintained list. Only the public-only and unguarded routes are
 * enumerated; every other `ROUTES` key is protected by subtraction, in the
 * type system and at runtime alike. Adding `engagements: '/engagements'` to
 * `ROUTES` therefore classifies it as protected immediately, and
 * `routes.tsx` stops compiling until it supplies an element for it. There
 * is no second array to forget to update.
 *
 * This is a routing concern only. It says nothing about whether a given
 * user may see a route — `RoleGuard` and, above all, the backend decide
 * that. Classifying a path here grants access to nothing.
 */

export type PublicOnlyRouteKey = 'login' | 'forgotPassword' | 'resetPassword' | 'inviteAccept';

/** Reachable regardless of session state: a session that just expired, or
 * an access-denied bounce, must render for an already-authenticated and an
 * already-unauthenticated visitor alike. */
export type UnguardedRouteKey = 'sessionExpired' | 'accessDenied';

/** Everything else. Derived, never listed. */
export type ProtectedRouteKey = Exclude<RouteKey, PublicOnlyRouteKey | UnguardedRouteKey>;

export const PUBLIC_ONLY_ROUTE_KEYS: readonly PublicOnlyRouteKey[] = [
  'login',
  'forgotPassword',
  'resetPassword',
  'inviteAccept',
];

export const UNGUARDED_ROUTE_KEYS: readonly UnguardedRouteKey[] = [
  'sessionExpired',
  'accessDenied',
];

const NON_PROTECTED_ROUTE_KEYS: readonly string[] = [
  ...PUBLIC_ONLY_ROUTE_KEYS,
  ...UNGUARDED_ROUTE_KEYS,
];

/**
 * The subtraction rule, exported as a pure function so a test can prove it
 * on a hypothetical future key rather than only on today's route table.
 */
export function deriveProtectedRouteKeys<Key extends string>(
  allKeys: readonly Key[],
  nonProtectedKeys: readonly string[],
): Key[] {
  const excluded = new Set<string>(nonProtectedKeys);
  return allKeys.filter((key) => !excluded.has(key));
}

export const PROTECTED_ROUTE_KEYS: readonly ProtectedRouteKey[] = deriveProtectedRouteKeys(
  Object.keys(ROUTES) as RouteKey[],
  NON_PROTECTED_ROUTE_KEYS,
) as ProtectedRouteKey[];

export const PUBLIC_ONLY_ROUTE_PATHS: readonly string[] = PUBLIC_ONLY_ROUTE_KEYS.map(
  (key) => ROUTES[key],
);

export const UNGUARDED_ROUTE_PATHS: readonly string[] = UNGUARDED_ROUTE_KEYS.map(
  (key) => ROUTES[key],
);

/** The authenticated shell's own index route, which has no `ROUTES` entry
 * because it renders a redirect rather than a page. */
export const PROTECTED_INDEX_PATH = '/';

export const PROTECTED_ROUTE_PATHS: readonly string[] = [
  PROTECTED_INDEX_PATH,
  ...PROTECTED_ROUTE_KEYS.map((key) => ROUTES[key]),
];

/** Matches against the route *patterns*, so dynamic segments
 * (`/documents/:id`, `/analysis/:runId`, …) are recognized for any concrete
 * id without being enumerated. */
export function isKnownProtectedPath(pathname: string): boolean {
  return PROTECTED_ROUTE_PATHS.some((pattern) => matchPath(pattern, pathname) != null);
}
