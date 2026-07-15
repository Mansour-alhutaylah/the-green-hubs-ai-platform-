import { apiRequest } from '../client';
import type { AnalysisRunResponse } from '../types';

/** The only analysis_type the backend accepts this sprint (see
 * backend/app/services/analysis/rag_analysis.py::_ALLOWED_ANALYSIS_TYPES). */
export const SUSTAINABILITY_SUMMARY_ANALYSIS_TYPE = 'sustainability_summary';

/** Fixed, deterministic query for the standard document summary. The
 * backend hashes (analysis_type, query_text, …) into an idempotency key,
 * so keeping this constant means repeated requests resolve to the same run
 * instead of spawning new ones. Not user-editable — prompt editing is out
 * of scope this sprint. */
export const SUSTAINABILITY_SUMMARY_QUERY_TEXT =
  'Summarize the sustainability performance reported in this document, including reported metrics, key findings, and recommendations.';

/** POST /api/v1/analysis/documents/{document_id}/analyze — synchronous on
 * this backend (no queue or worker exists): the response is normally
 * already terminal (COMPLETED / FAILED / INSUFFICIENT_EVIDENCE). A
 * PROCESSING response is still possible when an identical request is
 * genuinely mid-flight elsewhere, so callers must treat the returned
 * status as data rather than assume terminality. Re-invoking with the same
 * constants is safe: COMPLETED/INSUFFICIENT_EVIDENCE runs are re-fetched,
 * FAILED runs are retried server-side. */
export function analyzeDocument(documentId: string, signal?: AbortSignal): Promise<AnalysisRunResponse> {
  return apiRequest<AnalysisRunResponse>(`/api/v1/analysis/documents/${documentId}/analyze`, {
    method: 'POST',
    json: {
      analysis_type: SUSTAINABILITY_SUMMARY_ANALYSIS_TYPE,
      query_text: SUSTAINABILITY_SUMMARY_QUERY_TEXT,
    },
    signal,
  });
}

/** GET /api/v1/analysis/runs/{analysis_run_id} */
export function getAnalysisRun(analysisRunId: string, signal?: AbortSignal): Promise<AnalysisRunResponse> {
  return apiRequest<AnalysisRunResponse>(`/api/v1/analysis/runs/${analysisRunId}`, { signal });
}
