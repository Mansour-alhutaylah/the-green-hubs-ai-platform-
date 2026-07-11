import { useCallback, useState } from 'react';
import type { NavMode } from '@/lib/utils/breakpoints';

const STORAGE_KEY = 'ghp:rail-pref';
type RailPreference = 'expanded' | 'collapsed';

function readStoredPreference(): RailPreference | null {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === 'expanded' || stored === 'collapsed' ? stored : null;
}

/**
 * §3.3: "at <1280px viewport the rail auto-collapses to 72px... A pin
 * control lets users force either state; preference persists per user."
 * Until the user explicitly pins a state, the rail follows the breakpoint
 * (full at desktop, icon-only at tablet); once pinned, that choice sticks
 * regardless of viewport width until toggled again.
 */
export function useRailPreference(navMode: NavMode): { isCollapsed: boolean; toggle: () => void } {
  const [explicitPreference, setExplicitPreference] = useState<RailPreference | null>(
    readStoredPreference,
  );

  const defaultCollapsed = navMode === 'tablet';
  const isCollapsed = explicitPreference ? explicitPreference === 'collapsed' : defaultCollapsed;

  const toggle = useCallback(() => {
    const next: RailPreference = isCollapsed ? 'expanded' : 'collapsed';
    setExplicitPreference(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  }, [isCollapsed]);

  return { isCollapsed, toggle };
}
