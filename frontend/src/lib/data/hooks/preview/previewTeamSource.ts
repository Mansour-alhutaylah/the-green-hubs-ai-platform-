import { readyState, type DataState } from '../../contracts/common';
import type { TeamDirectory } from '../../contracts/team';
import { PREVIEW_TEAM_MEMBERS } from '../../fixtures/previewWorkspace';
import type { PreviewScenario } from '../../scenarios';
import { assertPreviewMode } from '../../source';
import { scenarioState } from './previewScenarioState';

/**
 * The Preview team directory: one obviously synthetic member per canonical
 * role, so the full tier model is demonstrable without a backend.
 *
 * `isCompleteDirectory: true` is truthful *here* — the fixture set really is
 * everyone in the synthetic workspace. The Live directory reports `false`,
 * because one signed-in user is not a directory.
 *
 * Pure and synchronous, with `assertPreviewMode` as the fail-closed
 * backstop: a Live build reaching this throws rather than presenting
 * invented colleagues as real ones.
 */
export function readPreviewTeamDirectory(scenario: PreviewScenario): DataState<TeamDirectory> {
  assertPreviewMode('The Preview team directory source');

  const early = scenarioState(scenario);
  if (early) return early;

  const members = scenario === 'partial' ? PREVIEW_TEAM_MEMBERS.slice(0, 2) : PREVIEW_TEAM_MEMBERS;

  return readyState(
    { members, isCompleteDirectory: scenario !== 'partial' },
    scenario === 'partial' ? 'partial' : 'complete',
  );
}
