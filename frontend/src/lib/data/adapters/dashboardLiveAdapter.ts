import type { DocumentListResponse, OrganizationListResponse } from '@/lib/api/types';
import type { DocumentState } from '../contracts/documents';
import type { DashboardLiveSummary } from '../contracts/dashboardLive';
import { toDocumentSummaries } from './documentAdapter';

/**
 * Assembles the Live dashboard from real responses.
 *
 * The important rule is encoded in the types: every counter argument is
 * `number | null`, and the only way to obtain one is to read a `total`
 * field the backend computed. Nothing here derives a count from
 * `items.length`, because a page of results is not a total — that is
 * exactly the "partial-page count labelled as a global count" mistake this
 * dashboard exists to avoid.
 *
 * A `null` counter means its request failed, and the card renders as
 * unavailable rather than as zero.
 */
export interface DashboardLiveSources {
  /** `GET /organizations` — the caller's own organization, or `null` if
   * the request failed or returned none. */
  organizations: OrganizationListResponse | null;
  /** `GET /documents?limit=…` — supplies both the exact global `total`
   * and the newest rows. `null` when the request failed. */
  documents: DocumentListResponse | null;
  /** `GET /documents?processing_status=X&limit=1` per state — each entry's
   * `total` is the exact count for that state. `null` per state when that
   * request failed. */
  documentsByState: Readonly<Record<DocumentState, DocumentListResponse | null>>;
  /** `GET /engagements?page_size=1` — `total` only. */
  engagementsTotal: number | null;
}

export function toDashboardLiveSummary(sources: DashboardLiveSources): DashboardLiveSummary {
  const states: DocumentState[] = ['pending', 'processing', 'processed', 'failed'];

  const documentsByState = states.reduce<Record<DocumentState, number | null>>(
    (accumulator, state) => {
      const response = sources.documentsByState[state];
      accumulator[state] = response == null ? null : response.total;
      return accumulator;
    },
    { pending: null, processing: null, processed: null, failed: null },
  );

  return {
    organizationName: sources.organizations?.items[0]?.name ?? null,
    documentsTotal: sources.documents?.total ?? null,
    documentsByState,
    engagementsTotal: sources.engagementsTotal,
    recentDocuments: sources.documents == null ? [] : toDocumentSummaries(sources.documents.items),
  };
}
