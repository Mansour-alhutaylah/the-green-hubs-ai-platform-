import { useCallback, useEffect, useState } from 'react';
import { getAnalysisRun } from '@/lib/api/endpoints/analysis';
import type { AnalysisRunResponse } from '@/lib/api/types';
import { ApiError, NotFoundApiError, RequestAbortedError } from '@/lib/api/errors';

export type AnalysisRunQueryStatus = 'loading' | 'ready' | 'not-found' | 'error';

interface InternalState {
  status: AnalysisRunQueryStatus;
  run: AnalysisRunResponse | null;
  error: string | null;
}

export interface AnalysisRunQueryState extends InternalState {
  retry: () => void;
}

const IDLE_STATE: InternalState = { status: 'loading', run: null, error: null };

/** Live-only single-run lookup — `GET /api/v1/analysis/runs/{id}`. The run
 * id always comes from the route, so a browser refresh recovers the real
 * current run instead of assuming any in-memory workflow survived.
 * `enabled` gates the fetch so demo-mode renders (which read mock data)
 * never issue a request. Aborts the in-flight request when `runId`
 * changes or the page unmounts. */
export function useAnalysisRunQuery(enabled: boolean, runId: string | undefined): AnalysisRunQueryState {
  const [state, setState] = useState<InternalState>(IDLE_STATE);
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    if (!enabled || !runId) {
      setState(IDLE_STATE);
      return;
    }

    const controller = new AbortController();
    setState((prev) => ({ ...prev, status: 'loading', error: null }));

    getAnalysisRun(runId, controller.signal)
      .then((run) => {
        setState({ status: 'ready', run, error: null });
      })
      .catch((error: unknown) => {
        if (error instanceof RequestAbortedError) return;
        if (error instanceof NotFoundApiError) {
          setState({ status: 'not-found', run: null, error: null });
          return;
        }
        setState({
          status: 'error',
          run: null,
          error:
            error instanceof ApiError || error instanceof Error ? error.message : 'Unable to load this analysis run.',
        });
      });

    return () => controller.abort();
  }, [enabled, runId, retryToken]);

  const retry = useCallback(() => setRetryToken((token) => token + 1), []);

  return { ...state, retry };
}
