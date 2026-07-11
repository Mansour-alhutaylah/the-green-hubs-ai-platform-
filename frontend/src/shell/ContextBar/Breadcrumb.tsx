import { useLocation } from 'react-router';
import { useLocale } from '@/lib/i18n/useLocale';
import { activeNavItemId, NAV_ITEMS } from '@/app/navigation/navConfig';
import { ROUTES } from '@/app/navigation/routePaths';

/**
 * §3.2: hidden on the dashboard ("the dashboard greets instead"). Derived
 * from the same nav-item/pathname matching CommandRail uses for its active
 * state (`activeNavItemId`) rather than React Router's `useMatches` +
 * route `handle` — that API requires a data router
 * (createBrowserRouter/RouterProvider), and this app deliberately stays on
 * the declarative `<Routes>` API since Phase 1 has no route loaders/actions
 * to justify the data router's extra ceremony.
 */
export function Breadcrumb() {
  const { t } = useLocale();
  const location = useLocation();

  if (location.pathname === ROUTES.dashboard) return null;

  const itemId = activeNavItemId(location.pathname);
  const item = NAV_ITEMS.find((navItem) => navItem.id === itemId);
  if (!item) return null;

  return (
    <nav aria-label="Breadcrumb" className="text-meta">
      <span className="font-bold text-forest-900">{t(item.labelKey)}</span>
    </nav>
  );
}
