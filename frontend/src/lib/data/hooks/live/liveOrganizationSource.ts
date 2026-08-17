import { useCallback } from 'react';
import { getOrganization, listOrganizations } from '@/lib/api/endpoints/organizations';
import { toOrganizationSummaries, toOrganizationSummary } from '../../adapters/organizationAdapter';
import type { OrganizationSummary } from '../../contracts/organization';
import type { PaginatedCollection } from '../../contracts/resource';
import { useAsyncResource, type AsyncResource } from '../useAsyncResource';

/**
 * The Live organization sources.
 *
 * This module imports the organizations endpoint client and the wire→domain
 * adapter, and **nothing from `../../fixtures/`**. That is the isolation
 * boundary stated as an import rule: there is no symbol in scope here that
 * could put synthetic data on a real user's screen, so a Live failure
 * cannot fall back to Preview content — it resolves to `error`, and the
 * page says so.
 *
 * Each hook takes `enabled` and does nothing when it is false, which is how
 * a Preview build calls these (to keep hook order stable) without issuing a
 * request.
 *
 * Kept in its own module, one per domain, rather than in a single
 * workspace-sources file: a page that only needs organizations should not
 * pull the engagement, team, and document endpoint clients into its bundle
 * along the way.
 */

/** Module-level so its identity is stable: a predicate re-created per
 * render would make the resource hook re-request on every render. */
const isEmptyCollection = (collection: PaginatedCollection<unknown>): boolean =>
  collection.items.length === 0;

/**
 * `GET /api/v1/organizations`.
 *
 * The backend answers with the caller's own single organization —
 * `OrganizationService.list` reads the caller's trusted `organization_id`
 * and returns exactly that row, with `total` fixed at 1. No client-supplied
 * scope is sent or accepted; `listOrganizations()` takes no parameters at
 * all.
 */
export function useLiveOrganizations(
  enabled: boolean,
): AsyncResource<PaginatedCollection<OrganizationSummary>> {
  const load = useCallback(
    async (signal: AbortSignal): Promise<PaginatedCollection<OrganizationSummary>> => {
      const response = await listOrganizations(signal);
      return {
        items: toOrganizationSummaries(response.items),
        page: response.page,
        pageSize: response.page_size,
        // The backend's own count. Not `items.length`.
        total: response.total,
      };
    },
    [],
  );

  return useAsyncResource(enabled, load, { isEmpty: isEmptyCollection });
}

/**
 * `GET /api/v1/organizations/{id}`.
 *
 * Passing an id here asserts nothing: the service compares it against the
 * caller's trusted organization and raises `NotFoundError` for anything
 * else — deliberately the same answer as a genuinely nonexistent id, so a
 * cross-tenant probe and a typo are indistinguishable. A 404 surfaces as
 * `not-found`, never as an empty organization.
 */
export function useLiveOrganizationDetail(
  enabled: boolean,
  organizationId: string | undefined,
): AsyncResource<OrganizationSummary> {
  const load = useCallback(
    async (signal: AbortSignal): Promise<OrganizationSummary> => {
      if (!organizationId) throw new Error('An organization id is required.');
      return toOrganizationSummary(await getOrganization(organizationId, signal));
    },
    [organizationId],
  );

  return useAsyncResource(Boolean(enabled && organizationId), load);
}
