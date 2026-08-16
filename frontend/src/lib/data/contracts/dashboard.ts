import type { IsoTimestamp } from './common';
import type {
  ActivityId,
  AnalysisRunId,
  DocumentId,
  FrameworkId,
  MetricId,
  QueueItemId,
} from './ids';
import type { DocumentState } from './documents';

/**
 * The dashboard's normalized domain model.
 *
 * The Backend has no dashboard-summary endpoint today, so nothing produces
 * this in Live mode yet — `useDashboardSnapshot` returns `unavailable`
 * there, and only the Preview source builds one (from fixtures, through
 * `adapters/dashboardAdapter.ts`). The contract is written against what a
 * real endpoint would have to supply, so the F2 adapter has a target that
 * does not require reshaping the UI.
 *
 * Every value is data, never presentation: counts are numbers (`86`, not
 * `"86%"`), states are closed unions (not translated badge text), and
 * instants are ISO strings (not "2 days ago").
 */

export type MetricKey =
  | 'documentsAnalyzed'
  | 'activeReports'
  | 'complianceScore'
  | 'pendingApprovals';

export type MetricTone = 'positive' | 'neutral' | 'attention';

export interface DashboardMetric {
  readonly id: MetricId;
  readonly key: MetricKey;
  /** `percentage` values are 0–100; `count` values are absolute. */
  readonly unit: 'count' | 'percentage';
  readonly value: number;
  readonly tone: MetricTone;
}

export interface DashboardRecentDocument {
  readonly id: DocumentId;
  readonly filename: string;
  readonly organizationName: string;
  readonly state: DocumentState;
  readonly updatedAt: IsoTimestamp;
}

export interface DashboardAnalysisInsight {
  readonly id: AnalysisRunId;
  readonly documentFilename: string;
  readonly state: DocumentState;
  /** 0–100 while processing, `null` once the run is not in progress. */
  readonly progressPercent: number | null;
  readonly extractedFigureCount: number | null;
  readonly flaggedForReviewCount: number | null;
}

export type ActivityAction = 'uploaded' | 'approved' | 'viewed' | 'published';

export interface DashboardActivityEntry {
  readonly id: ActivityId;
  readonly actorName: string;
  readonly action: ActivityAction;
  readonly documentFilename: string;
  readonly occurredAt: IsoTimestamp;
}

export type ComplianceState = 'onTrack' | 'needsReview';

export interface DashboardFramework {
  readonly id: FrameworkId;
  readonly name: string;
  readonly state: ComplianceState;
}

export interface DashboardQueueItem {
  readonly id: QueueItemId;
  readonly filename: string;
  readonly etaMinutes: number;
}

/** One point per calendar month; `month` is 1–12 so the label is chosen by
 * the renderer's dictionary rather than stored as text. */
export interface DashboardActivityPoint {
  readonly month: number;
  readonly completedRuns: number;
}

export type AnalysisOutcome = 'complete' | 'processing' | 'failed' | 'insufficientEvidence';

export interface DashboardAnalysisOutcome {
  readonly outcome: AnalysisOutcome;
  readonly count: number;
}

export interface DashboardTotals {
  readonly documentsTracked: number;
  readonly analysisRuns: number;
}

export interface DashboardSnapshot {
  readonly generatedAt: IsoTimestamp;
  readonly totals: DashboardTotals;
  readonly metrics: readonly DashboardMetric[];
  readonly recentDocuments: readonly DashboardRecentDocument[];
  readonly recentAnalysis: readonly DashboardAnalysisInsight[];
  readonly activity: readonly DashboardActivityEntry[];
  readonly frameworks: readonly DashboardFramework[];
  readonly processingQueue: readonly DashboardQueueItem[];
  readonly monthlyAnalysisActivity: readonly DashboardActivityPoint[];
  readonly analysisOutcomes: readonly DashboardAnalysisOutcome[];
}
