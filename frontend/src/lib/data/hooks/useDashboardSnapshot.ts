import { isPreviewMode } from '../source';
import type { DataState } from '../contracts/common';
import type { DashboardSnapshot } from '../contracts/dashboard';
import { readLiveDashboardState } from './live/liveDashboardSource';
import { readPreviewDashboardState } from './preview/previewDashboardSource';

/**
 * The dashboard's single data entry point — the first consumer of the
 * typed Live/Preview foundation. Pages read this; they never import a
 * fixture module directly.
 *
 * The branch is on the build-time mode, so a Live build can never reach the
 * Preview source, and the Preview source additionally asserts the mode
 * itself. Both sources are plain functions rather than nested hooks, so
 * there is no conditional-hook hazard here.
 */
export function useDashboardSnapshot(): DataState<DashboardSnapshot> {
  return isPreviewMode() ? readPreviewDashboardState() : readLiveDashboardState();
}
