import type { DocumentState } from './documents';

/**
 * The Preview-only part of the dashboard.
 *
 * `DashboardSnapshot` (F1) already carries totals, recent documents,
 * activity, framework readiness, and the processing queue. This supplement
 * adds the three breakdowns a *complete* demonstration workspace shows and
 * that contract does not model: documents by processing state, the
 * evidence-review lifecycle, and an engagement roll-up.
 *
 * Two rules keep this from leaking into Live:
 *
 * 1. It is a **separate contract from `DashboardLiveSummary`**, for the
 *    same reason `DashboardSnapshot` is: the Live dashboard's shape is
 *    "whatever existing FastAPI responses can prove", and this one's is
 *    "what a finished product looks like". Merging them is how a synthetic
 *    figure acquires a slot on a real screen.
 * 2. Only the Preview source constructs one. The Live dashboard has no
 *    field for any of these, so there is nothing to fill in.
 *
 * The evidence-review counts are presentation only — F2A ships no review
 * action, and the approval-authority policy is management decision M-4,
 * still open. Showing a demonstration of the lifecycle's *states* asserts
 * nothing about who may move a document between them.
 *
 * Counts are authored literals rather than derived from the fixture
 * arrays. A count derived from a list is only correct while that list is
 * the complete set, and the habit of computing totals from whatever rows
 * happen to be in hand is exactly what the Live dashboard must never do.
 * Preview keeps the same discipline so the two read alike.
 */

export type EvidenceReviewState = 'pendingReview' | 'approved' | 'rejected' | 'withdrawn';

export const EVIDENCE_REVIEW_STATES: readonly EvidenceReviewState[] = [
  'pendingReview',
  'approved',
  'rejected',
  'withdrawn',
];

export interface PreviewEngagementRollup {
  readonly total: number;
  readonly byStatus: readonly { readonly status: string; readonly count: number }[];
}

export interface DashboardPreviewSupplement {
  readonly documentsByState: Readonly<Record<DocumentState, number>>;
  readonly evidenceReview: Readonly<Record<EvidenceReviewState, number>>;
  readonly engagements: PreviewEngagementRollup;
  /** 0–100. A demonstration readiness figure, never shown in Live. */
  readonly readinessPercent: number;
}
