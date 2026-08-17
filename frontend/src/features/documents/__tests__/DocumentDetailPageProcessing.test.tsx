import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { AuthProvider } from '@/features/auth/AuthContext';
import { WorkspaceProvider } from '@/features/organizations/workspace/WorkspaceProvider';
import { LocaleProvider } from '@/lib/i18n/LocaleContext';
import { TooltipProvider, ToastProvider } from '@/design-system';
import type { AuthService, LoginResult } from '@/features/auth/services/AuthService';
import type { Session } from '@/features/auth/types';
import { Role } from '@/features/rbac/roles';
import { DocumentDetailPage } from '../pages/DocumentDetailPage';
import type { DocumentReadResponse, DocumentResponse, EngagementListResponse } from '@/lib/api/types';
import { ApiError } from '@/lib/api/errors';

const getDocument = vi.fn<() => Promise<DocumentReadResponse>>();
const processDocument = vi.fn<() => Promise<DocumentResponse>>();
const listEngagements = vi.fn<() => Promise<EngagementListResponse>>();

vi.mock('@/lib/api/endpoints/documents', () => ({
  getDocument: (...args: unknown[]) => getDocument(...(args as [])),
  processDocument: (...args: unknown[]) => processDocument(...(args as [])),
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
    async logout(): Promise<void> {},
    getSession: () => null,
    setActiveOrg: () => null,
    restoreSession: async () => buildLiveSession(),
  };
}

function renderDetail(documentId: string) {
  return render(
    <MemoryRouter initialEntries={[`/documents/${documentId}`]}>
      <LocaleProvider>
        <AuthProvider service={buildLiveAuthService()}>
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
    processing_status: 'PENDING',
    created_at: '2026-07-12T09:42:00Z',
    updated_at: '2026-07-12T09:58:00Z',
    has_extracted_text: false,
    chunk_count: 0,
    embedding_summary: { total_chunks: 0, processing: 0, completed: 0, failed: 0, is_complete: false },
    latest_analysis_summary: null,
    ...overrides,
  };
}

describe('DocumentDetailPage — processing (live mode)', () => {
  beforeEach(() => {
    getDocument.mockReset();
    processDocument.mockReset();
    listEngagements.mockReset();
    listEngagements.mockResolvedValue({ items: [], page: 1, page_size: 100, total: 0 });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('triggers processing exactly once and reflects the terminal PROCESSED state', async () => {
    getDocument.mockResolvedValueOnce(buildDocument({ processing_status: 'PENDING' }));
    processDocument.mockResolvedValue({
      id: 'doc-live-1',
      engagement_id: 'eng-live-1',
      filename: 'Live Backend Ledger Report.pdf',
      processing_status: 'PROCESSED',
      created_at: '2026-07-12T09:42:00Z',
      updated_at: '2026-07-12T10:00:00Z',
    });
    getDocument.mockResolvedValueOnce(
      buildDocument({ processing_status: 'PROCESSED', has_extracted_text: true, chunk_count: 4 }),
    );

    renderDetail('doc-live-1');
    const user = userEvent.setup();

    const processButton = await screen.findByRole('button', { name: /process document/i });
    await user.click(processButton);

    expect(processDocument).toHaveBeenCalledTimes(1);
    expect(processDocument).toHaveBeenCalledWith('doc-live-1');

    // Status renders in more than one place at once (header badge, timeline
    // card badge, hero metric, timeline step label) by design — same as the
    // demo page — so this asserts on "at least one", not a single match.
    await waitFor(() => expect(screen.getAllByText('Processed').length).toBeGreaterThan(0));
    expect(screen.queryByRole('button', { name: /process document/i })).not.toBeInTheDocument();
    expect(getDocument).toHaveBeenCalledTimes(2);
  });

  it('shows a safe terminal failure message and does not offer to process again', async () => {
    getDocument.mockResolvedValueOnce(buildDocument({ processing_status: 'PENDING' }));
    processDocument.mockRejectedValue(new ApiError(422, 'Extracted text is empty'));
    getDocument.mockResolvedValueOnce(buildDocument({ processing_status: 'FAILED' }));

    renderDetail('doc-live-1');
    const user = userEvent.setup();

    const processButton = await screen.findByRole('button', { name: /process document/i });
    await user.click(processButton);

    expect(await screen.findByText('Extracted text is empty', {})).toBeVisible();
    expect(await screen.findAllByText('Failed', {})).not.toHaveLength(0);
    expect(screen.queryByRole('button', { name: /process document/i })).not.toBeInTheDocument();
  });

  it('does not show a process action while already processing or once terminal', async () => {
    // A persistent (not "once") resolved value: this test only asserts on
    // the initial render, but the document is PROCESSING, which starts a
    // real polling timer — a persistent mock keeps any stray tick from
    // exhausting the mock queue and crashing after this test's own
    // assertions have already finished.
    getDocument.mockResolvedValue(buildDocument({ processing_status: 'PROCESSING' }));
    const view = renderDetail('doc-live-1');

    await waitFor(() => expect(screen.getAllByText('Processing').length).toBeGreaterThan(0));
    expect(screen.queryByRole('button', { name: /^process document$/i })).not.toBeInTheDocument();
    view.unmount();
  });

  it(
    'polls a document observed as PROCESSING and stops once it reaches a terminal state',
    async () => {
      // Real timers here, not fake ones: the polling hook's 2s interval is
      // a real `setTimeout`, and driving it with `vi.useFakeTimers()`
      // fights React's own scheduler in this environment. A bounded real
      // wait is a small, one-time cost for a deterministic assertion.
      getDocument.mockResolvedValueOnce(buildDocument({ processing_status: 'PROCESSING' }));
      getDocument.mockResolvedValueOnce(buildDocument({ processing_status: 'PROCESSING' }));
      getDocument.mockResolvedValueOnce(
        buildDocument({ processing_status: 'PROCESSED', has_extracted_text: true, chunk_count: 3 }),
      );

      renderDetail('doc-live-1');

      await waitFor(() => expect(getDocument).toHaveBeenCalledTimes(1));
      await waitFor(() => expect(getDocument).toHaveBeenCalledTimes(2));
      await waitFor(() => expect(getDocument).toHaveBeenCalledTimes(3));
      await waitFor(() => expect(screen.getAllByText('Processed').length).toBeGreaterThan(0));

      // Polling has stopped at the terminal state — wait past another full
      // interval and confirm no further request was issued.
      await new Promise((resolve) => setTimeout(resolve, 2500));
      expect(getDocument).toHaveBeenCalledTimes(3);
    },
    15_000,
  );
});
