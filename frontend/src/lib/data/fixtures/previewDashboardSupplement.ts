import type { DashboardPreviewSupplement } from '../contracts/dashboardPreview';

/**
 * Deterministic Preview fixtures for the dashboard breakdowns that
 * `DashboardSnapshot` does not model.
 *
 * Same rules as every other fixture module here: literal values only, no
 * `Math.random()`, no `Date.now()`, and nothing that could be mistaken for
 * a real organization's figures. Never imported by a Live source — see
 * `hooks/live/`, which imports no fixture module at all.
 *
 * The engagement roll-up mirrors `previewWorkspace.ts`'s four engagements
 * (two active, one draft, one closed) so the dashboard and the Engagements
 * page tell a reviewer the same story rather than two contradicting ones.
 */
export const PREVIEW_DASHBOARD_SUPPLEMENT: DashboardPreviewSupplement = {
  documentsByState: {
    processed: 84,
    processing: 6,
    pending: 11,
    failed: 3,
  },
  evidenceReview: {
    pendingReview: 12,
    approved: 47,
    rejected: 4,
    withdrawn: 2,
  },
  engagements: {
    total: 4,
    byStatus: [
      { status: 'active', count: 2 },
      { status: 'draft', count: 1 },
      { status: 'closed', count: 1 },
    ],
  },
  readinessPercent: 86,
};

/**
 * The `partial` scenario: processing has run, but nothing has reached
 * review yet and readiness has not been assessed. Same contract, so the
 * "some of this workspace has no figures yet" path is reviewable without a
 * second shape.
 */
export const PREVIEW_DASHBOARD_SUPPLEMENT_PARTIAL: DashboardPreviewSupplement = {
  documentsByState: {
    processed: 2,
    processing: 1,
    pending: 5,
    failed: 0,
  },
  evidenceReview: {
    pendingReview: 0,
    approved: 0,
    rejected: 0,
    withdrawn: 0,
  },
  engagements: {
    total: 1,
    byStatus: [{ status: 'draft', count: 1 }],
  },
  readinessPercent: 0,
};
