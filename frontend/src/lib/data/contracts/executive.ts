/**
 * The Preview-only executive command-centre contract.
 *
 * Separate from `DashboardLiveSummary` for the same reason every other
 * Preview contract is: the Live dashboard's shape is "whatever existing
 * FastAPI responses can prove", and this one's is "what a finished
 * evidence workspace looks like". Merging them is how a synthetic figure
 * acquires a slot on a real screen. No Live source has a field for any of
 * this, so there is nothing here for Live to fill in.
 *
 * Naming discipline: nothing here is called a compliance score. No backend
 * computes a regulatory judgement, so the product does not claim one.
 * `evidenceReadinessPercent` describes how much of the workspace's own
 * evidence has reached a report-ready state, which is a statement about
 * documents rather than about law.
 *
 * Counts are authored literals, never derived from the fixture arrays. A
 * count derived from a list is only correct while that list is the
 * complete set, and deriving totals from whatever rows are in hand is
 * exactly what the Live dashboard must never do. Preview keeps the same
 * discipline so the two read alike.
 */

/** The four lifecycle stages evidence moves through, in order. */
export type EvidenceStage = 'uploaded' | 'extracted' | 'analyzed' | 'verified' | 'reportReady';

export const EVIDENCE_STAGES: readonly EvidenceStage[] = [
  'uploaded',
  'extracted',
  'analyzed',
  'verified',
  'reportReady',
];

export interface EvidencePipelineStage {
  readonly stage: EvidenceStage;
  /** Documents that have reached this stage. Monotonically non-increasing
   * across the ordered stages, because a document cannot be verified
   * without having been analyzed first. */
  readonly count: number;
}

/** One month of the throughput series. `month` is a short English label;
 * Preview fixtures are authored, so no date arithmetic runs at render. */
export interface EvidenceThroughputPoint {
  readonly month: string;
  readonly verified: number;
  readonly reportReady: number;
}

/** How urgently an action wants attention. Drives ordering and the badge,
 * never colour alone. */
export type ActionSeverity = 'critical' | 'attention' | 'scheduled';

export const ACTION_SEVERITIES: readonly ActionSeverity[] = [
  'critical',
  'attention',
  'scheduled',
];

/**
 * One row in the Action Centre.
 *
 * `route` is a path from `ROUTES` and nothing else. Every action either
 * navigates somewhere registered or is not offered, so the panel cannot
 * contain a dead button. `explanationKey` carries the Preview-only note
 * shown when the action is a demonstration rather than a destination.
 */
export interface EvidenceAction {
  readonly id: string;
  readonly severity: ActionSeverity;
  /** i18n key for the action's title. */
  readonly titleKey: string;
  /** i18n key for the one-line context under the title. */
  readonly detailKey: string;
  /** A registered route path. */
  readonly route: string;
  /** Count of affected records, or `null` when the action is not a count. */
  readonly count: number | null;
}

/** A reporting framework's evidence coverage. Explicitly coverage of the
 * workspace's own evidence, never a certification or an audit outcome. */
export interface FrameworkCoverage {
  readonly id: 'gri' | 'csrd' | 'issb';
  readonly label: string;
  /** 0-100. Share of the framework's requested disclosures that have at
   * least one verified evidence document attached, in this synthetic
   * workspace. */
  readonly coveragePercent: number;
  readonly disclosuresCovered: number;
  readonly disclosuresTotal: number;
}

export interface ExecutiveSummary {
  /** 0-100. Share of source documents that have reached report-ready. */
  readonly evidenceReadinessPercent: number;
  readonly sourceDocuments: number;
  readonly awaitingReview: number;
  /** 0-100. Share of processing attempts that completed without failure. */
  readonly processingHealthPercent: number;
  /** Failed extractions behind `processingHealthPercent`. */
  readonly processingFailures: number;
  readonly reportingPeriod: string;
  /** Authored ISO timestamp. Preview never reads the clock, so the value a
   * reviewer sees is the same on every machine and in every screenshot. */
  readonly generatedAt: string;
  readonly pipeline: readonly EvidencePipelineStage[];
  readonly throughput: readonly EvidenceThroughputPoint[];
  readonly actions: readonly EvidenceAction[];
  readonly frameworks: readonly FrameworkCoverage[];
}
