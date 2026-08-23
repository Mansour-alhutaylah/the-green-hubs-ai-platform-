import { useCallback } from 'react';
import { listDocuments } from '@/lib/api/endpoints/documents';
import { listEngagements } from '@/lib/api/endpoints/engagements';
import { listOrganizations } from '@/lib/api/endpoints/organizations';
import type {
  DocumentListResponse,
  DocumentProcessingStatus,
  OrganizationListResponse,
} from '@/lib/api/types';
import { toDashboardLiveSummary } from '../../adapters/dashboardLiveAdapter';
import type { DashboardLiveSummary } from '../../contracts/dashboardLive';
import type { DocumentState } from '../../contracts/documents';
import { useAsyncResource, type AsyncResource } from '../useAsyncResource';

/**
 * The Live dashboard source.
 *
 * **Seven requests**, issued in parallel, every one of them to an endpoint
 * that already exists, and every figure read from a `total` the backend
 * computed. One request serves two fields; the other six are one-for-one:
 *
 * | # | request                                                  | field(s) it supports              |
 * |---|----------------------------------------------------------|-----------------------------------|
 * | 1 | `GET /organizations?page=1&page_size=1`                  | `items[0].name` → organization    |
 * | 2 | `GET /documents?limit=5&offset=0`                        | `total` → documents count, **and** that response's `items` → the five recent rows (`created_at DESC`) |
 * | 3 | `GET /engagements?page=1&page_size=1`                    | `total` → engagements count       |
 * | 4 | `GET /documents?processing_status=PENDING&limit=1`       | `total` → pending count           |
 * | 5 | `GET /documents?processing_status=PROCESSING&limit=1`    | `total` → processing count        |
 * | 6 | `GET /documents?processing_status=PROCESSED&limit=1`     | `total` → processed count         |
 * | 7 | `GET /documents?processing_status=FAILED&limit=1`        | `total` → failed count            |
 *
 * (An earlier version of this comment said "six requests" and collapsed the
 * four per-state calls into a single table row. The count is seven.)
 *
 * `Promise.allSettled`, not `Promise.all`, is the load-bearing choice: one
 * failed counter must not blank the six that succeeded, and it must not
 * silently become a zero either. A rejected request contributes `null`,
 * the adapter carries the `null` into the summary, and the card renders an
 * explicit unavailable state. Zero is a measurement; `null` is the absence
 * of one.
 *
 * Nothing here derives a global figure from a returned page. The six
 * numeric figures come from six `total` fields; `items` is used only to
 * list the five documents it literally contains. The per-state requests
 * deliberately ask for `limit: 1` — the rows are not wanted, only the count
 * the backend puts beside them.
 *
 * Capabilities with no endpoint (evidence-review counts, an activity feed,
 * compliance readiness, a processing queue) are absent from
 * `DashboardLiveSummary` entirely, so there is no field here to populate
 * with a guess.
 */

const RECENT_DOCUMENT_LIMIT = 5;

const WIRE_STATUS_BY_STATE: Record<DocumentState, DocumentProcessingStatus> = {
  pending: 'PENDING',
  processing: 'PROCESSING',
  processed: 'PROCESSED',
  failed: 'FAILED',
};

const DOCUMENT_STATES: readonly DocumentState[] = [
  'pending',
  'processing',
  'processed',
  'failed',
];

/** Some of the workspace resolved and some did not — the page marks itself
 * partial rather than presenting an incomplete picture as a whole one.
 * Module-level so its identity is stable across renders. */
function hasMissingCounter(summary: DashboardLiveSummary): boolean {
  return (
    summary.documentsTotal == null ||
    summary.engagementsTotal == null ||
    summary.organizationName == null ||
    DOCUMENT_STATES.some((state) => summary.documentsByState[state] == null)
  );
}

/** `null` for a rejected request — never a substituted default. */
async function settled<T>(promise: Promise<T>): Promise<T | null> {
  const [result] = await Promise.allSettled([promise]);
  return result?.status === 'fulfilled' ? result.value : null;
}

export function useLiveDashboardSummary(enabled: boolean): AsyncResource<DashboardLiveSummary> {
  const load = useCallback(async (signal: AbortSignal): Promise<DashboardLiveSummary> => {
    const [organizations, documents, engagements, ...byState] = await Promise.all([
      settled<OrganizationListResponse>(listOrganizations(signal)),
      settled<DocumentListResponse>(
        listDocuments({ limit: RECENT_DOCUMENT_LIMIT, offset: 0 }, signal),
      ),
      settled<{ total: number }>(listEngagements({ page: 1, page_size: 1 }, signal)),
      ...DOCUMENT_STATES.map((state) =>
        settled<DocumentListResponse>(
          listDocuments(
            { processing_status: WIRE_STATUS_BY_STATE[state], limit: 1, offset: 0 },
            signal,
          ),
        ),
      ),
    ]);

    const documentsByState = DOCUMENT_STATES.reduce<
      Record<DocumentState, DocumentListResponse | null>
    >(
      (accumulator, state, index) => {
        accumulator[state] = byState[index] ?? null;
        return accumulator;
      },
      { pending: null, processing: null, processed: null, failed: null },
    );

    const everyRequestFailed =
      organizations == null &&
      documents == null &&
      engagements == null &&
      DOCUMENT_STATES.every((state) => documentsByState[state] == null);

    // Total failure is a failure, not a dashboard of six "unavailable"
    // cards: the user needs "this could not be loaded, try again", with a
    // retry, rather than six separate shrugs.
    if (everyRequestFailed) throw new Error('The dashboard could not be loaded.');

    return toDashboardLiveSummary({
      organizations,
      documents,
      documentsByState,
      engagementsTotal: engagements?.total ?? null,
    });
  }, []);

  return useAsyncResource(enabled, load, { isPartial: hasMissingCounter });
}
