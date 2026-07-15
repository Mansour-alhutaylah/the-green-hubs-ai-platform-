/**
 * Wire types mirroring the backend's actual Pydantic response models
 * (backend/app/schemas/*.py) — field names and nullability match the
 * verified contract exactly, not an assumed shape.
 */

export interface UserProfileResponse {
  id: string;
  organization_id: string | null;
  full_name: string;
  email: string;
  role: string | null;
}

export interface OrganizationResponse {
  id: string;
  name: string;
  created_at: string | null;
}

export interface OrganizationListResponse {
  items: OrganizationResponse[];
  page: number;
  page_size: number;
  total: number;
}

export interface EngagementResponse {
  id: string;
  organization_id: string | null;
  title: string;
  status: string | null;
  created_at: string | null;
}

export interface EngagementListResponse {
  items: EngagementResponse[];
  page: number;
  page_size: number;
  total: number;
}

/** backend/app/schemas/document.py::DocumentProcessingStatus */
export type DocumentProcessingStatus = 'PENDING' | 'PROCESSING' | 'PROCESSED' | 'FAILED';

/** Response shape of POST /documents and POST /documents/{id}/process. */
export interface DocumentResponse {
  id: string;
  engagement_id: string;
  filename: string;
  processing_status: string;
  created_at: string;
  updated_at: string;
}

export interface EmbeddingSummaryResponse {
  total_chunks: number;
  processing: number;
  completed: number;
  failed: number;
  is_complete: boolean;
}

export interface AnalysisSummaryResponse {
  id: string;
  status: string;
  analysis_type: string;
  created_at: string | null;
  completed_at: string | null;
  overall_confidence: number | null;
}

/** Response shape of GET /documents (list items) and GET /documents/{id}. */
export interface DocumentReadResponse {
  id: string;
  engagement_id: string;
  filename: string;
  processing_status: string;
  created_at: string;
  updated_at: string;
  has_extracted_text: boolean;
  chunk_count: number;
  embedding_summary: EmbeddingSummaryResponse;
  latest_analysis_summary: AnalysisSummaryResponse | null;
}

export interface DocumentListResponse {
  items: DocumentReadResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface ListDocumentsParams {
  engagement_id?: string;
  processing_status?: DocumentProcessingStatus;
  limit?: number;
  offset?: number;
}
