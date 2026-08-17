/**
 * The typed Live/Preview data foundation.
 *
 * Layout (F2A: the Dashboard, Organizations, Engagements, Users & Roles,
 * and Settings all read through it):
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

export type { AsyncResource, AsyncResourceOptions } from './hooks/useAsyncResource';
export { useAsyncResource, toDataState } from './hooks/useAsyncResource';

export type { AsyncAction, AsyncActionStatus } from './hooks/useAsyncAction';
export { useAsyncAction } from './hooks/useAsyncAction';

export type { WorkspaceResource } from './hooks/sourceSelector';

/**
 * Selectors are exported per domain, and pages import them from their own
 * module rather than through this barrel. A page that needs engagements
 * should not pull the organization, team, and dashboard endpoint clients,
 * adapters, and fixtures into its bundle on the way — this barrel exists
 * for discovery and for tests, not as the page-level import path.
 */
export type { UpdateOrganizationInput } from './hooks/useOrganizationData';
export {
  useOrganizationDetail,
  useOrganizationsList,
  useUpdateOrganization,
} from './hooks/useOrganizationData';

export type { CreateEngagementInput, UpdateEngagementInput } from './hooks/useEngagementData';
export {
  useCreateEngagement,
  useEngagementDetail,
  useEngagementsList,
  useUpdateEngagement,
} from './hooks/useEngagementData';

export { useTeamDirectory } from './hooks/useTeamData';

export { useDashboardLiveSummary, useDashboardPreviewSupplement } from './hooks/useDashboardData';

export { useApplicationInfo, useIntegrationCapabilities } from './hooks/useApplicationInfo';
