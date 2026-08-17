import { useSyncExternalStore } from 'react';
import { isCompactWidth } from '@/lib/utils/breakpoints';

function subscribe(callback: () => void): () => void {
  window.addEventListener('resize', callback);
  return () => window.removeEventListener('resize', callback);
}

function getSnapshot(): boolean {
  return isCompactWidth(window.innerWidth);
}

/** Server and pre-hydration default: not compact, so a floating overlay
 * renders in its normal place rather than flashing a trigger button that
 * then disappears. */
function getServerSnapshot(): boolean {
  return false;
}

/**
 * True at 480px and below, where a floating overlay covers page content
 * instead of sitting beside it.
 *
 * Built the same way as `useResponsiveNav`: one `useSyncExternalStore`
 * over a single `resize` listener, rather than a `matchMedia` listener per
 * component. The threshold lives in `breakpoints.ts` with the other two,
 * so no component hard-codes a width.
 */
export function useIsCompactViewport(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
