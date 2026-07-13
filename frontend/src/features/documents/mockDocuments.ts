export type DocumentProcessingStatus = 'PENDING' | 'PROCESSING' | 'PROCESSED' | 'FAILED';

export interface MockDocument {
  id: string;
  name: string;
  type: 'PDF';
  size: string;
  owner: string;
  uploadedAt: string;
  updatedAt: string;
  status: DocumentProcessingStatus;
  engagement: string;
}

/** Local presentation fixtures only. No record is fetched or persisted. */
export const MOCK_DOCUMENTS: MockDocument[] = [
  {
    id: 'doc-1',
    name: 'Q3 2025 Sustainability Report.pdf',
    type: 'PDF',
    size: '8.4 MB',
    owner: 'Reem Al-Harbi',
    uploadedAt: '12 Jul 2026, 09:42',
    updatedAt: '12 Jul 2026, 09:58',
    status: 'PROCESSED',
    engagement: 'FY 2026 sustainability disclosure',
  },
  {
    id: 'doc-2',
    name: 'Scope 1 Emissions Ledger.pdf',
    type: 'PDF',
    size: '3.1 MB',
    owner: 'Faisal Al-Dossary',
    uploadedAt: '13 Jul 2026, 11:18',
    updatedAt: '13 Jul 2026, 11:22',
    status: 'PROCESSING',
    engagement: 'Operational emissions assurance',
  },
  {
    id: 'doc-3',
    name: 'Water Usage Audit.pdf',
    type: 'PDF',
    size: '5.7 MB',
    owner: 'Noura Al-Zahrani',
    uploadedAt: '13 Jul 2026, 10:05',
    updatedAt: '13 Jul 2026, 10:05',
    status: 'PENDING',
    engagement: 'Water stewardship review',
  },
  {
    id: 'doc-4',
    name: 'Supplier ESG Questionnaire.pdf',
    type: 'PDF',
    size: '1.9 MB',
    owner: 'Adel Al-Qahtani',
    uploadedAt: '10 Jul 2026, 15:30',
    updatedAt: '10 Jul 2026, 15:34',
    status: 'FAILED',
    engagement: 'Supplier due diligence',
  },
];
