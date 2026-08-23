import { useEffect, useState } from 'react';
import { listDocuments } from '@/lib/api/endpoints/documents';
import { RequestAbortedError } from '@/lib/api/errors';
import type { DocumentReadResponse } from '@/lib/api/types';

/** Enough of a page to choose from without turning the dialog into a
 * second document browser. The backend caps `limit` at 100. */
const CANDIDATE_LIMIT = 50;

export interface SuccessorCandidatesState {
  status: 'idle' | 'loading' | 'ready' | 'error';
  candidates: DocumentReadResponse[];
}

/**
 * The documents a reviewer may name as this document's replacement.
 *
 * Scoped to the same engagement, which is also the narrowest scope the
 * list endpoint offers — and, more importantly, the request carries no
 * organization identifier at all: the backend resolves the caller's
 * organization from the bearer token and will not return another tenant's
 * documents whatever this asks for. A cross-tenant successor is refused
 * server-side with the same 404 as an unknown one.
 *
 * The document itself is filtered out because a document may not supersede
 * itself. That rule is enforced in three independent places — this list,
 * the dialog's own guard, and the database CHECK constraint the transition
 * runs against — because it is the one supersede input a reviewer could
 * plausibly pick by accident.
 *
 * `enabled` gates the fetch so no request is issued until a reviewer
 * actually opens the supersede dialog: a panel that pre-loaded candidates
 * would be issuing a request on behalf of an action nobody has taken, and
 * a *denied* reviewer would be issuing it having no way to use the result.
 */
export function useSuccessorCandidates(
  enabled: boolean,
  document: Pick<DocumentReadResponse, 'id' | 'engagement_id'>,
): SuccessorCandidatesState {
  const [state, setState] = useState<SuccessorCandidatesState>({
    status: 'idle',
    candidates: [],
  });

  const { id, engagement_id: engagementId } = document;

  useEffect(() => {
    if (!enabled) {
      setState({ status: 'idle', candidates: [] });
      return;
    }

    const controller = new AbortController();
    setState({ status: 'loading', candidates: [] });

    listDocuments({ engagement_id: engagementId, limit: CANDIDATE_LIMIT, offset: 0 }, controller.signal)
      .then((response) => {
        setState({
          status: 'ready',
          candidates: response.items.filter((candidate) => candidate.id !== id),
        });
      })
      .catch((error: unknown) => {
        if (error instanceof RequestAbortedError) return;
        // A failed candidate list is not a failed review: supersede
        // accepts no successor at all, so the dialog stays usable and
        // simply offers nothing to name.
        setState({ status: 'error', candidates: [] });
      });

    return () => controller.abort();
  }, [enabled, id, engagementId]);

  return state;
}
