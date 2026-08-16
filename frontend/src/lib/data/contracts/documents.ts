import type { IsoTimestamp } from './common';
import type { DocumentId, EngagementId } from './ids';

/**
 * Normalized Frontend view of a document. Mirrors the *meaning* of the
 * verified backend contract (`backend/app/schemas/document.py`, wired as
 * `DocumentReadResponse` in `src/lib/api/types.ts`) without copying its
 * wire spelling into the UI: the mapping lives in
 * `src/lib/data/adapters/documentAdapter.ts` and nowhere else.
 *
 * Nothing here is a display string. `state` is a closed union, not a badge
 * label; `createdAt` is an instant, not "5 hours ago"; there is no
 * pre-formatted file size. Those are rendering decisions.
 */
export type DocumentState = 'pending' | 'processing' | 'processed' | 'failed';

export interface DocumentSummary {
  readonly id: DocumentId;
  readonly engagementId: EngagementId;
  readonly filename: string;
  readonly state: DocumentState;
  readonly createdAt: IsoTimestamp;
  readonly updatedAt: IsoTimestamp;
  readonly hasExtractedText: boolean;
  readonly chunkCount: number;
}
