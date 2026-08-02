import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/renderWithProviders';
import type { AuthService, LoginResult } from '@/features/auth/services/AuthService';
import type { Session } from '@/features/auth/types';
import { Role } from '@/features/rbac/roles';
import { DocumentsListPage } from '../pages/DocumentsListPage';
import type { DocumentListResponse, EngagementListResponse } from '@/lib/api/types';
import { ApiError } from '@/lib/api/errors';

const listDocuments = vi.fn<() => Promise<DocumentListResponse>>();
const listEngagements = vi.fn<() => Promise<EngagementListResponse>>();

vi.mock('@/lib/api/endpoints/documents', () => ({
  listDocuments: (...args: unknown[]) => listDocuments(...(args as [])),
}));

vi.mock('@/lib/api/endpoints/engagements', () => ({
  listEngagements: (...args: unknown[]) => listEngagements(...(args as [])),
}));

vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: async () => ({ items: [{ id: 'org-1', name: 'Al-Riyadh Industrial Group', created_at: null }], page: 1, page_size: 1, total: 1 }),
}));

// Deliberately distinct from every `MOCK_DOCUMENTS`/demo-org fixture name
// (see mockDocuments.ts) — the demo path renders synchronously before the
// live auth bootstrap resolves, so any overlapping text would let a test
// query match the transient demo render instead of the real live one.
const LIVE_ENGAGEMENT_TITLE = 'Live Backend Engagement Alpha';
const LIVE_FILENAME = 'Live Backend Ledger Report.pdf';
const LIVE_ENGAGEMENT = { id: 'eng-live-1', organization_id: 'org-1', title: LIVE_ENGAGEMENT_TITLE, status: 'active', created_at: null };

function buildLiveSession(): Session {
  return {
    kind: 'live',
    user: { id: 'user-1', name: 'Reem Al-Harbi', email: 'reem@example.com', role: Role.Admin, orgIds: ['org-1'] },
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
    async verifyOtp(): Promise<Session> {
      throw new Error('unused');
    },
    async resendOtp(): Promise<void> {},
    async logout(): Promise<void> {},
    getSession: () => null,
    setActiveOrg: () => null,
    restoreSession: async () => buildLiveSession(),
  };
}

function buildDocument(overrides: Partial<DocumentListResponse['items'][number]> = {}) {
  return {
    id: 'doc-live-1',
    engagement_id: LIVE_ENGAGEMENT.id,
    filename: LIVE_FILENAME,
    processing_status: 'PROCESSED',
    created_at: '2026-07-12T09:42:00Z',
    updated_at: '2026-07-12T09:58:00Z',
    has_extracted_text: true,
    chunk_count: 12,
    embedding_summary: { total_chunks: 12, processing: 0, completed: 12, failed: 0, is_complete: true },
    latest_analysis_summary: null,
    ...overrides,
  };
}

describe('DocumentsListPage — live mode', () => {
  beforeEach(() => {
    listDocuments.mockReset();
    listEngagements.mockReset();
  });

  it('renders real documents from the backend, not mock rows', async () => {
    listEngagements.mockResolvedValue({ items: [LIVE_ENGAGEMENT], page: 1, page_size: 100, total: 1 });
    listDocuments.mockResolvedValue({ items: [buildDocument()], total: 1, limit: 5, offset: 0 });

    renderWithProviders(<DocumentsListPage />, { authService: buildLiveAuthService() });

    expect(await screen.findByRole('link', { name: new RegExp(LIVE_FILENAME, 'i') }, { timeout: 5000 })).toBeVisible();
    expect(screen.queryByText(/sample data/i)).not.toBeInTheDocument();
    expect(screen.queryByText('Scope 1 Emissions Ledger.pdf')).not.toBeInTheDocument();
    expect(screen.getAllByText(LIVE_ENGAGEMENT_TITLE).length).toBeGreaterThan(0);
  });

  it('uses backend pagination (limit/offset), not client-side slicing', async () => {
    listEngagements.mockResolvedValue({ items: [], page: 1, page_size: 100, total: 0 });
    listDocuments.mockResolvedValue({ items: [buildDocument()], total: 42, limit: 5, offset: 0 });

    renderWithProviders(<DocumentsListPage />, { authService: buildLiveAuthService() });

    await screen.findByRole('link', { name: new RegExp(LIVE_FILENAME, 'i') }, { timeout: 5000 });
    expect(screen.getByText('Showing 1–5 of 42')).toBeInTheDocument();

    const user = userEvent.setup();
    listDocuments.mockResolvedValue({
      items: [buildDocument({ id: 'doc-live-2', filename: 'Live Backend Page Two.pdf' })],
      total: 42,
      limit: 5,
      offset: 5,
    });
    await user.click(await screen.findByRole('button', { name: '2' }));

    await screen.findByRole('link', { name: /live backend page two/i }, { timeout: 5000 });
    expect(listDocuments).toHaveBeenLastCalledWith(
      expect.objectContaining({ limit: 5, offset: 5 }),
      expect.anything(),
    );
  });

  it('filters by processing status and engagement using backend query parameters', async () => {
    listEngagements.mockResolvedValue({ items: [LIVE_ENGAGEMENT], page: 1, page_size: 100, total: 1 });
    listDocuments.mockResolvedValue({ items: [buildDocument()], total: 1, limit: 5, offset: 0 });

    renderWithProviders(<DocumentsListPage />, { authService: buildLiveAuthService() });
    await screen.findByRole('link', { name: new RegExp(LIVE_FILENAME, 'i') }, { timeout: 5000 });

    const user = userEvent.setup();
    await user.click(await screen.findByRole('tab', { name: 'Failed' }));
    await waitFor(() =>
      expect(listDocuments).toHaveBeenLastCalledWith(
        expect.objectContaining({ processing_status: 'FAILED' }),
        expect.anything(),
      ),
    );

    await user.click(await screen.findByRole('tab', { name: 'All' }));
    await user.selectOptions(await screen.findByLabelText(/filter by engagement/i), LIVE_ENGAGEMENT.id);
    await waitFor(() =>
      expect(listDocuments).toHaveBeenLastCalledWith(
        expect.objectContaining({ engagement_id: LIVE_ENGAGEMENT.id }),
        expect.anything(),
      ),
    );
  });

  it('shows an empty state when there are no documents', async () => {
    listEngagements.mockResolvedValue({ items: [LIVE_ENGAGEMENT], page: 1, page_size: 100, total: 1 });
    listDocuments.mockResolvedValue({ items: [], total: 0, limit: 5, offset: 0 });

    renderWithProviders(<DocumentsListPage />, { authService: buildLiveAuthService() });

    expect(await screen.findByRole('heading', { name: /no documents yet/i }, { timeout: 5000 })).toBeVisible();
  });

  it('shows a distinct empty state when the workspace has zero engagements', async () => {
    listEngagements.mockResolvedValue({ items: [], page: 1, page_size: 100, total: 0 });
    listDocuments.mockResolvedValue({ items: [], total: 0, limit: 5, offset: 0 });

    renderWithProviders(<DocumentsListPage />, { authService: buildLiveAuthService() });

    expect(await screen.findByRole('heading', { name: /no engagements yet/i }, { timeout: 5000 })).toBeVisible();
  });

  it('shows a retry action on a backend error and recovers on retry', async () => {
    listEngagements.mockResolvedValue({ items: [], page: 1, page_size: 100, total: 0 });
    listDocuments.mockRejectedValueOnce(new ApiError(500, 'Something went wrong on our end. Try again.'));
    listDocuments.mockResolvedValueOnce({ items: [buildDocument()], total: 1, limit: 5, offset: 0 });

    renderWithProviders(<DocumentsListPage />, { authService: buildLiveAuthService() });

    expect(await screen.findByRole('heading', { name: /documents could not be loaded/i }, { timeout: 5000 })).toBeVisible();
    expect(screen.getByText(/something went wrong on our end/i)).toBeVisible();

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /try again/i }));

    expect(await screen.findByRole('link', { name: new RegExp(LIVE_FILENAME, 'i') }, { timeout: 5000 })).toBeVisible();
  });
});
