export type AnalysisRunStatus = 'COMPLETE' | 'PROCESSING' | 'FAILED' | 'INSUFFICIENT_EVIDENCE';

export interface MockAnalysisRun {
  id: string;
  analysisName: string;
  documentName: string;
  orgName: string;
  status: AnalysisRunStatus;
  startedAt: string;
  confidence?: number;
  summary: string;
  findings: string[];
  recommendations: string[];
}

/** Sample presentation data. Findings and references are not real evidence. */
export const MOCK_ANALYSIS_RUNS: MockAnalysisRun[] = [
  {
    id: 'run-1',
    analysisName: 'Q3 Sustainability Review',
    documentName: 'Q3 2025 Sustainability Report.pdf',
    orgName: 'Al-Riyadh Industrial Group',
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
    analysisName: 'Scope 1 Emissions Check',
    documentName: 'Scope 1 Emissions Ledger.pdf',
    orgName: 'Al-Riyadh Industrial Group',
    status: 'PROCESSING',
    startedAt: '13 Jul 2026, 11:19',
    summary: '',
    findings: [],
    recommendations: [],
  },
  {
    id: 'run-3',
    analysisName: 'Supplier ESG Screening',
    documentName: 'Supplier ESG Questionnaire.pdf',
    orgName: 'NEOM Utilities Authority',
    status: 'FAILED',
    startedAt: '10 Jul 2026, 15:31',
    summary: '',
    findings: [],
    recommendations: [],
  },
  {
    id: 'run-4',
    analysisName: 'Water Usage Compliance Check',
    documentName: 'Water Usage Audit.pdf',
    orgName: 'Jeddah Logistics Co.',
    status: 'COMPLETE',
    startedAt: '9 Jul 2026, 08:12',
    confidence: 74,
    summary:
      'Facility-level water withdrawal figures are presented consistently, though discharge quality data is only partially disclosed.',
    findings: [
      'Withdrawal volumes are broken out by facility and quarter.',
      'Discharge quality data is missing for two of five facilities.',
    ],
    recommendations: ['Request discharge quality records for the remaining facilities.'],
  },
  {
    id: 'run-5',
    analysisName: 'Q2 Sustainability Review',
    documentName: 'Q2 2025 Sustainability Report.pdf',
    orgName: 'Al-Riyadh Industrial Group',
    status: 'COMPLETE',
    startedAt: '3 Jul 2026, 14:05',
    confidence: 91,
    summary:
      'The sample report shows a complete emissions inventory with clear methodology notes and third-party verification references.',
    findings: [
      'Scope 1 and 2 emissions are reconciled against the prior quarter.',
      'A third-party verification statement is referenced and dated.',
    ],
    recommendations: ['Carry the same verification approach into the Q3 report.'],
  },
  {
    id: 'run-6',
    analysisName: 'Facility Energy Log Review',
    documentName: 'Facility Energy Log — August.csv',
    orgName: 'Jeddah Logistics Co.',
    status: 'INSUFFICIENT_EVIDENCE',
    startedAt: '8 Jul 2026, 10:27',
    summary:
      'The sample source does not contain enough structured data to produce a reliable summary.',
    findings: ['Fewer than half of the expected facility readings are present in the source file.'],
    recommendations: ['Request a complete export before re-running this analysis.'],
  },
  {
    id: 'run-7',
    analysisName: 'Supplier Scorecard Review',
    documentName: 'Supplier Scorecard 2025.xlsx',
    orgName: 'NEOM Utilities Authority',
    status: 'PROCESSING',
    startedAt: '14 Jul 2026, 07:50',
    summary: '',
    findings: [],
    recommendations: [],
  },
  {
    id: 'run-8',
    analysisName: 'Biodiversity Impact Screening',
    documentName: 'Biodiversity Impact Study.pdf',
    orgName: 'Al-Riyadh Industrial Group',
    status: 'INSUFFICIENT_EVIDENCE',
    startedAt: '6 Jul 2026, 16:38',
    summary: 'The sample source is missing the site survey appendix referenced in its own summary.',
    findings: ['The document references an appendix that is not present in the uploaded file.'],
    recommendations: ['Re-upload the document with the full appendix attached.'],
  },
  {
    id: 'run-9',
    analysisName: 'Carbon Footprint Review',
    documentName: 'Carbon Footprint Review.pdf',
    orgName: 'NEOM Utilities Authority',
    status: 'COMPLETE',
    startedAt: '2 Jul 2026, 12:15',
    confidence: 68,
    summary:
      'The sample report covers Scope 1 and 2 emissions; Scope 3 categories are only partially addressed.',
    findings: [
      'Scope 1 and 2 figures are presented with a clear calculation basis.',
      'Scope 3 purchased-goods estimates rely on an unstated methodology.',
    ],
    recommendations: ['Document the Scope 3 estimation methodology before external use.'],
  },
];

export interface AnalysisStatusCount {
  status: AnalysisRunStatus;
  count: number;
}

const STATUS_ORDER: AnalysisRunStatus[] = [
  'COMPLETE',
  'PROCESSING',
  'FAILED',
  'INSUFFICIENT_EVIDENCE',
];

/** Single source of truth for status totals — consumed by both the AI
 * Analysis page's KPI strip and the dashboard's Analysis Summary donut, so
 * the two can never drift out of sync with each other. */
export const ANALYSIS_STATUS_BREAKDOWN: AnalysisStatusCount[] = STATUS_ORDER.map((status) => ({
  status,
  count: MOCK_ANALYSIS_RUNS.filter((run) => run.status === status).length,
}));
