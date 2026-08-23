import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/renderWithProviders';
import type { AuthService, LoginResult } from '@/features/auth/services/AuthService';
import type { Session } from '@/features/auth/types';
import { Role } from '@/features/rbac/roles';
import type {
  DocumentListResponse,
  DocumentReadResponse,
  EngagementListResponse,
  ListDocumentsParams,
} from '@/lib/api/types';
import { DocumentsListPage } from '../pages/DocumentsListPage';

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
    items: [{ id: 'org-1', name: 'Demo Organization', created_at: null }],
    page: 1,
    page_size: 1,
    total: 1,
  }),
}));

const PAGE_SIZE = 5;
const ENGAGEMENT = {
  id: 'eng-1',
  organization_id: 'org-1',
  title: 'Live Engagement Alpha',
  status: 'active',
  created_at: null,
};

function buildLiveSession(): Session {
  return {
    kind: 'live',
    user: {
      id: 'user-1',
      name: 'Demo Administrator',
      email: 'demo.administrator@preview.invalid',
      role: Role.Admin,
      orgIds: ['org-1'],
    },
    token: 'supabase-session',
    expiresAt: Date.now() + 60 * 60 * 1000,
    activeOrgId: 'org-1',
  };
}

function buildLiveAuthService(): AuthService {
  return {
    async requestLogin(): Promise<LoginResult> {
      throw new Error('unused');
    },
    async logout(): Promise<void> {},
    getSession: () => null,
    setActiveOrg: () => null,
    restoreSession: async () => buildLiveSession(),
  };
}

function buildDocument(index: number): DocumentReadResponse {
  return {
    id: `doc-live-${index}`,
    engagement_id: ENGAGEMENT.id,
    filename: `Live Backend Report ${index}.pdf`,
    processing_status: 'PROCESSED',
    created_at: '2026-07-12T09:42:00Z',
    updated_at: '2026-07-12T09:58:00Z',
    has_extracted_text: true,
    chunk_count: 12,
    embedding_summary: { total_chunks: 12, processing: 0, completed: 12, failed: 0, is_complete: true },
    latest_analysis_summary: null,
    // Slice 4 evidence fields, at the column default: no decision has
    // been recorded, so there is no reviewer, timestamp or reason.
    evidence_status: 'PENDING_REVIEW',
    reviewed_by: null,
    reviewed_at: null,
    review_reason: null,
    superseded_by_document_id: null,
  };
}

/**
 * Live pagination regression.
 *
 * The list is paginated server-side by `offset`. If the result set shrinks
 * while the user is on a later page — a document removed, or processing
 * moving rows out of the active status filter — the stored page number now
 * points past the end, and the user is shown an empty page even though
 * earlier pages still have rows. That is the defect this covers.
 */
describe('DocumentsListPage — live pagination', () => {
  beforeEach(() => {
    listDocuments.mockReset();
    listEngagements.mockReset();
    listEngagements.mockResolvedValue({ items: [ENGAGEMENT], page: 1, page_size: 100, total: 1 });
    Object.defineProperty(window, 'innerWidth', { value: 1440, configurable: true });
    window.dispatchEvent(new Event('resize'));
  });

  it('recovers to the last valid page when the result set shrinks under the user', async () => {
    const user = userEvent.setup();

    // 12 documents across 3 pages; the moment the user asks for page 3, the
    // backend reports only 6 remain — the offset the request carried is now
    // past the end.
    let total = 12;
    listDocuments.mockImplementation(async (params) => {
      const offset = params.offset ?? 0;
      if (offset > 0) total = 6;
      const items =
        offset >= total
          ? []
          : Array.from({ length: Math.min(PAGE_SIZE, total - offset) }, (_unused, index) =>
              buildDocument(offset + index + 1),
            );
      return { items, total, limit: PAGE_SIZE, offset };
    });

    renderWithProviders(<DocumentsListPage />, { authService: buildLiveAuthService() });

    expect(await screen.findByText('Live Backend Report 1.pdf', {})).toBeVisible();

    await user.click(screen.getByRole('button', { name: '3' }));

    // Without the clamp the user is stranded here on an empty page 3.
    await waitFor(
      () => {
        expect(screen.getByText('Live Backend Report 6.pdf')).toBeVisible();
      },
    );

    const lastOffset = listDocuments.mock.calls.at(-1)![0].offset ?? 0;
    expect(lastOffset).toBeLessThan(total);
  });

  it('resets to the first page when a filter changes', async () => {
    const user = userEvent.setup();

    listDocuments.mockImplementation(async (params) => {
      const offset = params.offset ?? 0;
      return {
        items: Array.from({ length: PAGE_SIZE }, (_unused, index) =>
          buildDocument(offset + index + 1),
        ),
        total: 12,
        limit: PAGE_SIZE,
        offset,
      };
    });

    renderWithProviders(<DocumentsListPage />, { authService: buildLiveAuthService() });
    expect(await screen.findByText('Live Backend Report 1.pdf', {})).toBeVisible();

    await user.click(screen.getByRole('button', { name: '3' }));
    expect(await screen.findByText('Live Backend Report 11.pdf', {})).toBeVisible();

    await user.click(screen.getByRole('tab', { name: /^processed$/i }));

    await waitFor(
      () => {
        expect(listDocuments.mock.calls.at(-1)![0].offset).toBe(0);
      },
    );
  });

  it('does not loop or duplicate requests once the page settles', async () => {
    listDocuments.mockImplementation(async (params) => {
      const offset = params.offset ?? 0;
      return {
        items: [buildDocument(offset + 1)],
        total: 1,
        limit: PAGE_SIZE,
        offset,
      };
    });

    renderWithProviders(<DocumentsListPage />, { authService: buildLiveAuthService() });
    expect(await screen.findByText('Live Backend Report 1.pdf', {})).toBeVisible();

    const callsAfterSettle = listDocuments.mock.calls.length;
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(listDocuments.mock.calls.length).toBe(callsAfterSettle);
  });
});
