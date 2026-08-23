import {
  emptyState,
  errorState,
  forbiddenState,
  loadingState,
  type DataState,
} from '../../contracts/common';
import type { PreviewScenario } from '../../scenarios';

/**
 * The six reviewable states, resolved identically for every Preview source.
 *
 * Shared so a reviewer sees the same vocabulary on each page: "loading",
 * "empty", "error", and "forbidden" mean the same thing on Organizations as
 * on Engagements, and a source cannot quietly invent a seventh.
 *
 * Returns `null` for `populated` and `partial` — the two scenarios that
 * carry data — leaving the caller to build it.
 */
export function scenarioState(scenario: PreviewScenario): DataState<never> | null {
  switch (scenario) {
    case 'loading':
      return loadingState();
    case 'error':
      return errorState();
    case 'forbidden':
      return forbiddenState();
    case 'empty':
      return emptyState();
    default:
      return null;
  }
}
