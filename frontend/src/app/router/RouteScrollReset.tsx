import { useLayoutEffect } from 'react';
import { useLocation } from 'react-router';

/**
 * Top-level route changes always start at the top of the window scroll container.
 * Hash navigation is left to the browser so in-page anchors continue to work.
 * Back and Forward navigation between pages intentionally follows the same rule.
 */
export function RouteScrollReset() {
  const { hash, pathname } = useLocation();

  useLayoutEffect(() => {
    if (hash) {
      return;
    }

    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, [hash, pathname]);

  return null;
}
