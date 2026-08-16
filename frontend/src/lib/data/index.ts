/**
 * The typed Live/Preview data foundation.
 *
 * Layout (F1 scope — the Dashboard is the first and only migrated consumer):
 *
 * ```
 * contracts/  one normalized Frontend domain model (branded ids, ISO instants,
 *             closed state unions — never display strings)
 * adapters/   the explicit mapping boundary between backend wire schemas and
 *             the domain model; Live responses and Preview fixtures converge here
 * fixtures/   deterministic, obviously synthetic Preview data
 * scenarios/  populated | empty | loading | error | forbidden | partial
 * source.ts   fail-closed build-time Live/Preview selection
 * hooks/      the only thing pages consume; live/ and preview/ never mix
 * ```
 */
export type { AppMode, AppEnvironment, AppModeEnv } from './source';
export {
  resolveAppMode,
  getAppMode,
  isPreviewMode,
  isLiveMode,
  assertPreviewMode,
} from './source';

export type { PreviewScenario, PreviewScenarioEnv } from './scenarios';
export {
  PREVIEW_SCENARIOS,
  DEFAULT_PREVIEW_SCENARIO,
  resolvePreviewScenario,
  getPreviewScenario,
} from './scenarios';

export * from './contracts';

export { useDashboardSnapshot } from './hooks/useDashboardSnapshot';
