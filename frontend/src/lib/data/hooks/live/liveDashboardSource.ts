import { unavailableState, type DataState } from '../../contracts/common';
import type { DashboardSnapshot } from '../../contracts/dashboard';

/**
 * The Live dashboard source.
 *
 * The Backend has no dashboard-summary endpoint yet (no aggregate metrics,
 * activity feed, or processing-queue resource exists), so there is nothing
 * truthful to fetch. This reports `unavailable` and the page states plainly
 * that dashboard metrics are not connected — it does not invent a metric,
 * and it never falls back to Preview fixtures.
 *
 * When F2 adds a real endpoint, this is where the request goes: its wire
 * response maps through `adapters/dashboardAdapter.ts` into the same
 * `DashboardSnapshot` the Preview source already produces, and the page
 * above it does not change.
 */
export function readLiveDashboardState(): DataState<DashboardSnapshot> {
  return unavailableState();
}
