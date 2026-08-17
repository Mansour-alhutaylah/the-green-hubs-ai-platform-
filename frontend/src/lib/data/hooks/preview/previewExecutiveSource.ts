import { readyState, type DataState } from '../../contracts/common';
import type { ExecutiveSummary } from '../../contracts/executive';
import {
  PREVIEW_EXECUTIVE_SUMMARY,
  PREVIEW_EXECUTIVE_SUMMARY_PARTIAL,
} from '../../fixtures/previewExecutive';
import type { PreviewScenario } from '../../scenarios';
import { assertPreviewMode } from '../../source';
import { scenarioState } from './previewScenarioState';

/**
 * The Preview executive command-centre source.
 *
 * Pure and synchronous: no `fetch`, no `apiRequest`, no Supabase call, and
 * no `await` anywhere in this module. Not merely "we don't call the
 * network" but *nothing here is capable of it*, which is what makes the
 * zero-network property checkable rather than aspirational.
 *
 * `assertPreviewMode` is the fail-closed backstop: a Live build reaching
 * this throws instead of quietly putting a synthetic readiness figure on a
 * real workspace's dashboard.
 */
export function readPreviewExecutiveSummary(
  scenario: PreviewScenario,
): DataState<ExecutiveSummary> {
  assertPreviewMode('The Preview executive summary source');

  const early = scenarioState(scenario);
  if (early) return early;

  return scenario === 'partial'
    ? readyState(PREVIEW_EXECUTIVE_SUMMARY_PARTIAL, 'partial')
    : readyState(PREVIEW_EXECUTIVE_SUMMARY);
}
