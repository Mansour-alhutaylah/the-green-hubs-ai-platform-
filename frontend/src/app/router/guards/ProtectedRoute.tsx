import { Navigate, Outlet, useLocation } from 'react-router';
import { useAuth } from '@/features/auth/useAuth';
import { LoadingDiamond } from '@/design-system';
import { ROUTES } from '../../navigation/routePaths';
import { hasDashboardBeenVisited } from '../dashboardVisited';

/**
 * Gate for the whole authenticated shell. Order matters: (1) still
 * restoring session → full-page loading diamond, (2) no session →
 * /login (or /session-expired when a previously-valid live session was
 * just found invalid out of band — see `AuthContextValue.sessionExpired`),
 * (3) session exists but /dashboard hasn't been visited this browser
 * session yet → bounce to /dashboard first (the "landing rule", §7),
 * (4) otherwise render the requested route.
 */
export function ProtectedRoute() {
  const { status, sessionExpired } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return <LoadingDiamond size={40} fullPage />;
  }

  if (status === 'unauthenticated') {
    return (
      <Navigate
        to={sessionExpired ? ROUTES.sessionExpired : ROUTES.login}
        state={{ from: location }}
        replace
      />
    );
  }

  if (!hasDashboardBeenVisited() && location.pathname !== ROUTES.dashboard) {
    return <Navigate to={ROUTES.dashboard} replace />;
  }

  return <Outlet />;
}
