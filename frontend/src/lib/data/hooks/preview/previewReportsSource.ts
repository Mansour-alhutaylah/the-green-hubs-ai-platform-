import { readyState, type DataState } from '../../contracts/common';
import type { ReportSummary, ReportsWorkspace } from '../../contracts/reports';
import { notFoundState, type ResourceState } from '../../contracts/resource';
import { PREVIEW_REPORTS, PREVIEW_REPORTS_PARTIAL } from '../../fixtures/previewReports';
import type { PreviewScenario } from '../../scenarios';
import { assertPreviewMode } from '../../source';
import { scenarioState } from './previewScenarioState';

/**
 * The Preview reports sources.
 *
 * Pure and synchronous: no `fetch`, no `apiRequest`, no Supabase call, and
 * no `await` here, so nothing in this module is *capable* of reaching the
 * network.
 *
 * `assertPreviewMode` throws if a Live build ever reaches one of these.
 * That matters more here than almost anywhere else: there is no reporting
 * endpoint at all, so a synthetic report rendered in Live would not be a
 * stale figure, it would be a document that does not exist.
 */
export function readPreviewReports(scenario: PreviewScenario): DataState<ReportsWorkspace> {
  assertPreviewMode('The Preview reports source');

  const early = scenarioState(scenario);
  if (early) return early;

  return scenario === 'partial'
    ? readyState(PREVIEW_REPORTS_PARTIAL, 'partial')
    : readyState(PREVIEW_REPORTS);
}

export function readPreviewReportDetail(
  scenario: PreviewScenario,
  reportId: string | undefined,
): ResourceState<ReportSummary> {
  assertPreviewMode('The Preview report source');

  const early = scenarioState(scenario);
  // A single report has no empty state; an "empty" scenario on a detail
  // route means the report is not there.
  if (early) return early.status === 'empty' ? notFoundState() : early;

  const workspace = scenario === 'partial' ? PREVIEW_REPORTS_PARTIAL : PREVIEW_REPORTS;
  const match = workspace.reports.find((report) => report.id === reportId);
  if (!match) return notFoundState();

  return readyState(match, scenario === 'partial' ? 'partial' : 'complete');
}
