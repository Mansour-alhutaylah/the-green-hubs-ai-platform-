import { Suspense, useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router';
import { Icon, LoadingDiamond } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { useResponsiveNav } from './useResponsiveNav';
import { useGlobalShortcuts } from './useGlobalShortcuts';
import { CommandRail } from './CommandRail/CommandRail';
import { useRailPreference } from './CommandRail/useRailPreference';
import { MobileDrawer } from './MobileDrawer/MobileDrawer';
import { ContextBar } from './ContextBar/ContextBar';
import { PageViewport } from './PageViewport';
import { RouteErrorBoundary } from './RouteErrorBoundary';
import { SkipLink } from './SkipLink';

/**
 * The authenticated layout every protected route renders inside (§7/§8):
 * Command Rail (desktop/tablet) or a drawer-triggering hamburger (mobile),
 * the Context Bar, and the PageViewport wrapping the routed page.
 */
export function AppShell() {
  const navMode = useResponsiveNav();
  const isMobile = navMode === 'mobile';
  const { isCollapsed, toggle } = useRailPreference(navMode);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const location = useLocation();
  const { t } = useLocale();

  useGlobalShortcuts();

  // Tapping a drawer nav item navigates but leaves the dialog mounted over
  // the destination page — the drawer owns no route state of its own, so
  // the shell closes it on every navigation. Keyed on `location.key` rather
  // than `pathname` so tapping the item for the page you're already on
  // still dismisses the drawer instead of appearing to do nothing.
  useEffect(() => {
    setDrawerOpen(false);
  }, [location.key]);

  // Rotating a phone to landscape (or any resize past 768px) unmounts the
  // drawer; without clearing the flag, coming back to mobile width would
  // re-open a drawer the user never asked for.
  useEffect(() => {
    if (!isMobile) setDrawerOpen(false);
  }, [isMobile]);

  return (
    <div className="app-atmosphere min-h-screen bg-paper-50">
      <SkipLink />
      {!isMobile && <CommandRail isCollapsed={isCollapsed} onToggle={toggle} />}
      {isMobile && <MobileDrawer open={drawerOpen} onOpenChange={setDrawerOpen} />}

      <div
        style={{
          marginInlineStart: isMobile
            ? 0
            : isCollapsed
              ? 'var(--size-rail-collapsed)'
              : 'var(--size-rail)',
        }}
        className="relative z-10 flex min-h-screen flex-col transition-[margin] duration-[var(--motion-base)]"
      >
        <ContextBar
          menuButton={
            isMobile ? (
              <button
                type="button"
                aria-label={t('shell.nav.open')}
                aria-expanded={drawerOpen}
                onClick={() => setDrawerOpen(true)}
                // 44px square: the drawer trigger is the only way back to
                // navigation on a phone, so it carries a full touch target
                // instead of the icon's own 20px box.
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-m border border-leaf-300 bg-mist-50 text-forest-800 shadow-card transition-colors hover:bg-mint-100"
              >
                <Icon name="menu" size={20} />
              </button>
            ) : undefined
          }
        />
        <PageViewport>
          {/* Keyed by pathname so a route that errored doesn't stay stuck
              once the user navigates elsewhere and back (§14.9). */}
          <RouteErrorBoundary key={location.pathname}>
            <Suspense fallback={<LoadingDiamond size={40} fullPage />}>
              <Outlet />
            </Suspense>
          </RouteErrorBoundary>
        </PageViewport>
      </div>
    </div>
  );
}
