import type { DataState } from './common';

/**
 * `DataState` plus the one state a *detail* route can reach that a
 * collection cannot: the requested id does not resolve.
 *
 * This is additive rather than a change to `DataState` on purpose. Every
 * F1 consumer of `DataState` (the dashboard) has no id to fail to resolve,
 * and widening the shared union would force each of them to handle a case
 * that cannot occur there. Detail hooks return `ResourceState`; collection
 * hooks keep returning `DataState`.
 *
 * `not-found` is deliberately distinct from `forbidden` and from `empty`:
 *
 * - The backend answers 404 for an id outside the caller's own
 *   organization *and* for an id that does not exist, precisely so the two
 *   are indistinguishable to a client. The UI must not guess which it was.
 * - `empty` means "this collection resolved and has no rows" — a different
 *   claim from "this thing does not exist".
 */
export type ResourceState<T> = DataState<T> | { readonly status: 'not-found' };

export const notFoundState = (): ResourceState<never> => ({ status: 'not-found' });

/**
 * A server-paginated collection.
 *
 * `total` is always the backend's own count for the whole filtered query,
 * never `items.length`. The two differ on every page but the last, and
 * conflating them is how a partial page becomes a fabricated global
 * figure. Hooks that build this read `total` from the response body and
 * have no code path that could substitute a length.
 */
export interface PaginatedCollection<T> {
  readonly items: readonly T[];
  readonly page: number;
  readonly pageSize: number;
  readonly total: number;
}
