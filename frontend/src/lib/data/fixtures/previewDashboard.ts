import type { DocumentReadResponse } from '@/lib/api/types';
import type { DashboardSnapshotSource } from '../adapters/dashboardAdapter';

/**
 * Deterministic Preview fixtures for the dashboard.
 *
 * Rules this module holds itself to, because a fixture that drifts is worse
 * than no fixture at all:
 *
 * - No `Math.random()`, no `Date.now()`, no `new Date()` — every instant is
 *   a literal ISO 8601 string, so two renders (and two test runs) are
 *   byte-identical.
 * - Every identity is obviously synthetic. No real company, government
 *   entity, customer, person, or email address appears here.
 * - Documents are authored in the real `DocumentReadResponse` wire shape
 *   and converge with a future Live source through `dashboardAdapter`.
 * - Nothing here is ever rendered in Live mode; see `hooks/useDashboardSnapshot`.
 */

export const PREVIEW_ORGANIZATION_NAME = 'Green Hubs Demo Organization';

const GENERATED_AT = '2026-03-16T09:00:00.000Z';

function previewDocument(input: {
  id: string;
  filename: string;
  status: DocumentReadResponse['processing_status'];
  createdAt: string;
  updatedAt: string;
  chunkCount: number;
}): DocumentReadResponse {
  return {
    id: input.id,
    engagement_id: 'preview-engagement-facility-alpha',
    filename: input.filename,
    processing_status: input.status,
    created_at: input.createdAt,
    updated_at: input.updatedAt,
    has_extracted_text: input.chunkCount > 0,
    chunk_count: input.chunkCount,
    embedding_summary: {
      total_chunks: input.chunkCount,
      processing: 0,
      completed: input.chunkCount,
      failed: 0,
      is_complete: input.chunkCount > 0,
    },
    latest_analysis_summary: null,
  };
}

const PREVIEW_DOCUMENTS: DocumentReadResponse[] = [
  previewDocument({
    id: 'preview-document-1',
    filename: 'Facility Alpha — Sustainability Report.pdf',
    status: 'PROCESSED',
    createdAt: '2026-03-10T08:15:00.000Z',
    updatedAt: '2026-03-14T11:42:00.000Z',
    chunkCount: 128,
  }),
  previewDocument({
    id: 'preview-document-2',
    filename: 'Facility Alpha — Scope 1 Emissions Ledger.xlsx',
    status: 'PROCESSING',
    createdAt: '2026-03-15T06:05:00.000Z',
    updatedAt: '2026-03-16T04:30:00.000Z',
    chunkCount: 64,
  }),
  previewDocument({
    id: 'preview-document-3',
    filename: 'Facility Beta — Water Usage Audit.pdf',
    status: 'PENDING',
    createdAt: '2026-03-15T13:20:00.000Z',
    updatedAt: '2026-03-15T13:20:00.000Z',
    chunkCount: 0,
  }),
  previewDocument({
    id: 'preview-document-4',
    filename: 'Supplier Questionnaire — Demo Set.docx',
    status: 'PROCESSED',
    createdAt: '2026-03-08T09:45:00.000Z',
    updatedAt: '2026-03-12T15:10:00.000Z',
    chunkCount: 96,
  }),
];

export const PREVIEW_DASHBOARD_SOURCE: DashboardSnapshotSource = {
  generatedAt: GENERATED_AT,
  organizationName: PREVIEW_ORGANIZATION_NAME,
  documents: PREVIEW_DOCUMENTS,
  metrics: [
    {
      id: 'preview-metric-documents-analyzed',
      key: 'documentsAnalyzed',
      unit: 'count',
      value: 128,
      tone: 'positive',
    },
    {
      id: 'preview-metric-active-reports',
      key: 'activeReports',
      unit: 'count',
      value: 6,
      tone: 'neutral',
    },
    {
      id: 'preview-metric-compliance-score',
      key: 'complianceScore',
      unit: 'percentage',
      value: 86,
      tone: 'positive',
    },
    {
      id: 'preview-metric-pending-approvals',
      key: 'pendingApprovals',
      unit: 'count',
      value: 3,
      tone: 'attention',
    },
  ],
  recentAnalysis: [
    {
      runId: 'preview-run-1',
      documentFilename: 'Facility Alpha — Sustainability Report.pdf',
      processingStatus: 'PROCESSED',
      progressPercent: null,
      extractedFigureCount: 42,
      flaggedForReviewCount: 3,
    },
    {
      runId: 'preview-run-2',
      documentFilename: 'Facility Alpha — Scope 1 Emissions Ledger.xlsx',
      processingStatus: 'PROCESSING',
      progressPercent: 60,
      extractedFigureCount: null,
      flaggedForReviewCount: null,
    },
    {
      runId: 'preview-run-3',
      documentFilename: 'Facility Beta — Water Usage Audit.pdf',
      processingStatus: 'PENDING',
      progressPercent: null,
      extractedFigureCount: null,
      flaggedForReviewCount: null,
    },
  ],
  activity: [
    {
      id: 'preview-activity-1',
      actorName: 'Reviewer A',
      action: 'approved',
      documentFilename: 'Facility Alpha — Sustainability Report.pdf',
      occurredAt: '2026-03-14T11:42:00.000Z',
    },
    {
      id: 'preview-activity-2',
      actorName: 'Demo Administrator',
      action: 'uploaded',
      documentFilename: 'Facility Alpha — Scope 1 Emissions Ledger.xlsx',
      occurredAt: '2026-03-15T06:05:00.000Z',
    },
    {
      id: 'preview-activity-3',
      actorName: 'Reviewer B',
      action: 'viewed',
      documentFilename: 'Supplier Questionnaire — Demo Set.docx',
      occurredAt: '2026-03-13T08:20:00.000Z',
    },
    {
      id: 'preview-activity-4',
      actorName: 'Demo Administrator',
      action: 'published',
      documentFilename: 'Facility Beta — Water Usage Audit.pdf',
      occurredAt: '2026-03-09T10:00:00.000Z',
    },
  ],
  frameworks: [
    { id: 'preview-framework-gri', name: 'GRI', state: 'onTrack' },
    { id: 'preview-framework-csrd', name: 'CSRD', state: 'needsReview' },
    { id: 'preview-framework-demo', name: 'Demo Reporting Standard', state: 'onTrack' },
  ],
  processingQueue: [
    { id: 'preview-queue-1', filename: 'Facility Beta — Water Usage Audit.pdf', etaMinutes: 10 },
    { id: 'preview-queue-2', filename: 'Facility Alpha — Energy Log.csv', etaMinutes: 15 },
    { id: 'preview-queue-3', filename: 'Supplier Scorecard — Demo Set.xlsx', etaMinutes: 20 },
  ],
  monthlyAnalysisActivity: [
    { month: 1, completedRuns: 42 },
    { month: 2, completedRuns: 48 },
    { month: 3, completedRuns: 51 },
    { month: 4, completedRuns: 46 },
    { month: 5, completedRuns: 58 },
    { month: 6, completedRuns: 63 },
    { month: 7, completedRuns: 71 },
    { month: 8, completedRuns: 68 },
    { month: 9, completedRuns: 75 },
    { month: 10, completedRuns: 82 },
    { month: 11, completedRuns: 79 },
    { month: 12, completedRuns: 88 },
  ],
  analysisOutcomes: [
    { outcome: 'complete', count: 18 },
    { outcome: 'processing', count: 4 },
    { outcome: 'failed', count: 2 },
    { outcome: 'insufficientEvidence', count: 3 },
  ],
};

/**
 * The `partial` scenario: a workspace where processing has started but most
 * derived intelligence has not landed yet. Same contract, fewer populated
 * collections — so the UI's "some sections have nothing to show" path is
 * reviewable without inventing a second contract.
 */
export const PREVIEW_DASHBOARD_SOURCE_PARTIAL: DashboardSnapshotSource = {
  ...PREVIEW_DASHBOARD_SOURCE,
  documents: PREVIEW_DOCUMENTS.slice(0, 2),
  metrics: PREVIEW_DASHBOARD_SOURCE.metrics.slice(0, 2),
  recentAnalysis: PREVIEW_DASHBOARD_SOURCE.recentAnalysis.slice(1, 2),
  activity: PREVIEW_DASHBOARD_SOURCE.activity.slice(0, 1),
  frameworks: [],
  processingQueue: PREVIEW_DASHBOARD_SOURCE.processingQueue.slice(0, 1),
};

/* The `empty` scenario needs no fixture: it resolves to the `empty` data
 * state, which the page renders as a stated "nothing here yet" rather than
 * as a snapshot full of zeroes. */
