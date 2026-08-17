import type { DocumentState, DocumentSummary } from './documents';

/**
 * The Live dashboard model.
 *
 * Deliberately separate from `DashboardSnapshot` (the Preview model),
 * because the two are not the same shape and pretending otherwise is how
 * fabricated metrics get onto a Live screen. `DashboardSnapshot` describes
 * a fully-featured workspace; this describes **only what existing
 * FastAPI contracts can prove**.
 *
 * Every number here is exact, never inferred from a partial page:
 *
 * - `documentsTotal` is the `total` field of `GET /api/v1/documents`, which
 *   the backend computes with its own `COUNT(*)` over the tenant-scoped
 *   query — not `items.length`.
 * - `documentsByState` is four more calls to the same endpoint, each with
 *   `processing_status` bound and `limit=1`, reading `total` from each.
 *   The filter and the total are both part of the verified contract.
 * - `engagementsTotal` is the `total` field of `GET /api/v1/engagements`.
 * - `recentDocuments` are real rows from the documents list, newest first
 *   (the endpoint already orders by `created_at DESC`).
 *
 * A `null` on any counter means the request for it failed; the card then
 * renders an explicit unavailable state instead of a zero. Zero and
 * "couldn't load" are different claims and must look different.
 *
 * Capabilities with no backing contract are absent by construction rather
 * than present-and-empty: evidence-review counts (F2B), the activity feed,
 * compliance readiness, and the processing queue have no endpoint, so they
 * have no field here to accidentally populate.
 */
export interface DashboardLiveSummary {
  readonly organizationName: string | null;
  readonly documentsTotal: number | null;
  readonly documentsByState: Readonly<Record<DocumentState, number | null>>;
  readonly engagementsTotal: number | null;
  readonly recentDocuments: readonly DocumentSummary[];
}

/** The metrics a Live dashboard cannot source from any existing contract.
 * Rendered as compact, specific disclosures — never as zeroes. */
export const LIVE_UNAVAILABLE_METRICS = [
  'evidenceReview',
  'activity',
  'readiness',
  'processingQueue',
] as const;

export type LiveUnavailableMetric = (typeof LIVE_UNAVAILABLE_METRICS)[number];
