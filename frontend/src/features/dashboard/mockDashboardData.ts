import type { StringKey } from '@/lib/i18n/strings/en';

/**
 * Static, local, presentation-only fixture data for the executive dashboard
 * shell (Enterprise UI Polish Pass). None of this is fetched, computed, or
 * persisted — it exists purely so the dashboard reads as a populated
 * workspace instead of an empty box. The page itself surfaces a visible
 * "Sample data" indicator (`dashboard.sampleData`) so it's never mistaken
 * for real production figures. Replacing this with live data later is a
 * data-layer change only — the components below take shaped props, not this
 * module directly.
 */

export type DocumentStatus = 'analyzed' | 'processing' | 'queued';
export type ComplianceState = 'onTrack' | 'needsReview';
export type ActivityAction = 'uploaded' | 'approved' | 'viewed' | 'published';
export type KpiTone = 'positive' | 'neutral' | 'attention';

export interface MockKpi {
  id: string;
  labelKey: StringKey;
  value: string;
  captionKey: StringKey;
  tone: KpiTone;
}

export interface MockRecentDocument {
  id: string;
  name: string;
  orgName: string;
  status: DocumentStatus;
  timestamp: string;
}

export interface MockAnalysisInsight {
  id: string;
  documentName: string;
  status: DocumentStatus;
  detail: string;
}

export interface MockActivityEntry {
  id: string;
  actorName: string;
  action: ActivityAction;
  documentName: string;
  timestamp: string;
}

export interface MockComplianceFramework {
  id: string;
  name: string;
  status: ComplianceState;
}

export interface MockQueueItem {
  id: string;
  name: string;
  eta: string;
}

export const DASHBOARD_KPIS: MockKpi[] = [
  {
    id: 'documents-analyzed',
    labelKey: 'dashboard.kpi.documentsAnalyzed',
    value: '128',
    captionKey: 'dashboard.kpi.documentsAnalyzed.caption',
    tone: 'positive',
  },
  {
    id: 'active-reports',
    labelKey: 'dashboard.kpi.activeReports',
    value: '6',
    captionKey: 'dashboard.kpi.activeReports.caption',
    tone: 'neutral',
  },
  {
    id: 'compliance-score',
    labelKey: 'dashboard.kpi.complianceScore',
    value: '86%',
    captionKey: 'dashboard.kpi.complianceScore.caption',
    tone: 'positive',
  },
  {
    id: 'pending-approvals',
    labelKey: 'dashboard.kpi.pendingApprovals',
    value: '3',
    captionKey: 'dashboard.kpi.pendingApprovals.caption',
    tone: 'attention',
  },
];

export const RECENT_DOCUMENTS: MockRecentDocument[] = [
  {
    id: 'doc-1',
    name: 'Q3 2025 Sustainability Report.pdf',
    orgName: 'Al-Riyadh Industrial Group',
    status: 'analyzed',
    timestamp: '2 days ago',
  },
  {
    id: 'doc-2',
    name: 'Scope 1 Emissions Ledger.xlsx',
    orgName: 'Al-Riyadh Industrial Group',
    status: 'processing',
    timestamp: '5 hours ago',
  },
  {
    id: 'doc-3',
    name: 'Water Usage Audit.pdf',
    orgName: 'Jeddah Logistics Co.',
    status: 'queued',
    timestamp: 'Yesterday',
  },
  {
    id: 'doc-4',
    name: 'Supplier ESG Questionnaire.docx',
    orgName: 'NEOM Utilities Authority',
    status: 'analyzed',
    timestamp: '4 days ago',
  },
];

export const RECENT_ANALYSIS: MockAnalysisInsight[] = [
  {
    id: 'insight-1',
    documentName: 'Q3 2025 Sustainability Report.pdf',
    status: 'analyzed',
    detail: '42 figures extracted, 3 flagged for review',
  },
  {
    id: 'insight-2',
    documentName: 'Scope 1 Emissions Ledger.xlsx',
    status: 'processing',
    detail: 'Running extraction — 60% complete',
  },
  {
    id: 'insight-3',
    documentName: 'Water Usage Audit.pdf',
    status: 'queued',
    detail: 'Queued for analysis',
  },
];

export const RECENT_ACTIVITY: MockActivityEntry[] = [
  {
    id: 'activity-1',
    actorName: 'Reem Al-Harbi',
    action: 'approved',
    documentName: 'Q3 2025 Sustainability Report.pdf',
    timestamp: '2 days ago',
  },
  {
    id: 'activity-2',
    actorName: 'Faisal Al-Dossary',
    action: 'uploaded',
    documentName: 'Scope 1 Emissions Ledger.xlsx',
    timestamp: '5 hours ago',
  },
  {
    id: 'activity-3',
    actorName: 'Noura Al-Zahrani',
    action: 'viewed',
    documentName: 'Supplier ESG Questionnaire.docx',
    timestamp: '3 days ago',
  },
  {
    id: 'activity-4',
    actorName: 'Adel Al-Qahtani',
    action: 'published',
    documentName: 'Q2 2025 Sustainability Report.pdf',
    timestamp: '1 week ago',
  },
];

export const COMPLIANCE_FRAMEWORKS: MockComplianceFramework[] = [
  { id: 'gri', name: 'GRI', status: 'onTrack' },
  { id: 'csrd', name: 'CSRD', status: 'needsReview' },
  { id: 'saudi', name: 'Saudi Sustainability Standards', status: 'onTrack' },
];

export const PROCESSING_QUEUE: MockQueueItem[] = [
  { id: 'queue-1', name: 'Water Usage Audit.pdf', eta: '~10 min' },
  { id: 'queue-2', name: 'Facility Energy Log — August.csv', eta: '~15 min' },
  { id: 'queue-3', name: 'Supplier Scorecard 2025.xlsx', eta: '~20 min' },
];
