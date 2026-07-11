import type { ReactNode } from 'react';
import { useHasMinTier } from './useHasMinTier';
import type { Role } from './roles';

/** Declarative in-page hide for a fragment of UI that only some tiers
 * should see (e.g. a future Owner-only Settings section) — renders nothing
 * rather than a disabled state, per §19's "hidden, not disabled" rule. */
export function RequireTier({ minTier, children }: { minTier: Role; children: ReactNode }) {
  const allowed = useHasMinTier(minTier);
  return allowed ? <>{children}</> : null;
}
