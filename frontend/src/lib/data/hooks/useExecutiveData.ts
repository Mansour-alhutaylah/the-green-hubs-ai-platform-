import { unavailableState, type DataState } from '../contracts/common';
import type { ExecutiveSummary } from '../contracts/executive';
import type { ReportSummary, ReportsWorkspace } from '../contracts/reports';
import { notFoundState, type ResourceState } from '../contracts/resource';
import { getPreviewScenario } from '../scenarios';
import { isPreviewMode } from '../source';
import { readPreviewExecutiveSummary } from './preview/previewExecutiveSource';
import { readPreviewReportDetail, readPreviewReports } from './preview/previewReportsSource';

/**
 * The Preview-only executive and reporting selectors.
 *
 * Each returns `unavailable` in Live without calling anything. That is not
 * a placeholder for work that is coming: no endpoint computes an evidence
 * readiness figure, a framework coverage percentage, or a report, so
 * `unavailable` is the truthful answer and the pages render a stated
 * unavailable surface rather than an empty list.
 *
 * There is deliberately no Live counterpart hook to pair with these. A
 * `useLiveReports` that returned an empty collection would let a Live page
 * render "0 reports", which claims the workspace has none when the truth
 * is that the product cannot tell.
 */
export function useExecutiveSummary(): DataState<ExecutiveSummary> {
  if (!isPreviewMode()) return unavailableState();
  return readPreviewExecutiveSummary(getPreviewScenario());
}

export function useReportsWorkspace(): DataState<ReportsWorkspace> {
  if (!isPreviewMode()) return unavailableState();
  return readPreviewReports(getPreviewScenario());
}

export function useReportDetail(reportId: string | undefined): ResourceState<ReportSummary> {
  if (!isPreviewMode()) return unavailableState();
  if (!reportId) return notFoundState();
  return readPreviewReportDetail(getPreviewScenario(), reportId);
}
