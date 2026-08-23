import { useEffect } from 'react';
import { matchPath, useLocation } from 'react-router';
import type { StringKey } from '@/lib/i18n/strings/en';
import { useLocale } from '@/lib/i18n/useLocale';
import { ROUTES } from '../navigation/routePaths';

/**
 * Ordered most-specific-first: `matchPath` would happily match
 * /documents/upload against /documents/:id, so the literal path has to be
 * offered first and the first hit wins.
 *
 * Detail routes deliberately resolve to a generic noun ("Document", not the
 * file's name). A browser title leaks into history, session restore, task
 * switchers, and screen-shared windows; the current privacy model makes no
 * commitment that a customer's document names may appear there.
 *
 * Every module already has an approved name in the nav dictionary, so those
 * are reused rather than restated — placeholder modules included, which is
 * what gives the Coming Soon pages their own titles. Session-expired and
 * access-denied likewise reuse their own page headings; only the routes
 * with no existing short name of their own get a `title.*` string.
 */
const TITLED_ROUTES: ReadonlyArray<{ path: string; key: StringKey }> = [
  { path: ROUTES.login, key: 'title.signIn' },
  { path: ROUTES.forgotPassword, key: 'title.forgotPassword' },
  { path: ROUTES.resetPassword, key: 'title.resetPassword' },
  { path: ROUTES.inviteAccept, key: 'title.invite' },
  { path: ROUTES.sessionExpired, key: 'auth.sessionExpired.heading' },
  { path: ROUTES.accessDenied, key: 'auth.accessDenied.heading' },

  { path: ROUTES.dashboard, key: 'nav.dashboard' },

  { path: ROUTES.reports, key: 'nav.reports' },
  { path: ROUTES.reportDetail, key: 'title.report' },

  { path: ROUTES.documentUpload, key: 'nav.upload' },
  { path: ROUTES.documents, key: 'nav.documents' },
  { path: ROUTES.documentDetail, key: 'title.document' },

  { path: ROUTES.engagements, key: 'nav.engagements' },
  { path: ROUTES.engagementDetail, key: 'title.engagement' },

  { path: ROUTES.analysis, key: 'nav.analysis' },
  { path: ROUTES.analysisRun, key: 'title.analysisRun' },

  { path: ROUTES.hubZero, key: 'nav.hubZero' },
  { path: ROUTES.carbon, key: 'nav.carbon' },
  { path: ROUTES.telemetry, key: 'nav.telemetry' },

  { path: ROUTES.organizations, key: 'nav.organizations' },
  { path: ROUTES.organizationDetail, key: 'title.organization' },

  { path: ROUTES.users, key: 'nav.users' },
  { path: ROUTES.frameworks, key: 'nav.frameworks' },
  { path: ROUTES.audit, key: 'nav.audit' },
  { path: ROUTES.settings, key: 'nav.settings' },

  { path: ROUTES.notifications, key: 'nav.notifications' },
  { path: ROUTES.profile, key: 'nav.profile' },
];

/**
 * Keeps `document.title` in step with the route, in the active locale.
 * Mounted once beside `RouteScrollReset` — a side-effect-only sibling of
 * `<Routes>` rather than a per-page hook, so no page can forget to set a
 * title and none of them has to know the brand suffix.
 *
 * `/` is only ever a redirect to /dashboard, so it shows the bare brand for
 * the frame it exists rather than flashing "Page not found"; anything else
 * unmatched is genuinely the 404 route.
 */
export function DocumentTitle() {
  const { pathname } = useLocation();
  const { t } = useLocale();

  useEffect(() => {
    const brand = t('brand.name');
    const matched = TITLED_ROUTES.find((route) =>
      matchPath({ path: route.path, end: true }, pathname),
    );

    if (matched) {
      document.title = `${t(matched.key)} | ${brand}`;
      return;
    }

    document.title = pathname === '/' ? brand : `${t('title.notFound')} | ${brand}`;
  }, [pathname, t]);

  return null;
}
