import { getAppMode } from '../source';

/**
 * Preview scenarios let a reviewer see every state a screen can reach
 * without a backend and without fabricating a "sometimes it fails" random
 * behavior. The scenario is chosen at build time by `VITE_PREVIEW_SCENARIO`
 * and, like the mode itself, is never readable from the URL, storage, or
 * any other browser-controlled surface.
 *
 * Outside Preview mode the scenario is meaningless: Live never renders
 * fixtures at all, so this always reports the default there.
 */
export const PREVIEW_SCENARIOS = [
  'populated',
  'empty',
  'loading',
  'error',
  'forbidden',
  'partial',
] as const;

export type PreviewScenario = (typeof PREVIEW_SCENARIOS)[number];

export const DEFAULT_PREVIEW_SCENARIO: PreviewScenario = 'populated';

export interface PreviewScenarioEnv {
  readonly VITE_PREVIEW_SCENARIO?: unknown;
}

/** Unknown or malformed values fall back to `populated` rather than
 * failing the build — an unrecognized scenario must not be able to blank a
 * Preview deployment, and it can never affect Live. */
export function resolvePreviewScenario(env: PreviewScenarioEnv): PreviewScenario {
  const raw = env.VITE_PREVIEW_SCENARIO;
  if (typeof raw !== 'string') return DEFAULT_PREVIEW_SCENARIO;
  const match = PREVIEW_SCENARIOS.find((scenario) => scenario === raw);
  return match ?? DEFAULT_PREVIEW_SCENARIO;
}

export function getPreviewScenario(): PreviewScenario {
  if (getAppMode() !== 'preview') return DEFAULT_PREVIEW_SCENARIO;
  return resolvePreviewScenario({ VITE_PREVIEW_SCENARIO: import.meta.env.VITE_PREVIEW_SCENARIO });
}
