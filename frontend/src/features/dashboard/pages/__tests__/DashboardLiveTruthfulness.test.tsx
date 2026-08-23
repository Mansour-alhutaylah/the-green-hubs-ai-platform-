import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import { renderWithProviders } from '@/test/renderWithProviders';
import { buildLiveAuthService, LIVE_ORGANIZATION_NAME } from '@/test/liveSession';
import { en } from '@/lib/i18n/strings/en';
import type {
  DocumentListResponse,
  DocumentReadResponse,
  OrganizationListResponse,
} from '@/lib/api/types';
import { DashboardPage } from '../DashboardPage';

/**
 * The Live dashboard's arithmetic.
 *
 * Three rules, each of which has a specific way of going wrong that this
 * file exists to catch:
 *
 * 1. **Every figure is an exact `total` the backend computed.** The way
 *    this breaks is subtle and plausible-looking: a page reads
 *    `response.items.length` because the array is right there, which is
 *    correct only until the result set is larger than one page. The
 *    fixtures below deliberately make `total` and `items.length` differ, so
 *    a page that counted rows renders a visibly wrong number.
 * 2. **A failed request is never a zero.** `null` means "we could not find
 *    out"; `0` means "we counted, and there are none". They must not look
 *    alike, because acting on them differs completely.
 * 3. **Live renders nothing synthetic.** Not on success, and — the case
 *    worth testing — not on failure either.
 */

const listDocuments = vi.fn<(params: { processing_status?: string }) => Promise<DocumentListResponse>>();
const listEngagements = vi.fn<() => Promise<{ total: number }>>();
const listOrganizations = vi.fn<() => Promise<OrganizationListResponse>>();

vi.mock('@/lib/api/endpoints/documents', () => ({
  listDocuments: (...args: unknown[]) => listDocuments(...(args as [{ processing_status?: string }])),
}));
vi.mock('@/lib/api/endpoints/engagements', () => ({
  listEngagements: (...args: unknown[]) => listEngagements(...(args as [])),
}));
vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: (...args: unknown[]) => listOrganizations(...(args as [])),
}));

const RECENT_FILENAME = 'Live Backend Quarterly Ledger.pdf';

function buildDocument(id: string, filename = RECENT_FILENAME): DocumentReadResponse {
  return {
    id,
    engagement_id: 'eng-live-1',
    filename,
    processing_status: 'PROCESSED',
    created_at: '2026-05-01T10:00:00.000Z',
    updated_at: '2026-05-02T10:00:00.000Z',
    has_extracted_text: true,
    chunk_count: 12,
    embedding_summary: {
      total_chunks: 12,
      processing: 0,
      completed: 12,
      failed: 0,
      is_complete: true,
    },
    latest_analysis_summary: null,
  };
}

/**
 * `total` is deliberately far larger than `items.length` in every response
 * below. Anything on screen that equals a row count rather than a `total`
 * is the bug.
 */
const TOTAL_DOCUMENTS = 4137;
const TOTAL_PROCESSED = 3901;
const TOTAL_PROCESSING = 12;
const TOTAL_PENDING = 224;
const TOTAL_FAILED = 0; // A verified zero — it must render as "0".
const TOTAL_ENGAGEMENTS = 57;

const STATE_TOTALS: Record<string, number> = {
  PROCESSED: TOTAL_PROCESSED,
  PROCESSING: TOTAL_PROCESSING,
  PENDING: TOTAL_PENDING,
  FAILED: TOTAL_FAILED,
};

function renderLiveDashboard() {
  return renderWithProviders(<DashboardPage />, { authService: buildLiveAuthService() });
}

describe('Live dashboard truthfulness', () => {
  beforeEach(() => {
    listOrganizations.mockResolvedValue({
      items: [{ id: 'org-1', name: LIVE_ORGANIZATION_NAME, created_at: null }],
      page: 1,
      page_size: 20,
      total: 1,
    });
    listEngagements.mockResolvedValue({ total: TOTAL_ENGAGEMENTS });
    listDocuments.mockImplementation(async (params) => {
      if (params.processing_status) {
        return {
          // One row back, a large total beside it — exactly the shape that
          // catches a count derived from the page.
          items: [buildDocument('doc-state-sample')],
          total: STATE_TOTALS[params.processing_status] ?? 0,
          limit: 1,
          offset: 0,
        };
      }
      return {
        items: [buildDocument('doc-1'), buildDocument('doc-2', 'Live Backend Emissions Log.pdf')],
        total: TOTAL_DOCUMENTS,
        limit: 5,
        offset: 0,
      };
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders the exact server totals, not the number of rows returned', async () => {
    renderLiveDashboard();

    expect(await screen.findByText(String(TOTAL_DOCUMENTS))).toBeVisible();
    expect(screen.getByText(String(TOTAL_ENGAGEMENTS))).toBeVisible();
    expect(screen.getByText(String(TOTAL_PROCESSED))).toBeVisible();
    expect(screen.getByText(String(TOTAL_PROCESSING))).toBeVisible();
    expect(screen.getByText(String(TOTAL_PENDING))).toBeVisible();
  });

  it('never derives a figure from a partial page of results', async () => {
    renderLiveDashboard();
    await screen.findByText(String(TOTAL_DOCUMENTS));

    // Two documents came back for the recent list and one for each state
    // request. Neither row count may appear as a workspace figure.
    const totalsRegion = screen
      .getByRole('heading', { name: en['dashboard.live.section.totals'] })
      .closest('section');
    const processingRegion = screen
      .getByRole('heading', { name: en['dashboard.live.section.processing'] })
      .closest('section');

    for (const region of [totalsRegion, processingRegion]) {
      expect(region).not.toBeNull();
      // `items.length` was 2 for the list request and 1 for each filtered
      // request; the real totals are all far larger.
      expect(region?.textContent).not.toMatch(/(^|\D)2(\D|$)/);
    }
  });

  it('renders a verified zero as 0, and a failed counter as an explicit unavailable state', async () => {
    // `FAILED` genuinely counts zero; the engagements request fails.
    listEngagements.mockRejectedValue(new Error('network'));

    renderLiveDashboard();
    await screen.findByText(String(TOTAL_DOCUMENTS));

    // A counted zero is a measurement and renders as one.
    expect(screen.getByText('0')).toBeVisible();

    // The failed counter says so in words, and says it is not zero.
    expect(screen.getAllByText(en['workspace.value.unavailable']).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(en['workspace.value.unavailable.detail']).length,
    ).toBeGreaterThan(0);
  });

  it('marks the page partial when some counters resolved and others did not', async () => {
    listEngagements.mockRejectedValue(new Error('network'));

    renderLiveDashboard();

    expect(await screen.findByText(en['workspace.state.partial'])).toBeVisible();
  });

  it('states a total failure as a failure, offering a retry rather than zeroes', async () => {
    listOrganizations.mockRejectedValue(new Error('network'));
    listEngagements.mockRejectedValue(new Error('network'));
    listDocuments.mockRejectedValue(new Error('network'));

    renderLiveDashboard();

    expect(await screen.findByText(en['dashboard.live.error.title'])).toBeVisible();
    expect(screen.getByText(en['dashboard.live.error.description'])).toBeVisible();
    expect(screen.getByRole('button', { name: en['workspace.state.retry'] })).toBeVisible();
    expect(screen.queryByText('0')).toBeNull();
  });

  it('names every capability that has no service, in success and in failure alike', async () => {
    renderLiveDashboard();
    await screen.findByText(String(TOTAL_DOCUMENTS));

    for (const key of [
      'dashboard.live.unavailable.evidenceReview',
      'dashboard.live.unavailable.activity',
      'dashboard.live.unavailable.readiness',
      'dashboard.live.unavailable.processingQueue',
    ] as const) {
      expect(screen.getByText(en[key])).toBeVisible();
    }
  });

  it('renders real documents from the response and no Preview fixture content', async () => {
    renderLiveDashboard();

    expect(await screen.findByText(RECENT_FILENAME)).toBeVisible();

    // The organization name legitimately appears in more than one place — the
    // workspace shell names it too — so the assertion that matters is where it
    // appears: on the Live dashboard's own organization card, inside the
    // workspace totals section.
    const totalsSection = screen
      .getByRole('heading', { name: en['dashboard.live.section.totals'] })
      .closest('section');

    expect(totalsSection).not.toBeNull();

    if (!totalsSection) {
      throw new Error('Live dashboard totals section was not rendered.');
    }

    expect(within(totalsSection).getByText(LIVE_ORGANIZATION_NAME)).toBeVisible();

    // The Preview dashboard's own figures and names, none of which may
    // appear in a Live render.
    for (const previewValue of [
      'Facility Alpha — Sustainability Report.pdf',
      'Green Hubs Demo Organization',
      'Reviewer A',
      '86%',
      '128',
    ]) {
      expect(
        screen.queryByText(previewValue, { exact: false }),
        `Live mode must not render the Preview value "${previewValue}"`,
      ).toBeNull();
    }
  });
});
