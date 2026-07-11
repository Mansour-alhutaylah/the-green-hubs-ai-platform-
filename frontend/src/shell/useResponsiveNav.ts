import { useSyncExternalStore } from 'react';
import { navModeForWidth, type NavMode } from '@/lib/utils/breakpoints';

function subscribe(callback: () => void): () => void {
  window.addEventListener('resize', callback);
  return () => window.removeEventListener('resize', callback);
}

function getSnapshot(): NavMode {
  return navModeForWidth(window.innerWidth);
}

function getServerSnapshot(): NavMode {
  return 'desktop';
}

/** The one place §13's 1280px/768px breakpoints are evaluated — CommandRail,
 * AppShell, and MobileDrawer all read from here rather than each running
 * their own matchMedia listener. */
export function useResponsiveNav(): NavMode {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
