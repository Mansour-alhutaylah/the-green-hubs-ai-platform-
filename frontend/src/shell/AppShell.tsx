import { Suspense, useState } from 'react';
import { Outlet, useLocation } from 'react-router';
import { Icon, LoadingDiamond } from '@/design-system';
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

  useGlobalShortcuts();

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
                aria-label="Open navigation"
                onClick={() => setDrawerOpen(true)}
                className="rounded-m border border-leaf-300 bg-mist-50 p-2 text-forest-800 shadow-card transition-colors hover:bg-mint-100"
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
