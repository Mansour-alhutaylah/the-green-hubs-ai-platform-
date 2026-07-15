import { useCallback, useEffect, useState } from 'react';
import { getDocument } from '@/lib/api/endpoints/documents';
import type { DocumentReadResponse } from '@/lib/api/types';
import { ApiError, NotFoundApiError, RequestAbortedError } from '@/lib/api/errors';

export type DocumentQueryStatus = 'loading' | 'ready' | 'not-found' | 'error';

interface InternalState {
  status: DocumentQueryStatus;
  document: DocumentReadResponse | null;
  error: string | null;
}

export interface DocumentQueryState extends InternalState {
  retry: () => void;
}

const IDLE_STATE: InternalState = { status: 'loading', document: null, error: null };

/** Live-only single-document lookup — `GET /api/v1/documents/{id}`.
 * `enabled` gates the fetch so a demo-mode render of this page (which
 * reads `MOCK_DOCUMENTS` instead) never issues a request. Re-fetches
 * whenever `documentId` changes (aborting any in-flight request for the
 * previous id first) or `retry()` is called — this is also the mechanism
 * a caller uses to recover the real state after a browser refresh, since
 * it never assumes an in-memory workflow is still running. */
export function useDocumentQuery(enabled: boolean, documentId: string | undefined): DocumentQueryState {
  const [state, setState] = useState<InternalState>(IDLE_STATE);
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    if (!enabled || !documentId) {
      setState(IDLE_STATE);
      return;
    }

    const controller = new AbortController();
    setState((prev) => ({ ...prev, status: 'loading', error: null }));

    getDocument(documentId, controller.signal)
      .then((document) => {
        setState({ status: 'ready', document, error: null });
      })
      .catch((error: unknown) => {
        if (error instanceof RequestAbortedError) return;
        if (error instanceof NotFoundApiError) {
          setState({ status: 'not-found', document: null, error: null });
          return;
        }
        setState({
          status: 'error',
          document: null,
          error: error instanceof ApiError || error instanceof Error ? error.message : 'Unable to load this document.',
        });
      });

    return () => controller.abort();
  }, [enabled, documentId, retryToken]);

  const retry = useCallback(() => setRetryToken((token) => token + 1), []);

  return { ...state, retry };
}
