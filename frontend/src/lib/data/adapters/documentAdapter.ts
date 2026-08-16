import type { DocumentReadResponse } from '@/lib/api/types';
import { documentId, engagementId } from '../contracts/ids';
import { isoTimestamp } from '../contracts/common';
import type { DocumentState, DocumentSummary } from '../contracts/documents';

/**
 * The explicit mapping boundary between the backend's wire schema and the
 * UI's domain model. Both real API responses and Preview fixtures are
 * authored in the wire shape and converge here, which is what keeps the two
 * sources structurally identical — a fixture that drifts from
 * `DocumentReadResponse` stops compiling instead of rendering a shape the
 * real API will never return.
 *
 * `processing_status` is a plain string on the wire, so an unrecognized
 * value maps to `'pending'` rather than being cast: the UI must stay safe
 * against a status the Frontend has not been taught yet.
 */
const STATE_BY_WIRE_STATUS: Record<string, DocumentState> = {
  PENDING: 'pending',
  PROCESSING: 'processing',
  PROCESSED: 'processed',
  FAILED: 'failed',
};

export function toDocumentState(wireStatus: string): DocumentState {
  return STATE_BY_WIRE_STATUS[wireStatus] ?? 'pending';
}

export function toDocumentSummary(wire: DocumentReadResponse): DocumentSummary {
  return {
    id: documentId(wire.id),
    engagementId: engagementId(wire.engagement_id),
    filename: wire.filename,
    state: toDocumentState(wire.processing_status),
    createdAt: isoTimestamp(wire.created_at),
    updatedAt: isoTimestamp(wire.updated_at),
    hasExtractedText: wire.has_extracted_text,
    chunkCount: wire.chunk_count,
  };
}

export function toDocumentSummaries(wire: readonly DocumentReadResponse[]): DocumentSummary[] {
  return wire.map(toDocumentSummary);
}
