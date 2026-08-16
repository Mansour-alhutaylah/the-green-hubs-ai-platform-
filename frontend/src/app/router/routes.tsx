import { lazy, type ReactElement } from 'react';
import { Navigate, Route, Routes } from 'react-router';
import { AppShell } from '@/shell/AppShell';
import { findNavItem } from '@/app/navigation/navConfig';
import { LoginPage } from '@/features/auth/pages/LoginPage';
import { ForgotPasswordPage } from '@/features/auth/pages/ForgotPasswordPage';
import { ResetPasswordPage } from '@/features/auth/pages/ResetPasswordPage';
import { InviteAcceptPage } from '@/features/auth/pages/InviteAcceptPage';
import { SessionExpiredPage } from '@/features/auth/pages/SessionExpiredPage';
import { AccessDeniedPage } from '@/features/auth/pages/AccessDeniedPage';
import { NotFoundPage } from '@/features/errors/pages/NotFoundPage';
import { ROUTES } from '../navigation/routePaths';
import {
  PROTECTED_ROUTE_KEYS,
  PUBLIC_ONLY_ROUTE_KEYS,
  UNGUARDED_ROUTE_KEYS,
  type ProtectedRouteKey,
  type PublicOnlyRouteKey,
  type UnguardedRouteKey,
} from './routeRegistry';
import { ProtectedRoute } from './guards/ProtectedRoute';
import { PublicOnlyRoute } from './guards/PublicOnlyRoute';
import { RoleGuard } from './guards/RoleGuard';
import { RouteScrollReset } from './RouteScrollReset';
import { DocumentTitle } from './DocumentTitle';

/**
 * Every business-module page (everything behind auth) is code-split with
 * `React.lazy` — AppShell wraps the `<Outlet/>` in one shared `<Suspense>`,
 * so none of these routes bundle into the initial chunk. Auth pages stay
 * eagerly imported since /login is the unauthenticated entry point itself
 * (lazy-loading the first thing a user sees would just trade a blank
 * screen for a loading flash); AppShell/NotFoundPage are shell
 * infrastructure, not business modules.
 */
const DashboardPage = lazy(() =>
  import('@/features/dashboard/pages/DashboardPage').then((m) => ({ default: m.DashboardPage })),
);
const ReportsListPage = lazy(() =>
  import('@/features/reports/pages/ReportsListPage').then((m) => ({
    default: m.ReportsListPage,
  })),
);
const ReportDetailPage = lazy(() =>
  import('@/features/reports/pages/ReportDetailPage').then((m) => ({
    default: m.ReportDetailPage,
  })),
);
const DocumentsListPage = lazy(() =>
  import('@/features/documents/pages/DocumentsListPage').then((m) => ({
    default: m.DocumentsListPage,
  })),
);
const DocumentDetailPage = lazy(() =>
  import('@/features/documents/pages/DocumentDetailPage').then((m) => ({
    default: m.DocumentDetailPage,
  })),
);
const DocumentUploadPage = lazy(() =>
  import('@/features/documents/pages/DocumentUploadPage').then((m) => ({
    default: m.DocumentUploadPage,
  })),
);
const AnalysisListPage = lazy(() =>
  import('@/features/analysis/pages/AnalysisListPage').then((m) => ({
    default: m.AnalysisListPage,
  })),
);
const AnalysisRunPage = lazy(() =>
  import('@/features/analysis/pages/AnalysisRunPage').then((m) => ({
    default: m.AnalysisRunPage,
  })),
);
const OrganizationsListPage = lazy(() =>
  import('@/features/organizations/pages/OrganizationsListPage').then((m) => ({
    default: m.OrganizationsListPage,
  })),
);
const OrganizationDetailPage = lazy(() =>
  import('@/features/organizations/pages/OrganizationDetailPage').then((m) => ({
    default: m.OrganizationDetailPage,
  })),
);
const UsersPage = lazy(() =>
  import('@/features/users/pages/UsersPage').then((m) => ({ default: m.UsersPage })),
);
const SettingsPage = lazy(() =>
  import('@/features/settings/pages/SettingsPage').then((m) => ({ default: m.SettingsPage })),
);
const NotificationsPage = lazy(() =>
  import('@/features/notifications/pages/NotificationsPage').then((m) => ({
    default: m.NotificationsPage,
  })),
);
const ProfilePage = lazy(() =>
  import('@/features/profile/pages/ProfilePage').then((m) => ({ default: m.ProfilePage })),
);
const HubZeroPage = lazy(() =>
  import('@/features/placeholders/pages/HubZeroPage').then((m) => ({ default: m.HubZeroPage })),
);
const CarbonPage = lazy(() =>
  import('@/features/placeholders/pages/CarbonPage').then((m) => ({ default: m.CarbonPage })),
);
const TelemetryPage = lazy(() =>
  import('@/features/placeholders/pages/TelemetryPage').then((m) => ({
    default: m.TelemetryPage,
  })),
);
const FrameworksPage = lazy(() =>
  import('@/features/placeholders/pages/FrameworksPage').then((m) => ({
    default: m.FrameworksPage,
  })),
);
const AuditPage = lazy(() =>
  import('@/features/placeholders/pages/AuditPage').then((m) => ({ default: m.AuditPage })),
);

/**
 * What each route renders. These three maps are exhaustive `Record`s over
 * the route-group key types from `routeRegistry.ts`, which is what keeps
 * the two files from drifting: add a key to `ROUTES` and it is classified
 * as protected by subtraction, and this file stops compiling until it says
 * what that route renders. Nothing here re-states a path.
 */
const PUBLIC_ONLY_ELEMENTS: Record<PublicOnlyRouteKey, ReactElement> = {
  login: <LoginPage />,
  forgotPassword: <ForgotPasswordPage />,
  resetPassword: <ResetPasswordPage />,
  inviteAccept: <InviteAcceptPage />,
};

const UNGUARDED_ELEMENTS: Record<UnguardedRouteKey, ReactElement> = {
  sessionExpired: <SessionExpiredPage />,
  accessDenied: <AccessDeniedPage />,
};

const PROTECTED_ELEMENTS: Record<ProtectedRouteKey, ReactElement> = {
  dashboard: <DashboardPage />,
  reports: <ReportsListPage />,
  reportDetail: <ReportDetailPage />,
  documents: <DocumentsListPage />,
  documentDetail: <DocumentDetailPage />,
  documentUpload: <DocumentUploadPage />,
  analysis: <AnalysisListPage />,
  analysisRun: <AnalysisRunPage />,
  hubZero: <HubZeroPage />,
  carbon: <CarbonPage />,
  telemetry: <TelemetryPage />,
  organizations: <OrganizationsListPage />,
  organizationDetail: <OrganizationDetailPage />,
  users: <UsersPage />,
  frameworks: <FrameworksPage />,
  audit: <AuditPage />,
  settings: <SettingsPage />,
  notifications: <NotificationsPage />,
  profile: <ProfilePage />,
};

/**
 * The handful of protected routes above Viewer tier (Appendix A). The value
 * is a navConfig item id, so the minimum tier itself is still encoded
 * exactly once — in navConfig.ts — and read from there.
 */
const PROTECTED_ROUTE_GATES: Partial<Record<ProtectedRouteKey, string>> = {
  documentUpload: 'upload',
  users: 'users',
  settings: 'settings',
};

/**
 * The IA's route tree (§7). Public auth routes, the two session-state
 * routes, and the authenticated shell are separate layout branches; every
 * route inside AppShell needs only `ProtectedRoute`'s authentication check
 * unless `PROTECTED_ROUTE_GATES` names a tier for it.
 *
 * The branches are generated from `routeRegistry.ts` rather than written
 * out one `<Route>` at a time. That is the point: the registry is the
 * single classification the guards also read, so a route cannot exist in
 * the tree while being invisible to `isKnownProtectedPath` (which would
 * 404 an unauthenticated deep link to a real page) or to the post-login
 * return-path validator (which would silently drop the user on /dashboard).
 *
 * React Router ranks `<Routes>` children by specificity rather than source
 * order, so generating them in `ROUTES` declaration order is safe —
 * `/documents/upload` still wins over `/documents/:id`.
 *
 * This stays on React Router's declarative `<Routes>` API rather than a
 * data router (createBrowserRouter/RouterProvider) — there are no route
 * loaders/actions to justify one, and Breadcrumb derives its label from
 * navConfig + the current pathname instead of the data-router-only
 * `handle`/`useMatches` mechanism.
 */
export function AppRoutes() {
  return (
    <>
      <RouteScrollReset />
      <DocumentTitle />
      <Routes>
        <Route element={<PublicOnlyRoute />}>
          {PUBLIC_ONLY_ROUTE_KEYS.map((key) => (
            <Route key={key} path={ROUTES[key]} element={PUBLIC_ONLY_ELEMENTS[key]} />
          ))}
        </Route>

        {/* Reachable regardless of session state — a session that just
          expired, or an access-denied bounce, must render even for an
          already-authenticated or already-unauthenticated visitor, so
          neither PublicOnlyRoute nor ProtectedRoute wraps these. */}
        {UNGUARDED_ROUTE_KEYS.map((key) => (
          <Route key={key} path={ROUTES[key]} element={UNGUARDED_ELEMENTS[key]} />
        ))}

        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to={ROUTES.dashboard} replace />} />

            {PROTECTED_ROUTE_KEYS.map((key) => {
              const gate = PROTECTED_ROUTE_GATES[key];
              return (
                <Route
                  key={key}
                  path={ROUTES[key]}
                  element={
                    gate ? (
                      <RoleGuard minTier={findNavItem(gate).minTier}>
                        {PROTECTED_ELEMENTS[key]}
                      </RoleGuard>
                    ) : (
                      PROTECTED_ELEMENTS[key]
                    )
                  }
                />
              );
            })}

            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>
      </Routes>
    </>
  );
}
