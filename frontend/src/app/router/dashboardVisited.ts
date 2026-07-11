/**
 * Landing rule (§7): "every successful authentication ends at /dashboard,
 * including deep-link logins... deep link honored after the dashboard has
 * been visited once per session." Tracked in `sessionStorage` (cleared per
 * browser session) — deliberately separate from the persisted auth session
 * in `localStorage`, so a fresh tab with an already-logged-in user still
 * bounces through /dashboard first, while the same tab honors deep links
 * for the rest of that browser session.
 */
const KEY = 'ghp:dashboard-visited';

export function hasDashboardBeenVisited(): boolean {
  return window.sessionStorage.getItem(KEY) === '1';
}

export function markDashboardVisited(): void {
  window.sessionStorage.setItem(KEY, '1');
}
