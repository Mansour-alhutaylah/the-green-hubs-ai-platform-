import { useCallback } from 'react';
import { updateOrganization } from '@/lib/api/endpoints/organizations';
import type { OrganizationResponse } from '@/lib/api/types';
import type { DataState } from '../contracts/common';
import type { OrganizationSummary } from '../contracts/organization';
import type { PaginatedCollection, ResourceState } from '../contracts/resource';
import { getPreviewScenario } from '../scenarios';
import { isPreviewMode } from '../source';
import {
  useLiveOrganizationDetail,
  useLiveOrganizations,
} from './live/liveOrganizationSource';
import {
  readPreviewOrganizationDetail,
  readPreviewOrganizations,
} from './preview/previewOrganizationSource';
import { NO_RETRY, type WorkspaceResource } from './sourceSelector';
import { useAsyncAction, type AsyncAction } from './useAsyncAction';
import { toDataState } from './useAsyncResource';

/** The organization sources every Organizations page reads. See
 * `sourceSelector.ts` for why each one gates rather than branches. */
export function useOrganizationsList(): WorkspaceResource<
  DataState<PaginatedCollection<OrganizationSummary>>
> {
  const preview = isPreviewMode();
  const live = useLiveOrganizations(!preview);

  if (preview) {
    return { state: readPreviewOrganizations(getPreviewScenario()), retry: NO_RETRY };
  }
  // A collection has no id to fail to resolve, so `not-found` cannot occur
  // here; the narrowing keeps that impossibility in the type rather than
  // leaving every consumer to handle a case that never arrives.
  return { state: toDataState(live.state), retry: live.retry };
}

export function useOrganizationDetail(
  organizationId: string | undefined,
): WorkspaceResource<ResourceState<OrganizationSummary>> {
  const preview = isPreviewMode();
  const live = useLiveOrganizationDetail(!preview, organizationId);

  if (preview) {
    return {
      state: readPreviewOrganizationDetail(getPreviewScenario(), organizationId),
      retry: NO_RETRY,
    };
  }
  return live;
}

export interface UpdateOrganizationInput {
  organizationId: string;
  name: string;
}

/**
 * `PATCH /api/v1/organizations/{id}` — requires `organization.manage`
 * (admin/owner on this backend). `name` is the only mutable field the
 * contract exposes, and the service refuses any id but the caller's own
 * with a 404.
 *
 * There is deliberately no create counterpart. `OrganizationService.create`
 * raises `AuthorizationError("Organization creation is not available in
 * this phase.")` unconditionally, so a create client could only ever
 * produce a guaranteed 403 — see `endpoints/organizations.ts`.
 */
export function useUpdateOrganization(
  fallbackMessage: string,
): AsyncAction<UpdateOrganizationInput, OrganizationResponse> {
  const perform = useCallback(
    (input: UpdateOrganizationInput, signal: AbortSignal) =>
      updateOrganization(input.organizationId, { name: input.name }, signal),
    [],
  );
  return useAsyncAction(perform, fallbackMessage);
}
