import { apiRequest } from '../client';
import type { DocumentListResponse, DocumentReadResponse, DocumentResponse, ListDocumentsParams } from '../types';

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
