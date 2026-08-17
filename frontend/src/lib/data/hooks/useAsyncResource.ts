import { useCallback, useEffect, useState } from 'react';
import { ForbiddenError, NotFoundApiError, RequestAbortedError } from '@/lib/api/errors';
import {
  emptyState,
  errorState,
  forbiddenState,
  loadingState,
  readyState,
  type DataState,
} from '../contracts/common';
import { notFoundState, type ResourceState } from '../contracts/resource';

/**
 * The one asynchronous-resource primitive every Live source is built from.
 *
 * It exists so that the properties F2A has to guarantee are guaranteed
 * *once*, in a place a test can reach, rather than re-implemented per page:
 *
 * - **Every state is explicit.** The result is the shared `ResourceState`
 *   union, so a consumer cannot forget loading, empty, forbidden,
 *   not-found, or error — the type will not let it.
 * - **A failure never becomes an empty result.** The catch branch resolves
 *   to `error`/`forbidden`/`not-found`. There is no path from a rejected
 *   promise to `empty`, and none from a rejected promise to `ready` with a
 *   zero-length list. That distinction is the whole point: "nothing here"
 *   and "we could not find out" are different claims.
 * - **In-flight requests are aborted** on unmount and whenever the loader
 *   changes, so a slow response for filter A can never overwrite the state
 *   for filter B.
 * - **Preview costs nothing.** `enabled: false` short-circuits before any
 *   controller is created, so a Preview build's call to this hook (made to
 *   keep hook order stable) issues no request at all.
 *
 * No new state-management dependency is involved: this is `useState` +
 * `useEffect` + `AbortController`, the same primitives the F1 query hooks
 * already use, consolidated.
 *
 * **The loader is the dependency.** There is no `deps` array: `load` must
 * be a `useCallback` closing over whatever should trigger a refetch, and
 * its identity is what the effect watches. That keeps the dependency
 * statically checkable — an array spread into the effect's dependency list
 * cannot be verified by the lint rule, which is exactly the check worth
 * keeping on a hook whose whole job is to re-run correctly.
 *
 * For the same reason `isEmpty`/`isPartial` should be module-level
 * constants or memoized: a predicate re-created on every render would
 * re-run the request on every render.
 */

export interface AsyncResourceOptions<T> {
  /**
   * Decides whether a successfully loaded value should present as `empty`
   * rather than `ready`. Omitted means "any successful load is ready" —
   * correct for a single entity, where there is no such thing as an empty
   * one.
   */
  isEmpty?: (data: T) => boolean;
  /**
   * Marks a successful load as `coverage: 'partial'` — some of what the
   * screen asked for resolved and some did not. Only a source that fans
   * out across several requests can be partial; a single request is
   * complete or it is one of the failure states.
   */
  isPartial?: (data: T) => boolean;
}

export interface AsyncResource<T> {
  readonly state: ResourceState<T>;
  /** Re-runs the loader. Safe to call from an error/forbidden state. */
  readonly retry: () => void;
}

export function useAsyncResource<T>(
  enabled: boolean,
  load: (signal: AbortSignal) => Promise<T>,
  options: AsyncResourceOptions<T> = {},
): AsyncResource<T> {
  const [state, setState] = useState<ResourceState<T>>(loadingState);
  const [retryToken, setRetryToken] = useState(0);

  const { isEmpty, isPartial } = options;

  useEffect(() => {
    if (!enabled) {
      setState(loadingState());
      return;
    }

    const controller = new AbortController();
    setState(loadingState());

    load(controller.signal)
      .then((data) => {
        // A late resolution for a superseded dependency set must not land.
        // The cleanup below has already aborted the request, but a loader
        // that resolved from somewhere other than `fetch` would not see
        // that, so the signal is checked here too.
        if (controller.signal.aborted) return;
        if (isEmpty?.(data)) {
          setState(emptyState());
          return;
        }
        setState(readyState(data, isPartial?.(data) ? 'partial' : 'complete'));
      })
      .catch((error: unknown) => {
        // An abort is this component's own doing — never a user-facing
        // failure, and never an empty result.
        if (error instanceof RequestAbortedError || controller.signal.aborted) return;
        if (error instanceof ForbiddenError) {
          setState(forbiddenState());
          return;
        }
        if (error instanceof NotFoundApiError) {
          setState(notFoundState());
          return;
        }
        // Everything else — including a 401, which the API client has
        // already routed to the session-expired flow — is reported as a
        // failure rather than quietly rendered as "no data".
        setState(errorState());
      });

    return () => controller.abort();
  }, [enabled, retryToken, load, isEmpty, isPartial]);

  const retry = useCallback(() => setRetryToken((token) => token + 1), []);

  return { state, retry };
}

/**
 * Collapses a `ResourceState` down to `DataState` for a consumer that
 * genuinely has no id to resolve. `not-found` maps to `error` rather than
 * to `empty`, keeping the "a failure is never an empty result" rule intact
 * across the narrowing.
 */
export function toDataState<T>(state: ResourceState<T>): DataState<T> {
  return state.status === 'not-found' ? errorState() : state;
}
