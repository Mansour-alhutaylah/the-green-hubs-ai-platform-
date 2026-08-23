import { toEngagementSummaries } from '../../adapters/engagementAdapter';
import { readyState, type DataState } from '../../contracts/common';
import type { EngagementSummary } from '../../contracts/engagement';
import {
  notFoundState,
  type PaginatedCollection,
  type ResourceState,
} from '../../contracts/resource';
import { PREVIEW_ENGAGEMENTS } from '../../fixtures/previewWorkspace';
import type { PreviewScenario } from '../../scenarios';
import { assertPreviewMode } from '../../source';
import { scenarioState } from './previewScenarioState';

/**
 * The Preview engagement sources.
 *
 * Pure and synchronous: no `fetch`, no `apiRequest`, no Supabase call, and
 * no `await` — nothing here is *capable* of reaching the network, which is
 * what makes the zero-network property verifiable rather than intended.
 *
 * `assertPreviewMode` throws if a Live build ever reaches one of these,
 * rather than quietly rendering synthetic engagements to a real user.
 */
export function readPreviewEngagements(
  scenario: PreviewScenario,
  params: { page: number; pageSize: number },
): DataState<PaginatedCollection<EngagementSummary>> {
  assertPreviewMode('The Preview engagements source');

  const early = scenarioState(scenario);
  if (early) return early;

  const all = toEngagementSummaries(PREVIEW_ENGAGEMENTS);
  const start = (params.page - 1) * params.pageSize;

  return readyState(
    {
      items: all.slice(start, start + params.pageSize),
      page: params.page,
      pageSize: params.pageSize,
      // The total for the whole set, not for the slice above it — the
      // Preview page paginates against the same contract Live does.
      total: all.length,
    },
    scenario === 'partial' ? 'partial' : 'complete',
  );
}

export function readPreviewEngagementDetail(
  scenario: PreviewScenario,
  engagementId: string | undefined,
): ResourceState<EngagementSummary> {
  assertPreviewMode('The Preview engagement source');

  const early = scenarioState(scenario);
  if (early) return early.status === 'empty' ? notFoundState() : early;

  const match = toEngagementSummaries(PREVIEW_ENGAGEMENTS).find(
    (engagement) => engagement.id === engagementId,
  );
  if (!match) return notFoundState();

  return readyState(match, scenario === 'partial' ? 'partial' : 'complete');
}
