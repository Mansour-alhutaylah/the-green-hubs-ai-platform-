import { assertPreviewMode } from '../../source';
import { getPreviewScenario, type PreviewScenario } from '../../scenarios';
import {
  emptyState,
  errorState,
  forbiddenState,
  loadingState,
  readyState,
  type DataState,
} from '../../contracts/common';
import type { DashboardSnapshot } from '../../contracts/dashboard';
import { toDashboardSnapshot } from '../../adapters/dashboardAdapter';
import {
  PREVIEW_DASHBOARD_SOURCE,
  PREVIEW_DASHBOARD_SOURCE_PARTIAL,
} from '../../fixtures/previewDashboard';

/**
 * The Preview dashboard source. Pure and synchronous by design: it makes no
 * `fetch`, no Supabase call, and no `apiRequest` — there is nothing here
 * that *could* reach the network, which is what makes the zero-network
 * boundary verifiable rather than merely intended.
 *
 * `assertPreviewMode` is the fail-closed backstop: if a Live build ever
 * reached this function it would throw instead of quietly showing
 * fabricated metrics to a real authenticated user.
 */
export function buildPreviewDashboardState(
  scenario: PreviewScenario,
): DataState<DashboardSnapshot> {
  assertPreviewMode('The Preview dashboard source');

  switch (scenario) {
    case 'loading':
      return loadingState();
    case 'error':
      return errorState();
    case 'forbidden':
      return forbiddenState();
    case 'empty':
      return emptyState();
    case 'partial':
      return readyState(toDashboardSnapshot(PREVIEW_DASHBOARD_SOURCE_PARTIAL), 'partial');
    case 'populated':
    default:
      return readyState(toDashboardSnapshot(PREVIEW_DASHBOARD_SOURCE));
  }
}

/** Reads the build-time scenario and resolves the Preview state. Not a
 * React hook (it owns no state), so the selector below can call it inside a
 * branch without bending the rules of hooks. */
export function readPreviewDashboardState(): DataState<DashboardSnapshot> {
  return buildPreviewDashboardState(getPreviewScenario());
}
