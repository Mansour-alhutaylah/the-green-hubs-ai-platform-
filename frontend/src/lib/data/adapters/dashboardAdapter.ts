import type { DocumentReadResponse } from '@/lib/api/types';
import { isoTimestamp } from '../contracts/common';
import {
  activityId,
  analysisRunId,
  documentId,
  frameworkId,
  metricId,
  queueItemId,
} from '../contracts/ids';
import type {
  ActivityAction,
  AnalysisOutcome,
  ComplianceState,
  DashboardSnapshot,
  MetricKey,
  MetricTone,
} from '../contracts/dashboard';
import { toDocumentState } from './documentAdapter';

/**
 * The dashboard's mapping boundary.
 *
 * `DashboardSnapshotSource` is the *unmapped* shape a source supplies:
 * plain strings, no branded ids, no validated instants. The Preview fixture
 * module is authored in exactly this shape, and its document records use
 * the real verified `DocumentReadResponse` wire type — so the Preview
 * source and a future Live source converge on one adapter instead of two
 * parallel domain models.
 *
 * There is deliberately no invented backend response type here. When F2
 * adds a real dashboard endpoint, its wire schema is mapped into this same
 * `DashboardSnapshotSource` and the UI below it does not change.
 */

export interface RawMetric {
  id: string;
  key: MetricKey;
  unit: 'count' | 'percentage';
  value: number;
  tone: MetricTone;
}

export interface RawAnalysisInsight {
  runId: string;
  documentFilename: string;
  /** Wire-spelled processing status, mapped through `toDocumentState`. */
  processingStatus: string;
  progressPercent: number | null;
  extractedFigureCount: number | null;
  flaggedForReviewCount: number | null;
}

export interface RawActivityEntry {
  id: string;
  actorName: string;
  action: ActivityAction;
  documentFilename: string;
  occurredAt: string;
}

export interface RawFramework {
  id: string;
  name: string;
  state: ComplianceState;
}

export interface RawQueueItem {
  id: string;
  filename: string;
  etaMinutes: number;
}

export interface RawActivityPoint {
  month: number;
  completedRuns: number;
}

export interface RawAnalysisOutcome {
  outcome: AnalysisOutcome;
  count: number;
}

export interface DashboardSnapshotSource {
  generatedAt: string;
  organizationName: string;
  /** The verified backend list-item contract, unchanged. */
  documents: readonly DocumentReadResponse[];
  metrics: readonly RawMetric[];
  recentAnalysis: readonly RawAnalysisInsight[];
  activity: readonly RawActivityEntry[];
  frameworks: readonly RawFramework[];
  processingQueue: readonly RawQueueItem[];
  monthlyAnalysisActivity: readonly RawActivityPoint[];
  analysisOutcomes: readonly RawAnalysisOutcome[];
}

export function toDashboardSnapshot(source: DashboardSnapshotSource): DashboardSnapshot {
  return {
    generatedAt: isoTimestamp(source.generatedAt),
    totals: {
      documentsTracked: source.documents.length,
      analysisRuns: source.analysisOutcomes.reduce((total, entry) => total + entry.count, 0),
    },
    metrics: source.metrics.map((metric) => ({
      id: metricId(metric.id),
      key: metric.key,
      unit: metric.unit,
      value: metric.value,
      tone: metric.tone,
    })),
    recentDocuments: source.documents.map((document) => ({
      id: documentId(document.id),
      filename: document.filename,
      organizationName: source.organizationName,
      state: toDocumentState(document.processing_status),
      updatedAt: isoTimestamp(document.updated_at),
    })),
    recentAnalysis: source.recentAnalysis.map((insight) => ({
      id: analysisRunId(insight.runId),
      documentFilename: insight.documentFilename,
      state: toDocumentState(insight.processingStatus),
      progressPercent: insight.progressPercent,
      extractedFigureCount: insight.extractedFigureCount,
      flaggedForReviewCount: insight.flaggedForReviewCount,
    })),
    activity: source.activity.map((entry) => ({
      id: activityId(entry.id),
      actorName: entry.actorName,
      action: entry.action,
      documentFilename: entry.documentFilename,
      occurredAt: isoTimestamp(entry.occurredAt),
    })),
    frameworks: source.frameworks.map((framework) => ({
      id: frameworkId(framework.id),
      name: framework.name,
      state: framework.state,
    })),
    processingQueue: source.processingQueue.map((item) => ({
      id: queueItemId(item.id),
      filename: item.filename,
      etaMinutes: item.etaMinutes,
    })),
    monthlyAnalysisActivity: source.monthlyAnalysisActivity.map((point) => ({
      month: point.month,
      completedRuns: point.completedRuns,
    })),
    analysisOutcomes: source.analysisOutcomes.map((entry) => ({
      outcome: entry.outcome,
      count: entry.count,
    })),
  };
}
