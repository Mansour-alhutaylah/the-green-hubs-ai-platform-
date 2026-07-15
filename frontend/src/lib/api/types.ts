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

/** backend/app/schemas/embedding.py::EmbeddingGenerationSummaryResponse —
 * aggregate counts only, never vectors or per-row provider errors. */
export interface EmbeddingGenerationSummaryResponse {
  document_id: string;
  total_chunks: number;
  newly_completed: number;
  already_completed: number;
  failed: number;
  in_progress: number;
  conflicts: number;
}

/** The `analysis_runs.status` values the backend writes
 * (backend/app/services/analysis/rag_analysis.py). The column is a plain
 * string, so consumers must still handle unknown values safely. */
export type AnalysisRunStatus = 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'INSUFFICIENT_EVIDENCE';

/** backend/app/services/analysis/structured_output.py::MetricValue.status */
export type MetricStatus = 'stated' | 'not_stated' | 'uncertain';

/** backend/app/schemas/analysis.py::MetricValueOut. `citation_ids` holds
 * real persisted citation UUIDs — the backend remaps the LLM's temporary
 * source keys before this ever reaches a client. Optional-with-default
 * fields are typed optional so older stored results missing them still
 * parse safely. */
export interface MetricValueResponse {
  name: string;
  status: string;
  value?: string | null;
  unit?: string | null;
  period?: string | null;
  citation_ids?: string[];
}

/** backend/app/schemas/analysis.py::FindingOut */
export interface FindingResponse {
  statement: string;
  citation_ids?: string[];
}

/** backend/app/schemas/analysis.py::RecommendationOut */
export interface RecommendationResponse {
  statement: string;
  citation_ids?: string[];
}

/** backend/app/schemas/analysis.py::StructuredAnalysisOut */
export interface StructuredAnalysisResponse {
  analysis_type: string;
  evidence_status: string;
  insufficient_evidence_reason?: string | null;
  executive_summary: string;
  reporting_period?: string | null;
  detected_topics?: string[];
  reported_metrics?: MetricValueResponse[];
  key_findings?: FindingResponse[];
  recommendations?: RecommendationResponse[];
  overall_confidence?: number;
}

/** backend/app/schemas/analysis.py::CitationOut — server-verified evidence
 * only; the backend never exposes vectors, content hashes, or page numbers
 * (page-level provenance is not preserved by this backend). */
export interface CitationResponse {
  id: string;
  document_id: string;
  chunk_index: number;
  char_start: number;
  char_end: number;
  quoted_snippet: string;
  citation_order: number;
  relevance_score: number;
}

/** backend/app/schemas/analysis.py::AnalysisRunResponse — returned by both
 * POST /analysis/documents/{id}/analyze and GET /analysis/runs/{id}.
 * `citations` is populated only for COMPLETED runs. */
export interface AnalysisRunResponse {
  analysis_run_id: string;
  engagement_id: string;
  document_id: string | null;
  status: string;
  analysis_type: string;
  structured_output: StructuredAnalysisResponse | null;
  insufficient_evidence_reason: string | null;
  error_message: string | null;
  citations: CitationResponse[];
  created_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
}
