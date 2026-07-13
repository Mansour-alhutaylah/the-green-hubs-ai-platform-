export type AnalysisRunStatus = 'COMPLETE' | 'PROCESSING' | 'FAILED';

export interface MockAnalysisRun {
  id: string;
  documentName: string;
  status: AnalysisRunStatus;
  startedAt: string;
  summary: string;
  confidence?: number;
  findings: string[];
  recommendations: string[];
}

/** Sample presentation data. Findings and references are not real evidence. */
export const MOCK_ANALYSIS_RUNS: MockAnalysisRun[] = [
  {
    id: 'run-1',
    documentName: 'Q3 2025 Sustainability Report.pdf',
    status: 'COMPLETE',
    startedAt: '12 Jul 2026, 09:44',
    confidence: 87,
    summary:
      'The sample report presents measurable progress on operational emissions and renewable electricity, while supplier data coverage remains incomplete.',
    findings: [
      'Operational emissions are presented with a year-over-year comparison.',
      'Renewable electricity coverage is disclosed for major facilities.',
      'Supplier emissions methodology requires additional review.',
    ],
    recommendations: [
      'Confirm the reporting boundary before external publication.',
      'Add a documented method for supplier-data estimation.',
    ],
  },
  {
    id: 'run-2',
    documentName: 'Scope 1 Emissions Ledger.pdf',
    status: 'PROCESSING',
    startedAt: '13 Jul 2026, 11:19',
    summary: '',
    findings: [],
    recommendations: [],
  },
  {
    id: 'run-3',
    documentName: 'Supplier ESG Questionnaire.pdf',
    status: 'FAILED',
    startedAt: '10 Jul 2026, 15:31',
    summary: '',
    findings: [],
    recommendations: [],
  },
];
