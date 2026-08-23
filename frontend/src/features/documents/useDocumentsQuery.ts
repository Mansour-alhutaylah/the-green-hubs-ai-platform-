import { useCallback, useEffect, useState } from 'react';
import { listDocuments } from '@/lib/api/endpoints/documents';
import type { DocumentProcessingStatus, DocumentReadResponse, EvidenceStatus } from '@/lib/api/types';
import { ApiError, RequestAbortedError } from '@/lib/api/errors';

export interface DocumentsQueryParams {
  engagementId?: string;
  processingStatus?: DocumentProcessingStatus;
  /** Server-side evidence filter. The backend applies it inside the same
   * tenant-scoped query that produces `total`, so the returned `total` is a
   * real count of matching documents rather than the length of this page. */
  evidenceStatus?: EvidenceStatus;
  limit: number;
  offset: number;
}

export type DocumentsQueryStatus = 'loading' | 'ready' | 'error';

export interface DocumentsQueryState {
  status: DocumentsQueryStatus;
  items: DocumentReadResponse[];
  total: number;
  error: string | null;
  retry: () => void;
}

type InternalState = Omit<DocumentsQueryState, 'retry'>;

const IDLE_STATE: InternalState = { status: 'loading', items: [], total: 0, error: null };

/** Live-only server-side-paginated document listing —
 * `GET /api/v1/documents`. `enabled` gates the fetch so a demo/no-session
 * page never issues a request; every dependency that should trigger a
 * refetch (filters, page, an explicit retry) is a hook dependency, and the
 * in-flight request is aborted on unmount or whenever those change. */
export function useDocumentsQuery(enabled: boolean, params: DocumentsQueryParams): DocumentsQueryState {
  const [state, setState] = useState<InternalState>(IDLE_STATE);
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    if (!enabled) {
      setState(IDLE_STATE);
      return;
    }

    const controller = new AbortController();
    setState((prev) => ({ ...prev, status: 'loading', error: null }));

    listDocuments(
      {
        engagement_id: params.engagementId,
        processing_status: params.processingStatus,
        evidence_status: params.evidenceStatus,
        limit: params.limit,
        offset: params.offset,
      },
      controller.signal,
    )
      .then((response) => {
        setState({ status: 'ready', items: response.items, total: response.total, error: null });
      })
      .catch((error: unknown) => {
        if (error instanceof RequestAbortedError) return;
        setState({
          status: 'error',
          items: [],
          total: 0,
          error: error instanceof ApiError || error instanceof Error
            ? error.message
            : 'Unable to load documents.',
        });
      });

    return () => controller.abort();
  }, [
    enabled,
    params.engagementId,
    params.processingStatus,
    params.evidenceStatus,
    params.limit,
    params.offset,
    retryToken,
  ]);

  const retry = useCallback(() => setRetryToken((token) => token + 1), []);

  return { ...state, retry };
}
