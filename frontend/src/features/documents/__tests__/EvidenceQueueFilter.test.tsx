import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/renderWithProviders';
import { buildLiveAuthService } from '@/test/liveSession';
import { Role } from '@/features/rbac/roles';
import { en } from '@/lib/i18n/strings/en';
import type {
  DocumentListResponse,
  DocumentReadResponse,
  EngagementListResponse,
  ListDocumentsParams,
} from '@/lib/api/types';
import { DocumentsListPage } from '../pages/DocumentsListPage';

/**
 * The evidence work queue on the Documents list.
 *
 * The one property that matters beyond "the filter works": the count and
 * the rows must describe the same set. The backend applies
 * `evidence_status` inside the same tenant-scoped query that produces
 * `total`, so this page must forward the filter and then display the
 * server's `total` — never `items.length`.
 *
 * The fixture below makes `total` deliberately far larger than the page it
 * returns, so a page that counted rows would render a visibly wrong
 * number rather than coincidentally passing.
 */

const listDocuments = vi.fn<(params: ListDocumentsParams) => Promise<DocumentListResponse>>();
const listEngagements = vi.fn<() => Promise<EngagementListResponse>>();

vi.mock('@/lib/api/endpoints/documents', () => ({
  listDocuments: (...args: unknown[]) => listDocuments(...(args as [ListDocumentsParams])),
}));

vi.mock('@/lib/api/endpoints/engagements', () => ({
  listEngagements: (...args: unknown[]) => listEngagements(...(args as [])),
}));

vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: async () => ({
    items: [{ id: 'org-live-1', name: 'Authenticated Live Organization', created_at: null }],
    page: 1,
    page_size: 1,
    total: 1,
  }),
}));

const ENGAGEMENT_ID = 'eng-live-1';

/** A real server total, far larger than any page this fixture returns. */
const PENDING_TOTAL = 417;

function buildDocument(index: number): DocumentReadResponse {
  return {
    id: `doc-live-${index}`,
    engagement_id: ENGAGEMENT_ID,
    filename: `Live Ledger ${index}.pdf`,
    processing_status: 'PROCESSED',
    created_at: '2026-07-12T09:42:00Z',
    updated_at: '2026-07-12T09:58:00Z',
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
    evidence_status: 'PENDING_REVIEW',
    reviewed_by: null,
    reviewed_at: null,
    review_reason: null,
    superseded_by_document_id: null,
  };
}

beforeEach(() => {
  listDocuments.mockReset();
  listEngagements.mockReset();

  listDocuments.mockResolvedValue({
    // Two rows back, a large total beside them — the shape that catches a
    // count derived from the page.
    items: [buildDocument(1), buildDocument(2)],
    total: PENDING_TOTAL,
    limit: 5,
    offset: 0,
  });
  listEngagements.mockResolvedValue({
    items: [
      {
        id: ENGAGEMENT_ID,
        organization_id: 'org-live-1',
        title: 'Live Engagement',
        status: 'ACTIVE',
        created_at: null,
      },
    ],
    page: 1,
    page_size: 20,
    total: 1,
  });
});

function renderList(role: Role = Role.Approver) {
  return renderWithProviders(<DocumentsListPage />, { authService: buildLiveAuthService(role) });
}

describe('Evidence review queue', () => {
  it('issues no evidence filter until one is chosen', async () => {
    renderList();
    await waitFor(() => expect(listDocuments).toHaveBeenCalled());

    expect(listDocuments.mock.calls[0]?.[0].evidence_status).toBeUndefined();
  });

  it('forwards the chosen evidence status to the server', async () => {
    const user = userEvent.setup();
    renderList();
    await waitFor(() => expect(listDocuments).toHaveBeenCalled());

    await user.selectOptions(
      screen.getByLabelText(en['evidence.filter.label']),
      'PENDING_REVIEW',
    );

    await waitFor(() => {
      const latest = listDocuments.mock.calls.at(-1);
      expect(latest?.[0].evidence_status).toBe('PENDING_REVIEW');
    });
  });

  it('offers every evidence state, plus an explicit no-filter option', async () => {
    renderList();
    await waitFor(() => expect(listDocuments).toHaveBeenCalled());

    const filter = screen.getByLabelText(en['evidence.filter.label']);
    for (const label of [
      en['evidence.filter.all'],
      en['evidence.status.PENDING_REVIEW'],
      en['evidence.status.VERIFIED'],
      en['evidence.status.REJECTED'],
      en['evidence.status.RESTRICTED'],
      en['evidence.status.SUPERSEDED'],
    ]) {
      expect(within(filter).getByRole('option', { name: label })).toBeInTheDocument();
    }
  });

  it('reports the server total for the filtered set, never the page length', async () => {
    const user = userEvent.setup();
    renderList();
    await waitFor(() => expect(listDocuments).toHaveBeenCalled());

    await user.selectOptions(
      screen.getByLabelText(en['evidence.filter.label']),
      'PENDING_REVIEW',
    );

    // The page returned two rows; the truthful count is the server's.
    await waitFor(() =>
      expect(screen.getByText(new RegExp(String(PENDING_TOTAL)))).toBeVisible(),
    );
    expect(screen.queryByText(/showing 1 to 2 of 2/i)).toBeNull();
  });

  it('sends no organization identifier with the filtered query', async () => {
    const user = userEvent.setup();
    renderList();
    await waitFor(() => expect(listDocuments).toHaveBeenCalled());

    await user.selectOptions(screen.getByLabelText(en['evidence.filter.label']), 'VERIFIED');

    await waitFor(() => {
      const latest = listDocuments.mock.calls.at(-1)?.[0];
      expect(latest?.evidence_status).toBe('VERIFIED');
    });

    for (const call of listDocuments.mock.calls) {
      const keys = Object.keys(call[0]);
      for (const key of keys) {
        expect(key).not.toMatch(/organization|tenant|org_id/i);
      }
    }
  });

  it('resets to the first page when the evidence filter changes', async () => {
    const user = userEvent.setup();
    renderList();
    await waitFor(() => expect(listDocuments).toHaveBeenCalled());

    await user.selectOptions(screen.getByLabelText(en['evidence.filter.label']), 'REJECTED');

    await waitFor(() => {
      const latest = listDocuments.mock.calls.at(-1)?.[0];
      expect(latest?.evidence_status).toBe('REJECTED');
      expect(latest?.offset).toBe(0);
    });
  });

  it.each([Role.Viewer, Role.Editor])(
    'still offers the read-only queue filter to %s',
    async (role) => {
      // Filtering a list is a read, and every role may read documents.
      // Denying the filter would hide information a viewer is entitled to.
      renderList(role);
      await waitFor(() => expect(listDocuments).toHaveBeenCalled());

      expect(screen.getByLabelText(en['evidence.filter.label'])).toBeEnabled();
    },
  );
});