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
  /**
   * At or below this, a floating overlay has no room to sit beside page
   * content and covers it instead, so overlays collapse behind an explicit
   * trigger.
   *
   * Deliberately distinct from `mobile`. A 600px tablet-portrait viewport
   * still has room for a corner panel; a 360px phone does not, and there
   * the same panel lands on top of the header, the primary actions, or a
   * KPI card.
   */
  compact: 480,
} as const;

export type NavMode = 'desktop' | 'tablet' | 'mobile';

export function navModeForWidth(width: number): NavMode {
  if (width < BREAKPOINTS.mobile) return 'mobile';
  if (width < BREAKPOINTS.tablet) return 'tablet';
  return 'desktop';
}

/** True when a floating overlay would obstruct rather than accompany the
 * page. Inclusive of the breakpoint itself: 480px is compact. */
export function isCompactWidth(width: number): boolean {
  return width <= BREAKPOINTS.compact;
}
