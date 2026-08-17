import { useCallback } from 'react';
import { getEngagement, listEngagements } from '@/lib/api/endpoints/engagements';
import { toEngagementSummaries, toEngagementSummary } from '../../adapters/engagementAdapter';
import type { EngagementSummary } from '../../contracts/engagement';
import type { PaginatedCollection } from '../../contracts/resource';
import { useAsyncResource, type AsyncResource } from '../useAsyncResource';

/**
 * The Live engagement sources.
 *
 * Imports the engagements endpoint client and the wire→domain adapter, and
 * **nothing from `../../fixtures/`** — so a Live failure has no synthetic
 * value in scope to fall back to. It resolves to `error`, and the page says
 * so.
 */

/** Module-level so its identity is stable across renders. */
const hasNoRows = (collection: PaginatedCollection<unknown>): boolean => collection.total === 0;

/**
 * `GET /api/v1/engagements`.
 *
 * The route accepts an optional `organization_id` filter and this never
 * sends one — see `endpoints/engagements.ts`. Tenant scope is the server's
 * decision, derived from the bearer token; a client-chosen id here could
 * only narrow a scope already decided while making the request look like a
 * tenancy assertion.
 */
export function useLiveEngagements(
  enabled: boolean,
  params: { page: number; pageSize: number },
): AsyncResource<PaginatedCollection<EngagementSummary>> {
  const { page, pageSize } = params;

  const load = useCallback(
    async (signal: AbortSignal): Promise<PaginatedCollection<EngagementSummary>> => {
      const response = await listEngagements({ page, page_size: pageSize }, signal);
      return {
        items: toEngagementSummaries(response.items),
        page: response.page,
        pageSize: response.page_size,
        // `EngagementService.list` computes this with its own tenant-scoped
        // `count()`. It is the total for the whole filtered query, not for
        // the page that came back.
        total: response.total,
      };
    },
    [page, pageSize],
  );

  return useAsyncResource(enabled, load, { isEmpty: hasNoRows });
}

/** `GET /api/v1/engagements/{id}` — 404 for anything outside the caller's
 * own organization, surfaced as `not-found`. */
export function useLiveEngagementDetail(
  enabled: boolean,
  engagementId: string | undefined,
): AsyncResource<EngagementSummary> {
  const load = useCallback(
    async (signal: AbortSignal): Promise<EngagementSummary> => {
      if (!engagementId) throw new Error('An engagement id is required.');
      return toEngagementSummary(await getEngagement(engagementId, signal));
    },
    [engagementId],
  );

  return useAsyncResource(Boolean(enabled && engagementId), load);
}
