import { ROUTES } from '@/app/navigation/routePaths';
import type { ExecutiveSummary } from '../contracts/executive';

/**
 * Deterministic Preview fixtures for the executive command centre.
 *
 * Same rules as every other fixture module here: literal values only, no
 * `Math.random()`, no `Date.now()`, and nothing that could be mistaken for
 * a real organization's figures. Never imported by a Live source, which is
 * checkable rather than aspirational: `hooks/live/` imports no fixture
 * module at all.
 *
 * The figures are internally consistent on purpose. The pipeline falls
 * monotonically (104 uploaded, 68 report-ready), `sourceDocuments` matches
 * the uploaded stage, `awaitingReview` matches the gap between analyzed
 * and verified, and `evidenceReadinessPercent` is 68/104 rounded. A
 * reviewer who checks the arithmetic finds it holds, rather than finding
 * four unrelated impressive numbers.
 *
 * The counts also agree with `previewDashboardSupplement.ts` and
 * `previewWorkspace.ts`, so the dashboard, Engagements, and Reports tell a
 * reviewer one story instead of three contradicting ones.
 */
export const PREVIEW_EXECUTIVE_SUMMARY: ExecutiveSummary = {
  evidenceReadinessPercent: 65,
  sourceDocuments: 104,
  awaitingReview: 12,
  processingHealthPercent: 97,
  processingFailures: 3,
  reportingPeriod: 'FY 2025',
  // Authored, not read from the clock, so every screenshot matches.
  generatedAt: '2026-03-31T09:15:00.000Z',

  pipeline: [
    { stage: 'uploaded', count: 104 },
    { stage: 'extracted', count: 98 },
    { stage: 'analyzed', count: 91 },
    { stage: 'verified', count: 79 },
    { stage: 'reportReady', count: 68 },
  ],

  throughput: [
    { month: 'Oct', verified: 9, reportReady: 5 },
    { month: 'Nov', verified: 14, reportReady: 9 },
    { month: 'Dec', verified: 11, reportReady: 8 },
    { month: 'Jan', verified: 17, reportReady: 13 },
    { month: 'Feb', verified: 15, reportReady: 14 },
    { month: 'Mar', verified: 13, reportReady: 19 },
  ],

  actions: [
    {
      id: 'failed-extraction',
      severity: 'critical',
      titleKey: 'dashboard.action.failedExtraction.title',
      detailKey: 'dashboard.action.failedExtraction.detail',
      route: ROUTES.documents,
      count: 3,
    },
    {
      id: 'awaiting-review',
      severity: 'attention',
      titleKey: 'dashboard.action.awaitingReview.title',
      detailKey: 'dashboard.action.awaitingReview.detail',
      route: ROUTES.documents,
      count: 12,
    },
    {
      id: 'insufficient-evidence',
      severity: 'attention',
      titleKey: 'dashboard.action.insufficientEvidence.title',
      detailKey: 'dashboard.action.insufficientEvidence.detail',
      route: ROUTES.analysis,
      count: 4,
    },
    {
      id: 'engagement-deadline',
      severity: 'scheduled',
      titleKey: 'dashboard.action.engagementDeadline.title',
      detailKey: 'dashboard.action.engagementDeadline.detail',
      route: ROUTES.engagements,
      count: 1,
    },
  ],

  frameworks: [
    {
      id: 'gri',
      label: 'GRI',
      coveragePercent: 74,
      disclosuresCovered: 43,
      disclosuresTotal: 58,
    },
    {
      id: 'csrd',
      label: 'CSRD',
      coveragePercent: 52,
      disclosuresCovered: 39,
      disclosuresTotal: 75,
    },
    {
      id: 'issb',
      label: 'ISSB',
      coveragePercent: 61,
      disclosuresCovered: 28,
      disclosuresTotal: 46,
    },
  ],
};

/**
 * The `partial` scenario: documents have landed and extraction has run,
 * but nothing has been verified and no framework has been assessed. Same
 * contract, so the "some of this workspace has no figures yet" path is
 * reviewable without inventing a second shape.
 */
export const PREVIEW_EXECUTIVE_SUMMARY_PARTIAL: ExecutiveSummary = {
  evidenceReadinessPercent: 0,
  sourceDocuments: 8,
  awaitingReview: 5,
  processingHealthPercent: 100,
  processingFailures: 0,
  reportingPeriod: 'FY 2025',
  generatedAt: '2026-03-31T09:15:00.000Z',

  pipeline: [
    { stage: 'uploaded', count: 8 },
    { stage: 'extracted', count: 6 },
    { stage: 'analyzed', count: 1 },
    { stage: 'verified', count: 0 },
    { stage: 'reportReady', count: 0 },
  ],

  throughput: [
    { month: 'Feb', verified: 0, reportReady: 0 },
    { month: 'Mar', verified: 0, reportReady: 0 },
  ],

  actions: [
    {
      id: 'awaiting-review',
      severity: 'attention',
      titleKey: 'dashboard.action.awaitingReview.title',
      detailKey: 'dashboard.action.awaitingReview.detail',
      route: ROUTES.documents,
      count: 5,
    },
  ],

  frameworks: [],
};
