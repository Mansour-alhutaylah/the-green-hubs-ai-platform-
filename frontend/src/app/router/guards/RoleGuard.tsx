import type { ReactNode } from 'react';
import { useHasMinTier } from '@/features/rbac/useHasMinTier';
import type { Role } from '@/features/rbac/roles';
import { NoAccessPage } from '@/features/errors/pages/NoAccessPage';

/**
 * Route-level RBAC gate for the handful of routes above Viewer tier
 * (Appendix A: /documents/upload, /users, /settings). Renders NoAccessPage
 * *inside* AppShell's Outlet (rail + context bar stay visible) rather than
 * redirecting away, matching §7's "404/no-access render inside the shell".
 */
export function RoleGuard({ minTier, children }: { minTier: Role; children: ReactNode }) {
  const allowed = useHasMinTier(minTier);
  return allowed ? <>{children}</> : <NoAccessPage />;
}
