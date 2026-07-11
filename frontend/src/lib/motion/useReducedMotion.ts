import { useSyncExternalStore } from 'react';

const QUERY = '(prefers-reduced-motion: reduce)';

function subscribe(callback: () => void): () => void {
  const mediaQueryList = window.matchMedia(QUERY);
  mediaQueryList.addEventListener('change', callback);
  return () => mediaQueryList.removeEventListener('change', callback);
}

function getSnapshot(): boolean {
  return window.matchMedia(QUERY).matches;
}

function getServerSnapshot(): boolean {
  return false;
}

/** §17 / §18: components with bespoke (non-CSS-token-driven) animation —
 * e.g. the LoadingDiamond's clockwise draw — read this to skip it outright,
 * since the CSS-token duration collapse only helps transitions/animations
 * that consume the --motion-* custom properties directly. */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
