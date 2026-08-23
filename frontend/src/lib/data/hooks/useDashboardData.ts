import { unavailableState, type DataState } from '../contracts/common';
import type { DashboardLiveSummary } from '../contracts/dashboardLive';
import type { DashboardPreviewSupplement } from '../contracts/dashboardPreview';
import { getPreviewScenario } from '../scenarios';
import { isPreviewMode } from '../source';
import { useLiveDashboardSummary } from './live/liveDashboardSummarySource';
import { readPreviewDashboardSupplement } from './preview/previewDashboardSupplementSource';
import { NO_RETRY, type WorkspaceResource } from './sourceSelector';
import { toDataState } from './useAsyncResource';

/**
 * The Live dashboard. In a Preview build this resolves to `unavailable`
 * without calling anything: the Preview dashboard is a different contract
 * (`DashboardSnapshot` + `DashboardPreviewSupplement`) read through its own
 * hooks, precisely so a synthetic figure has no route into a Live card.
 */
export function useDashboardLiveSummary(): WorkspaceResource<DataState<DashboardLiveSummary>> {
  const preview = isPreviewMode();
  const live = useLiveDashboardSummary(!preview);

  if (preview) return { state: unavailableState(), retry: NO_RETRY };
  return { state: toDataState(live.state), retry: live.retry };
}

/**
 * The Preview-only dashboard breakdowns. `unavailable` in Live, where the
 * page renders none of them — and where the Preview source would throw if
 * it were somehow reached.
 */
export function useDashboardPreviewSupplement(): DataState<DashboardPreviewSupplement> {
  if (!isPreviewMode()) return unavailableState();
  return readPreviewDashboardSupplement(getPreviewScenario());
}
