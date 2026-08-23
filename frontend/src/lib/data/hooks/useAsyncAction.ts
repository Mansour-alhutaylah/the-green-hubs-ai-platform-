import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, RequestAbortedError } from '@/lib/api/errors';

/**
 * The write counterpart to `useAsyncResource`: one submission, four
 * observable outcomes, and an abort on unmount.
 *
 * Kept separate from the read primitive because a write is not a
 * declarative subscription to a dependency set — it happens because a
 * person pressed a button, exactly as many times as they pressed it. A
 * `useEffect` would re-run it on a re-render, which for a POST is a
 * duplicate record.
 *
 * The failure message is the backend's own `detail` string (already
 * normalized and stripped of internals by `buildApiErrorFromResponse`), or
 * a caller-supplied fallback. Nothing here logs, stores, or re-throws a
 * raw response.
 */

export type AsyncActionStatus = 'idle' | 'submitting' | 'succeeded' | 'failed';

export interface AsyncAction<TInput, TResult> {
  readonly status: AsyncActionStatus;
  /** Safe, human-readable failure text. `null` unless `status` is `failed`. */
  readonly error: string | null;
  /** Resolves to the result on success, or `null` on failure — so a caller
   * can branch without a try/catch and without the action throwing into a
   * render path. */
  readonly run: (input: TInput) => Promise<TResult | null>;
  readonly reset: () => void;
}

export function useAsyncAction<TInput, TResult>(
  perform: (input: TInput, signal: AbortSignal) => Promise<TResult>,
  fallbackMessage: string,
): AsyncAction<TInput, TResult> {
  const [status, setStatus] = useState<AsyncActionStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  const controllerRef = useRef<AbortController | null>(null);

  // The one effect this hook owns: on unmount, abort whatever is in flight
  // and stop a late resolution from setting state on a dead component.
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      controllerRef.current?.abort();
    };
  }, []);

  const run = useCallback(
    async (input: TInput): Promise<TResult | null> => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;

      setStatus('submitting');
      setError(null);

      try {
        const result = await perform(input, controller.signal);
        if (!mounted.current || controller.signal.aborted) return null;
        setStatus('succeeded');
        return result;
      } catch (cause: unknown) {
        if (!mounted.current || cause instanceof RequestAbortedError) return null;
        setStatus('failed');
        setError(
          cause instanceof ApiError || cause instanceof Error ? cause.message : fallbackMessage,
        );
        return null;
      }
    },
    [perform, fallbackMessage],
  );

  const reset = useCallback(() => {
    setStatus('idle');
    setError(null);
  }, []);

  return { status, error, run, reset };
}
