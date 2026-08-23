import { readyState, type DataState } from '../../contracts/common';
import type { DashboardPreviewSupplement } from '../../contracts/dashboardPreview';
import {
  PREVIEW_DASHBOARD_SUPPLEMENT,
  PREVIEW_DASHBOARD_SUPPLEMENT_PARTIAL,
} from '../../fixtures/previewDashboardSupplement';
import type { PreviewScenario } from '../../scenarios';
import { assertPreviewMode } from '../../source';
import { scenarioState } from './previewScenarioState';

/**
 * The Preview-only dashboard breakdowns: documents by processing state, the
 * evidence-review lifecycle, an engagement roll-up, and a readiness figure.
 *
 * Pure and synchronous, and guarded by `assertPreviewMode` — a Live build
 * reaching this throws rather than putting a synthetic readiness percentage
 * on a real workspace's dashboard.
 */
export function readPreviewDashboardSupplement(
  scenario: PreviewScenario,
): DataState<DashboardPreviewSupplement> {
  assertPreviewMode('The Preview dashboard supplement source');

  const early = scenarioState(scenario);
  if (early) return early;

  return scenario === 'partial'
    ? readyState(PREVIEW_DASHBOARD_SUPPLEMENT_PARTIAL, 'partial')
    : readyState(PREVIEW_DASHBOARD_SUPPLEMENT);
}
