import { Navigate, Outlet, useLocation } from 'react-router';
import { useAuth } from '@/features/auth/useAuth';
import { LoadingDiamond } from '@/design-system';
import { resolveReturnPath } from '../returnPath';

/**
 * Mirror image of ProtectedRoute — an already-authenticated visitor on
 * /login (or forgot/reset/invite) is sent onward rather than shown a
 * sign-in form.
 *
 * The destination is the protected route they were originally trying to
 * reach, when `ProtectedRoute` recorded one and it still validates;
 * /dashboard otherwise. Deciding it here as well as in `LoginPage` means
 * the deep link survives regardless of which of the two navigations lands
 * first after a successful sign-in.
 */
export function PublicOnlyRoute() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return <LoadingDiamond size={40} fullPage />;
  }

  if (status === 'authenticated') {
    return <Navigate to={resolveReturnPath(location.state)} replace />;
  }

  return <Outlet />;
}
