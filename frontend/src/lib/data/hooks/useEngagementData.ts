import { useCallback } from 'react';
import { createEngagement, updateEngagement } from '@/lib/api/endpoints/engagements';
import type { EngagementResponse } from '@/lib/api/types';
import type { DataState } from '../contracts/common';
import type { EngagementSummary } from '../contracts/engagement';
import type { PaginatedCollection, ResourceState } from '../contracts/resource';
import { getPreviewScenario } from '../scenarios';
import { isPreviewMode } from '../source';
import { useLiveEngagementDetail, useLiveEngagements } from './live/liveEngagementSource';
import {
  readPreviewEngagementDetail,
  readPreviewEngagements,
} from './preview/previewEngagementSource';
import { NO_RETRY, type WorkspaceResource } from './sourceSelector';
import { useAsyncAction, type AsyncAction } from './useAsyncAction';
import { toDataState } from './useAsyncResource';

/** The engagement sources every Engagements page reads. See
 * `sourceSelector.ts` for why each one gates rather than branches. */
export function useEngagementsList(params: {
  page: number;
  pageSize: number;
}): WorkspaceResource<DataState<PaginatedCollection<EngagementSummary>>> {
  const preview = isPreviewMode();
  const live = useLiveEngagements(!preview, params);

  if (preview) {
    return { state: readPreviewEngagements(getPreviewScenario(), params), retry: NO_RETRY };
  }
  return { state: toDataState(live.state), retry: live.retry };
}

export function useEngagementDetail(
  engagementId: string | undefined,
): WorkspaceResource<ResourceState<EngagementSummary>> {
  const preview = isPreviewMode();
  const live = useLiveEngagementDetail(!preview, engagementId);

  if (preview) {
    return {
      state: readPreviewEngagementDetail(getPreviewScenario(), engagementId),
      retry: NO_RETRY,
    };
  }
  return live;
}

export interface CreateEngagementInput {
  /**
   * The caller's own organization, as returned by the server in
   * `GET /auth/me` and carried through the authenticated session.
   *
   * The contract requires this field, and the service compares it against
   * the caller's trusted organization, answering 403 on a mismatch. The
   * only safe way to populate it is therefore from the server's own answer
   * about who the caller is — never a query parameter, a route parameter,
   * `localStorage`, or a field a person can edit. The Engagements page
   * reads it from the authenticated session and renders it as read-only
   * context.
   */
  organizationId: string;
  title: string;
  /** Omitted entirely when the creator did not choose one, so the backend
   * applies its own default. Never sent as `null`: the schema types
   * `status` as a plain `str`, so an explicit null is a 422. */
  status?: string;
}

export function useCreateEngagement(
  fallbackMessage: string,
): AsyncAction<CreateEngagementInput, EngagementResponse> {
  const perform = useCallback(
    (input: CreateEngagementInput, signal: AbortSignal) =>
      createEngagement(
        {
          organization_id: input.organizationId,
          title: input.title,
          ...(input.status ? { status: input.status } : {}),
        },
        signal,
      ),
    [],
  );
  return useAsyncAction(perform, fallbackMessage);
}

export interface UpdateEngagementInput {
  engagementId: string;
  title?: string;
  status?: string;
}

/**
 * `PATCH /api/v1/engagements/{id}` — requires `engagement.manage`.
 *
 * Sends only the fields actually edited, and never `organization_id`:
 * reassigning an engagement to another tenant is refused server-side, and
 * the UI offers no control for it. An explicitly-null field is a 422 on
 * this contract, so omitted-means-unchanged is the only shape used.
 */
export function useUpdateEngagement(
  fallbackMessage: string,
): AsyncAction<UpdateEngagementInput, EngagementResponse> {
  const perform = useCallback(
    (input: UpdateEngagementInput, signal: AbortSignal) =>
      updateEngagement(
        input.engagementId,
        {
          ...(input.title === undefined ? {} : { title: input.title }),
          ...(input.status === undefined ? {} : { status: input.status }),
        },
        signal,
      ),
    [],
  );
  return useAsyncAction(perform, fallbackMessage);
}
