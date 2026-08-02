import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { render } from '@testing-library/react';
import { AuthProvider } from '@/features/auth/AuthContext';
import { WorkspaceProvider } from '@/features/organizations/workspace/WorkspaceProvider';
import { LocaleProvider } from '@/lib/i18n/LocaleContext';
import { TooltipProvider, ToastProvider } from '@/design-system';
import type { AuthService, LoginResult } from '@/features/auth/services/AuthService';
import type { Session } from '@/features/auth/types';
import { Role } from '@/features/rbac/roles';
import { DocumentDetailPage } from '../pages/DocumentDetailPage';
import type { DocumentReadResponse, EngagementListResponse } from '@/lib/api/types';
import { ApiError, NotFoundApiError } from '@/lib/api/errors';

const getDocument = vi.fn<() => Promise<DocumentReadResponse>>();
const listEngagements = vi.fn<() => Promise<EngagementListResponse>>();

vi.mock('@/lib/api/endpoints/documents', () => ({
  getDocument: (...args: unknown[]) => getDocument(...(args as [])),
}));

vi.mock('@/lib/api/endpoints/engagements', () => ({
  listEngagements: (...args: unknown[]) => listEngagements(...(args as [])),
}));

vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: async () => ({ items: [{ id: 'org-1', name: 'Al-Riyadh Industrial Group', created_at: null }], page: 1, page_size: 1, total: 1 }),
}));

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

function renderDetail(documentId: string) {
  const service = buildLiveAuthService();
  return render(
    <MemoryRouter initialEntries={[`/documents/${documentId}`]}>
      <LocaleProvider>
        <AuthProvider service={service}>
          <WorkspaceProvider>
            <TooltipProvider>
              <ToastProvider>
                <Routes>
                  <Route path="/documents/:id" element={<DocumentDetailPage />} />
                </Routes>
              </ToastProvider>
            </TooltipProvider>
          </WorkspaceProvider>
        </AuthProvider>
      </LocaleProvider>
    </MemoryRouter>,
  );
}

function buildDocument(overrides: Partial<DocumentReadResponse> = {}): DocumentReadResponse {
  return {
    id: 'doc-live-1',
    engagement_id: 'eng-live-1',
    filename: 'Live Backend Ledger Report.pdf',
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

describe('DocumentDetailPage — live mode', () => {
  beforeEach(() => {
    getDocument.mockReset();
    listEngagements.mockReset();
  });

  it('renders real document metadata from the backend', async () => {
    listEngagements.mockResolvedValue({
      items: [{ id: 'eng-live-1', organization_id: 'org-1', title: 'Live Backend Engagement Alpha', status: 'active', created_at: null }],
      page: 1,
      page_size: 100,
      total: 1,
    });
    getDocument.mockResolvedValue(buildDocument());

    renderDetail('doc-live-1');

    expect(await screen.findByRole('heading', { name: 'Live Backend Ledger Report.pdf' }, { timeout: 5000 })).toBeVisible();
    expect(screen.getAllByText('Live Backend Engagement Alpha').length).toBeGreaterThan(0);
    expect(screen.getByText('Available')).toBeVisible();
    expect(screen.getByText('12')).toBeVisible();
  });

  it('shows a terminal failure state safely, without exposing raw provider errors', async () => {
    listEngagements.mockResolvedValue({ items: [], page: 1, page_size: 100, total: 0 });
    getDocument.mockResolvedValue(buildDocument({ processing_status: 'FAILED', has_extracted_text: false, chunk_count: 0 }));

    renderDetail('doc-live-1');

    await screen.findByRole('heading', { name: 'Live Backend Ledger Report.pdf' }, { timeout: 5000 });
    expect(screen.getAllByText('Failed').length).toBeGreaterThan(0);
    expect(screen.queryByText(/traceback/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/openai/i)).not.toBeInTheDocument();
  });

  it('shows a not-found state for a missing document', async () => {
    listEngagements.mockResolvedValue({ items: [], page: 1, page_size: 100, total: 0 });
    getDocument.mockRejectedValue(new NotFoundApiError('Document not found'));

    renderDetail('doc-missing');

    expect(await screen.findByRole('heading', { name: /this document could not be found/i }, { timeout: 5000 })).toBeVisible();
    expect(screen.getByRole('link', { name: /back to documents/i })).toHaveAttribute('href', '/documents');
  });

  it('shows a retry action on a backend error and recovers on retry', async () => {
    listEngagements.mockResolvedValue({ items: [], page: 1, page_size: 100, total: 0 });
    getDocument.mockRejectedValueOnce(new ApiError(500, 'Something went wrong on our end. Try again.'));
    getDocument.mockResolvedValueOnce(buildDocument());

    renderDetail('doc-live-1');

    expect(await screen.findByRole('heading', { name: /this document could not be loaded/i }, { timeout: 5000 })).toBeVisible();

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /try again/i }));

    expect(await screen.findByRole('heading', { name: 'Live Backend Ledger Report.pdf' }, { timeout: 5000 })).toBeVisible();
  });
});
