import { lazy } from 'react';
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
 * The IA's route tree (§7). Public auth routes and the authenticated shell
 * are separate layout branches; every route inside AppShell needs only
 * `ProtectedRoute`'s authentication check unless it's wrapped in
 * `RoleGuard` — those three (Upload, Users, Settings) pull their `minTier`
 * from navConfig.ts so Appendix A's table is encoded exactly once.
 *
 * This stays on React Router's declarative `<Routes>` API rather than a
 * data router (createBrowserRouter/RouterProvider) — Phase 1 has no route
 * loaders/actions to justify it, and Breadcrumb derives its label from
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
          <Route path={ROUTES.login} element={<LoginPage />} />
          <Route path={ROUTES.forgotPassword} element={<ForgotPasswordPage />} />
          <Route path={ROUTES.resetPassword} element={<ResetPasswordPage />} />
          <Route path={ROUTES.inviteAccept} element={<InviteAcceptPage />} />
        </Route>

        {/* Reachable regardless of session state — a session that just
          expired, or an access-denied bounce, must render even for an
          already-authenticated or already-unauthenticated visitor, so
          neither PublicOnlyRoute nor ProtectedRoute wraps these. */}
        <Route path={ROUTES.sessionExpired} element={<SessionExpiredPage />} />
        <Route path={ROUTES.accessDenied} element={<AccessDeniedPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to={ROUTES.dashboard} replace />} />
            <Route path={ROUTES.dashboard} element={<DashboardPage />} />

            <Route path={ROUTES.reports} element={<ReportsListPage />} />
            <Route path={ROUTES.reportDetail} element={<ReportDetailPage />} />

            <Route path={ROUTES.documents} element={<DocumentsListPage />} />
            <Route path={ROUTES.documentDetail} element={<DocumentDetailPage />} />
            <Route
              path={ROUTES.documentUpload}
              element={
                <RoleGuard minTier={findNavItem('upload').minTier}>
                  <DocumentUploadPage />
                </RoleGuard>
              }
            />

            <Route path={ROUTES.analysis} element={<AnalysisListPage />} />
            <Route path={ROUTES.analysisRun} element={<AnalysisRunPage />} />

            <Route path={ROUTES.hubZero} element={<HubZeroPage />} />
            <Route path={ROUTES.carbon} element={<CarbonPage />} />
            <Route path={ROUTES.telemetry} element={<TelemetryPage />} />

            <Route path={ROUTES.organizations} element={<OrganizationsListPage />} />
            <Route path={ROUTES.organizationDetail} element={<OrganizationDetailPage />} />
            <Route
              path={ROUTES.users}
              element={
                <RoleGuard minTier={findNavItem('users').minTier}>
                  <UsersPage />
                </RoleGuard>
              }
            />
            <Route path={ROUTES.frameworks} element={<FrameworksPage />} />
            <Route path={ROUTES.audit} element={<AuditPage />} />
            <Route
              path={ROUTES.settings}
              element={
                <RoleGuard minTier={findNavItem('settings').minTier}>
                  <SettingsPage />
                </RoleGuard>
              }
            />

            <Route path={ROUTES.notifications} element={<NotificationsPage />} />
            <Route path={ROUTES.profile} element={<ProfilePage />} />

            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>
      </Routes>
    </>
  );
}
