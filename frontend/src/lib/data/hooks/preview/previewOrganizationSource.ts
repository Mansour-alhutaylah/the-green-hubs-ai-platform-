import { toOrganizationSummaries } from '../../adapters/organizationAdapter';
import { readyState, type DataState } from '../../contracts/common';
import type { OrganizationSummary } from '../../contracts/organization';
import {
  notFoundState,
  type PaginatedCollection,
  type ResourceState,
} from '../../contracts/resource';
import { PREVIEW_ORGANIZATIONS } from '../../fixtures/previewWorkspace';
import type { PreviewScenario } from '../../scenarios';
import { assertPreviewMode } from '../../source';
import { scenarioState } from './previewScenarioState';

/**
 * The Preview organization sources.
 *
 * Pure and synchronous, exactly like the F1 Preview dashboard source. There
 * is no `fetch`, no `apiRequest`, no Supabase call, and no `await` anywhere
 * in this module — not merely "we don't call the network", but *nothing
 * here is capable of it*. That is what makes the zero-network property
 * checkable rather than aspirational.
 *
 * `assertPreviewMode` is the fail-closed backstop on every entry point: if
 * a Live build ever reached one of these it throws, instead of quietly
 * putting a synthetic organization in front of a real authenticated user.
 *
 * The fixtures are authored in the real wire shape and pass through the
 * same adapter Live responses do, so a fixture that drifts from the backend
 * contract stops compiling.
 */
export function readPreviewOrganizations(
  scenario: PreviewScenario,
): DataState<PaginatedCollection<OrganizationSummary>> {
  assertPreviewMode('The Preview organizations source');

  const early = scenarioState(scenario);
  if (early) return early;

  const items = toOrganizationSummaries(PREVIEW_ORGANIZATIONS);
  return readyState(
    {
      items,
      page: 1,
      pageSize: items.length,
      // The fixture list is the complete synthetic set, and the count is
      // stated as such — the same field a Live response would carry a
      // server-computed `total` in.
      total: items.length,
    },
    scenario === 'partial' ? 'partial' : 'complete',
  );
}

export function readPreviewOrganizationDetail(
  scenario: PreviewScenario,
  organizationId: string | undefined,
): ResourceState<OrganizationSummary> {
  assertPreviewMode('The Preview organization source');

  const early = scenarioState(scenario);
  // A single entity has no empty state; an "empty" scenario on a detail
  // route means the entity is not there.
  if (early) return early.status === 'empty' ? notFoundState() : early;

  const match = toOrganizationSummaries(PREVIEW_ORGANIZATIONS).find(
    (organization) => organization.id === organizationId,
  );
  if (!match) return notFoundState();

  return readyState(match, scenario === 'partial' ? 'partial' : 'complete');
}
