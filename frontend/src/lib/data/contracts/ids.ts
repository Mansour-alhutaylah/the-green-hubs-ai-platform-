/**
 * Branded identifier types for the Frontend domain model.
 *
 * A bare `string` id is trivially mixed up with a filename, a label, or an
 * id of a different entity. Branding costs nothing at runtime (the
 * constructors are identity functions) but makes those mistakes compile
 * errors, which is the point: fixtures and adapter output are checked
 * against the same contract, so a fixture that drifts from its contract
 * shape fails the build rather than silently rendering.
 */

declare const idBrand: unique symbol;

type Branded<Name extends string> = string & { readonly [idBrand]: Name };

export type OrganizationId = Branded<'OrganizationId'>;
export type EngagementId = Branded<'EngagementId'>;
export type DocumentId = Branded<'DocumentId'>;
export type AnalysisRunId = Branded<'AnalysisRunId'>;
export type ActivityId = Branded<'ActivityId'>;
export type MetricId = Branded<'MetricId'>;
export type FrameworkId = Branded<'FrameworkId'>;
export type QueueItemId = Branded<'QueueItemId'>;

/** The one place a raw wire/fixture string becomes a typed id. Rejects the
 * empty string so a missing field can never silently become a valid id. */
function brand<T extends string>(value: string, kind: string): T {
  if (value.length === 0) {
    throw new Error(`${kind} cannot be empty.`);
  }
  return value as T;
}

export const organizationId = (value: string): OrganizationId =>
  brand<OrganizationId>(value, 'OrganizationId');
export const engagementId = (value: string): EngagementId =>
  brand<EngagementId>(value, 'EngagementId');
export const documentId = (value: string): DocumentId => brand<DocumentId>(value, 'DocumentId');
export const analysisRunId = (value: string): AnalysisRunId =>
  brand<AnalysisRunId>(value, 'AnalysisRunId');
export const activityId = (value: string): ActivityId => brand<ActivityId>(value, 'ActivityId');
export const metricId = (value: string): MetricId => brand<MetricId>(value, 'MetricId');
export const frameworkId = (value: string): FrameworkId => brand<FrameworkId>(value, 'FrameworkId');
export const queueItemId = (value: string): QueueItemId => brand<QueueItemId>(value, 'QueueItemId');
