/**
 * Cross-domain contract primitives.
 *
 * Two rules are enforced here rather than by convention:
 *
 * 1. A timestamp in the domain model is always a validated ISO 8601 string,
 *    never a pre-rendered label ("2 days ago"). Formatting is a rendering
 *    concern and belongs to the component that knows the locale/direction.
 * 2. Every data-producing hook returns the same `DataState` union, so a
 *    Live consumer and a Preview consumer are interchangeable and neither
 *    can quietly forget a state (loading/empty/error/forbidden/unavailable).
 */

declare const isoBrand: unique symbol;

export type IsoTimestamp = string & { readonly [isoBrand]: 'IsoTimestamp' };

/** Validates and brands an ISO 8601 instant. Deliberately strict: fixtures
 * are authored by hand, and a typo that produces `Invalid Date` should fail
 * at module load in a test run rather than render as garbage. */
export function isoTimestamp(value: string): IsoTimestamp {
  if (Number.isNaN(Date.parse(value))) {
    throw new Error(`Not a valid ISO 8601 timestamp: ${value}`);
  }
  return value as IsoTimestamp;
}

/**
 * The single state union every `src/lib/data/hooks/*` hook resolves to.
 *
 * `unavailable` is the truthful Live state for a capability the Backend
 * does not implement yet — it is never used to hide an error, and it is
 * never satisfied by rendering Preview fixtures.
 */
export type DataState<T> =
  | { readonly status: 'loading' }
  | { readonly status: 'ready'; readonly data: T; readonly coverage: 'complete' | 'partial' }
  | { readonly status: 'empty' }
  | { readonly status: 'error'; readonly reason: 'request-failed' }
  | { readonly status: 'forbidden' }
  | { readonly status: 'unavailable' };

export const loadingState = (): DataState<never> => ({ status: 'loading' });
export const emptyState = (): DataState<never> => ({ status: 'empty' });
export const errorState = (): DataState<never> => ({ status: 'error', reason: 'request-failed' });
export const forbiddenState = (): DataState<never> => ({ status: 'forbidden' });
export const unavailableState = (): DataState<never> => ({ status: 'unavailable' });

export const readyState = <T>(data: T, coverage: 'complete' | 'partial' = 'complete'): DataState<T> => ({
  status: 'ready',
  data,
  coverage,
});
