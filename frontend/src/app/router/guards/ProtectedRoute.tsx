import { Navigate, Outlet, useLocation } from 'react-router';
import { useAuth } from '@/features/auth/useAuth';
import { LoadingDiamond } from '@/design-system';
import { NotFoundPage } from '@/features/errors/pages/NotFoundPage';
import { ROUTES } from '../../navigation/routePaths';
import { isKnownProtectedPath } from '../routeRegistry';
import { PublicShell } from '../PublicShell';

/**
 * Gate for the whole authenticated shell. Order matters:
 *
 * 1. still restoring session → full-page loading diamond;
 * 2. no session, and the URL is not a route that exists → a truthful 404,
 *    rendered standalone (there is no shell to render it inside for a
 *    signed-out visitor). Previously every unknown URL redirected to
 *    /login, which implied the page existed and the visitor was merely
 *    signed out;
 * 3. no session on a real protected route → /login (or /session-expired
 *    when a previously-valid live session was just found invalid out of
 *    band), carrying the attempted location so sign-in can return to it;
 * 4. otherwise render the requested route.
 *
 * The "landing rule" bounce that used to sit between (3) and (4) — send
 * every authenticated deep link to /dashboard until the dashboard had been
 * visited once per browser session — is gone. It silently discarded the
 * URL the user actually asked for, including on a page refresh, which the
 * audit flagged as a routing defect rather than a feature.
 *
 * None of this is authorization. It decides what renders; the backend
 * decides what a request may return.
 */
export function ProtectedRoute() {
  const { status, sessionExpired } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return <LoadingDiamond size={40} fullPage />;
  }

  if (status === 'unauthenticated') {
    if (!isKnownProtectedPath(location.pathname)) {
      return (
        <PublicShell>
          <NotFoundPage />
        </PublicShell>
      );
    }

    return (
      <Navigate
        to={sessionExpired ? ROUTES.sessionExpired : ROUTES.login}
        state={{ from: location }}
        replace
      />
    );
  }

  return <Outlet />;
}
