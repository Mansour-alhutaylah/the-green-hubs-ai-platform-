import { apiRequest } from '../client';
import type {
  DocumentEvidenceResponse,
  DocumentListResponse,
  DocumentReadResponse,
  DocumentResponse,
  EmbeddingGenerationSummaryResponse,
  ListDocumentsParams,
} from '../types';

/** GET /api/v1/documents — server-side paginated, filtered by the caller's
 * own organization on the backend (never a client-supplied organization
 * id). Only forwards the query parameters the backend actually supports. */
export function listDocuments(
  params: ListDocumentsParams,
  signal?: AbortSignal,
): Promise<DocumentListResponse> {
  return apiRequest<DocumentListResponse>('/api/v1/documents', {
    query: {
      engagement_id: params.engagement_id,
      processing_status: params.processing_status,
      evidence_status: params.evidence_status,
      limit: params.limit,
      offset: params.offset,
    },
    signal,
  });
}

/** GET /api/v1/documents/{document_id} */
export function getDocument(documentId: string, signal?: AbortSignal): Promise<DocumentReadResponse> {
  return apiRequest<DocumentReadResponse>(`/api/v1/documents/${documentId}`, { signal });
}

/** POST /api/v1/documents — multipart upload. `engagement_id` and `file`
 * only; `organization_id` is never sent (tenant scope is derived
 * server-side from the bearer token). */
export function uploadDocument(
  params: { engagementId: string; file: File },
  signal?: AbortSignal,
): Promise<DocumentResponse> {
  const formData = new FormData();
  formData.append('engagement_id', params.engagementId);
  formData.append('file', params.file);
  return apiRequest<DocumentResponse>('/api/v1/documents', {
    method: 'POST',
    formData,
    signal,
  });
}

/** POST /api/v1/documents/{document_id}/process — synchronous on this
 * backend: the response is already the terminal PROCESSED/FAILED state
 * (or a mapped error), never an in-flight PROCESSING acknowledgement. */
export function processDocument(documentId: string, signal?: AbortSignal): Promise<DocumentResponse> {
  return apiRequest<DocumentResponse>(`/api/v1/documents/${documentId}/process`, {
    method: 'POST',
    signal,
  });
}

/** POST /api/v1/documents/{document_id}/embeddings — deliberately no
 * request body: the backend derives everything from the path id and the
 * bearer token (never a client-supplied organization id). Idempotent per
 * chunk: chunks embedded earlier come back counted in `already_completed`,
 * never as an error. 409 = the document is not PROCESSED yet. */
export function generateEmbeddings(
  documentId: string,
  signal?: AbortSignal,
): Promise<EmbeddingGenerationSummaryResponse> {
  return apiRequest<EmbeddingGenerationSummaryResponse>(`/api/v1/documents/${documentId}/embeddings`, {
    method: 'POST',
    signal,
  });
}

/* -------------------------------------------------------------------- *
 * Evidence review — the four explicit review commands.
 *
 * One private helper issues all four because they share a single
 * contract, and duplicating it four times is how the four drift apart.
 *
 * What is deliberately *absent* from every request below:
 *
 * * no organization or tenant identifier. The backend resolves the
 *   caller's organization from the bearer token and scopes the document
 *   lookup to it; a client-supplied one would be an authorization input
 *   the browser controls. None of these route contracts accepts one.
 * * no `reviewed_by`, `reviewed_at` or `evidence_status`. The server
 *   records who decided, when, and what the resulting state is. A client
 *   that sent them would be asserting provenance it cannot be trusted for
 *   — and the backend's command schemas reject the fields outright.
 *
 * The response is always the document's *current* decision as stored,
 * including on an idempotent repeat, so a caller re-renders from the
 * server's answer rather than from what it hoped it had written.
 * -------------------------------------------------------------------- */

function reviewEvidence(
  documentId: string,
  command: 'verify' | 'reject' | 'restrict' | 'supersede',
  body: object | undefined,
  signal?: AbortSignal,
): Promise<DocumentEvidenceResponse> {
  return apiRequest<DocumentEvidenceResponse>(
    `/api/v1/documents/${documentId}/evidence/${command}`,
    { method: 'POST', json: body, signal },
  );
}

/** POST /api/v1/documents/{document_id}/evidence/verify — approve a
 * document as evidence eligible for retrieval.
 *
 * 409 when the document is not in a verifiable state *or* is not
 * `PROCESSED`: approving a document asserts something about content that
 * does not exist until extraction and chunking have completed. `reason`
 * is an optional note; the route accepts an absent body entirely. */
export function verifyDocumentEvidence(
  documentId: string,
  params: { reason?: string } = {},
  signal?: AbortSignal,
): Promise<DocumentEvidenceResponse> {
  const reason = params.reason?.trim();
  return reviewEvidence(documentId, 'verify', reason ? { reason } : {}, signal);
}

/** POST /api/v1/documents/{document_id}/evidence/reject — refuse a
 * document as approved evidence. The reason is mandatory: a refusal is
 * not interpretable without one, and the backend answers a missing or
 * blank reason with 422. */
export function rejectDocumentEvidence(
  documentId: string,
  params: { reason: string },
  signal?: AbortSignal,
): Promise<DocumentEvidenceResponse> {
  return reviewEvidence(documentId, 'reject', { reason: params.reason }, signal);
}

/** POST /api/v1/documents/{document_id}/evidence/restrict — exclude a
 * document from normal retrieval. Reason mandatory, as for reject. This
 * is not a clearance or classification system: it means exactly
 * "retrieval ineligible". */
export function restrictDocumentEvidence(
  documentId: string,
  params: { reason: string },
  signal?: AbortSignal,
): Promise<DocumentEvidenceResponse> {
  return reviewEvidence(documentId, 'restrict', { reason: params.reason }, signal);
}

/** POST /api/v1/documents/{document_id}/evidence/supersede — mark a
 * document obsolete, optionally recording the document that replaces it.
 *
 * The successor is optional (a reviewer may mark something obsolete with
 * no replacement to point at), and is omitted from the body rather than
 * sent as `null` when absent. Recording a successor never approves it: it
 * stays in whatever state it already holds. A document may not supersede
 * itself — refused server-side, and not offered by the UI. */
export function supersedeDocumentEvidence(
  documentId: string,
  params: { reason: string; supersededByDocumentId?: string },
  signal?: AbortSignal,
): Promise<DocumentEvidenceResponse> {
  const successor = params.supersededByDocumentId?.trim();
  return reviewEvidence(
    documentId,
    'supersede',
    successor
      ? { reason: params.reason, superseded_by_document_id: successor }
      : { reason: params.reason },
    signal,
  );
}
