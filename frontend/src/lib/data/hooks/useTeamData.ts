import type { DataState } from '../contracts/common';
import type { TeamDirectory } from '../contracts/team';
import { getPreviewScenario } from '../scenarios';
import { isPreviewMode } from '../source';
import { useLiveTeamDirectory } from './live/liveTeamSource';
import { readPreviewTeamDirectory } from './preview/previewTeamSource';
import { NO_RETRY, type WorkspaceResource } from './sourceSelector';
import { toDataState } from './useAsyncResource';

/**
 * The authenticated user and their colleagues.
 *
 * Live returns exactly one member — the caller, from `GET /auth/me` — with
 * `isCompleteDirectory: false`, because no organization-wide user endpoint
 * exists on this backend. Preview returns one obviously synthetic member
 * per canonical role.
 *
 * See `sourceSelector.ts` for why this gates rather than branches.
 */
export function useTeamDirectory(): WorkspaceResource<DataState<TeamDirectory>> {
  const preview = isPreviewMode();
  const live = useLiveTeamDirectory(!preview);

  if (preview) {
    return { state: readPreviewTeamDirectory(getPreviewScenario()), retry: NO_RETRY };
  }
  return { state: toDataState(live.state), retry: live.retry };
}
