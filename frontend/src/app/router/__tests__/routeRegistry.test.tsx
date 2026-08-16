import { isValidElement, type ReactElement, type ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { AppRoutes } from '../routes';
import { ProtectedRoute } from '../guards/ProtectedRoute';
import { PublicOnlyRoute } from '../guards/PublicOnlyRoute';
import { ROUTES, type RouteKey } from '@/app/navigation/routePaths';
import {
  deriveProtectedRouteKeys,
  isKnownProtectedPath,
  PROTECTED_INDEX_PATH,
  PROTECTED_ROUTE_KEYS,
  PROTECTED_ROUTE_PATHS,
  PUBLIC_ONLY_ROUTE_KEYS,
  PUBLIC_ONLY_ROUTE_PATHS,
  UNGUARDED_ROUTE_KEYS,
  UNGUARDED_ROUTE_PATHS,
} from '../routeRegistry';

/**
 * Structural guard against route-classification drift.
 *
 * The failure this exists to prevent is quiet: a page is added to the route
 * tree but not to the classification the guards read, so an unauthenticated
 * deep link to a real page answers 404, and the post-login return path
 * silently drops the user on /dashboard instead of the page they asked for.
 * Nothing throws, no test of that page fails, and the bug only shows up as
 * a confusing user report.
 *
 * Rather than re-listing the routes (which would just move the drift here),
 * these tests read the actual rendered route tree and compare it against
 * the registry.
 */

type Branch = 'protected' | 'publicOnly' | 'unguarded';

interface DeclaredRoute {
  path: string;
  branch: Branch;
}

interface RouteLikeProps {
  path?: string;
  index?: boolean;
  element?: ReactNode;
  children?: ReactNode;
}

/** Walks the JSX the router is built from and records every `<Route>` path
 * together with the guard branch it sits under. `AppRoutes` holds no hooks
 * of its own, so it can be invoked directly to obtain that tree. */
function collectDeclaredRoutes(node: ReactNode, branch: Branch, found: DeclaredRoute[]): void {
  if (Array.isArray(node)) {
    for (const child of node) collectDeclaredRoutes(child, branch, found);
    return;
  }
  if (!isValidElement(node)) return;

  const props = (node as ReactElement<RouteLikeProps>).props;

  let childBranch = branch;
  if (isValidElement(props.element)) {
    if (props.element.type === ProtectedRoute) childBranch = 'protected';
    else if (props.element.type === PublicOnlyRoute) childBranch = 'publicOnly';
  }

  if (typeof props.path === 'string') found.push({ path: props.path, branch: childBranch });
  if (props.index === true) found.push({ path: PROTECTED_INDEX_PATH, branch: childBranch });

  collectDeclaredRoutes(props.children, childBranch, found);
}

function declaredRoutes(): DeclaredRoute[] {
  const found: DeclaredRoute[] = [];
  collectDeclaredRoutes(AppRoutes(), 'unguarded', found);
  // The in-shell catch-all is not a route path; it is the 404 fallback.
  return found.filter((route) => route.path !== '*');
}

/** A concrete URL for a pattern, so dynamic segments can be exercised
 * through the same matcher the guards use. */
function sampleUrlFor(pattern: string): string {
  return pattern.replace(/:[^/]+/g, 'sample-id');
}

describe('route registry classification', () => {
  it('classifies every route path exactly once', () => {
    const allKeys = Object.keys(ROUTES) as RouteKey[];
    const classified = [
      ...PUBLIC_ONLY_ROUTE_KEYS,
      ...UNGUARDED_ROUTE_KEYS,
      ...PROTECTED_ROUTE_KEYS,
    ];

    expect([...classified].sort()).toEqual([...allKeys].sort());
    expect(new Set(classified).size).toBe(classified.length);
  });

  it('treats a newly added route key as protected by default', () => {
    // The drift scenario stated plainly: F2 adds an Engagements page. It is
    // protected without anyone remembering to say so, because protected is
    // what "not public-only and not unguarded" means.
    const withFutureRoute = [...(Object.keys(ROUTES) as string[]), 'engagements'];
    const derived = deriveProtectedRouteKeys(withFutureRoute, [
      ...PUBLIC_ONLY_ROUTE_KEYS,
      ...UNGUARDED_ROUTE_KEYS,
    ]);

    expect(derived).toContain('engagements');
    expect(derived).not.toContain('login');
    expect(derived).not.toContain('sessionExpired');
  });

  it('recognizes every protected route the router actually declares', () => {
    // Any path listed here is rendered behind ProtectedRoute but is not
    // classified as protected: an unauthenticated deep link to it would
    // answer 404, and its post-login return would be dropped.
    const unrecognized = declaredRoutes()
      .filter((entry) => entry.branch === 'protected')
      .filter((entry) => !isKnownProtectedPath(sampleUrlFor(entry.path)))
      .map((entry) => entry.path);

    expect(unrecognized).toEqual([]);
  });

  it('classifies no public-only or unguarded route as protected', () => {
    const misclassified = declaredRoutes()
      .filter((entry) => entry.branch !== 'protected')
      .filter((entry) => isKnownProtectedPath(sampleUrlFor(entry.path)))
      .map((entry) => entry.path);

    expect(misclassified).toEqual([]);
  });

  it('declares exactly the routes the registry classifies, and no hand-added extras', () => {
    const declared = declaredRoutes();

    const declaredProtected = declared
      .filter((entry) => entry.branch === 'protected')
      .map((entry) => entry.path)
      .sort();
    expect(declaredProtected).toEqual([...PROTECTED_ROUTE_PATHS].sort());

    const declaredPublicOnly = declared
      .filter((entry) => entry.branch === 'publicOnly')
      .map((entry) => entry.path)
      .sort();
    expect(declaredPublicOnly).toEqual([...PUBLIC_ONLY_ROUTE_PATHS].sort());

    const declaredUnguarded = declared
      .filter((entry) => entry.branch === 'unguarded')
      .map((entry) => entry.path)
      .sort();
    expect(declaredUnguarded).toEqual([...UNGUARDED_ROUTE_PATHS].sort());
  });

  it('keeps the protected index route classified', () => {
    expect(isKnownProtectedPath(PROTECTED_INDEX_PATH)).toBe(true);
    expect(declaredRoutes()).toContainEqual({ path: PROTECTED_INDEX_PATH, branch: 'protected' });
  });

  it.each([
    ['/documents/doc-1', ROUTES.documentDetail],
    ['/analysis/run-1', ROUTES.analysisRun],
    ['/organizations/org-1', ROUTES.organizationDetail],
    ['/reports/report-1', ROUTES.reportDetail],
  ])('matches the dynamic route %s', (url, pattern) => {
    expect(PROTECTED_ROUTE_PATHS).toContain(pattern);
    expect(isKnownProtectedPath(url)).toBe(true);
  });

  it('still rejects a URL that matches no route at all', () => {
    expect(isKnownProtectedPath('/no-such-page')).toBe(false);
    expect(isKnownProtectedPath('/documents/doc-1/extra/segments')).toBe(false);
  });
});
