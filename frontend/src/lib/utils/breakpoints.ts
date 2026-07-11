/**
 * The two responsive breakpoints from spec §13. Every place that needs to
 * know "are we desktop/tablet/mobile" reads from here — no component
 * hard-codes 1280/768 itself.
 */
export const BREAKPOINTS = {
  /** Below this, the Command Rail collapses to a 72px icon rail. */
  tablet: 1280,
  /** Below this, the rail disappears entirely in favor of a drawer. */
  mobile: 768,
} as const;

export type NavMode = 'desktop' | 'tablet' | 'mobile';

export function navModeForWidth(width: number): NavMode {
  if (width < BREAKPOINTS.mobile) return 'mobile';
  if (width < BREAKPOINTS.tablet) return 'tablet';
  return 'desktop';
}
