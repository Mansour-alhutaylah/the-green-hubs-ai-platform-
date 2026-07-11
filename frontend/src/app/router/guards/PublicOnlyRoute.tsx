import { Navigate, Outlet } from 'react-router';
import { useAuth } from '@/features/auth/useAuth';
import { LoadingDiamond } from '@/design-system';
import { ROUTES } from '../../navigation/routePaths';

/** Mirror image of ProtectedRoute — an already-authenticated user hitting
 * /login (or forgot/reset/invite) is sent straight to /dashboard instead. */
export function PublicOnlyRoute() {
  const { status } = useAuth();

  if (status === 'loading') {
    return <LoadingDiamond size={40} fullPage />;
  }

  if (status === 'authenticated') {
    return <Navigate to={ROUTES.dashboard} replace />;
  }

  return <Outlet />;
}
