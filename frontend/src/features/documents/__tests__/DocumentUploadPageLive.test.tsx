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
import { DocumentUploadPage } from '../pages/DocumentUploadPage';
import type { DocumentResponse, EngagementListResponse } from '@/lib/api/types';
import { ValidationApiError } from '@/lib/api/errors';

const uploadDocument = vi.fn<() => Promise<DocumentResponse>>();
const listEngagements = vi.fn<() => Promise<EngagementListResponse>>();

vi.mock('@/lib/api/endpoints/documents', () => ({
  uploadDocument: (...args: unknown[]) => uploadDocument(...(args as [])),
}));

vi.mock('@/lib/api/endpoints/engagements', () => ({
  listEngagements: (...args: unknown[]) => listEngagements(...(args as [])),
}));

vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: async () => ({ items: [{ id: 'org-1', name: 'Al-Riyadh Industrial Group', created_at: null }], page: 1, page_size: 1, total: 1 }),
}));

const navigateSpy = vi.fn<(path: string) => void>();
vi.mock('react-router', async () => {
  const actual = await vi.importActual<typeof import('react-router')>('react-router');
  return { ...actual, useNavigate: () => navigateSpy };
});

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

function renderUpload() {
  return render(
    <MemoryRouter initialEntries={['/documents/upload']}>
      <LocaleProvider>
        <AuthProvider service={buildLiveAuthService()}>
          <WorkspaceProvider>
            <TooltipProvider>
              <ToastProvider>
                <Routes>
                  <Route path="/documents/upload" element={<DocumentUploadPage />} />
                </Routes>
              </ToastProvider>
            </TooltipProvider>
          </WorkspaceProvider>
        </AuthProvider>
      </LocaleProvider>
    </MemoryRouter>,
  );
}

function pdfFile(name = 'report.pdf') {
  return new File(['%PDF-1.7 sample'], name, { type: 'application/pdf' });
}

const SINGLE_ENGAGEMENT = { id: 'eng-1', organization_id: 'org-1', title: 'Live Backend Engagement Alpha', status: 'active', created_at: null };
const SECOND_ENGAGEMENT = { id: 'eng-2', organization_id: 'org-1', title: 'Live Backend Engagement Beta', status: 'active', created_at: null };

describe('DocumentUploadPage — live mode', () => {
  beforeEach(() => {
    uploadDocument.mockReset();
    listEngagements.mockReset();
    navigateSpy.mockReset();
  });

  it('auto-selects a single engagement and uploads a valid PDF, navigating to the returned document', async () => {
    listEngagements.mockResolvedValue({ items: [SINGLE_ENGAGEMENT], page: 1, page_size: 100, total: 1 });
    uploadDocument.mockResolvedValue({
      id: 'doc-new-1',
      engagement_id: SINGLE_ENGAGEMENT.id,
      filename: 'report.pdf',
      processing_status: 'PENDING',
      created_at: '2026-07-15T10:00:00Z',
      updated_at: '2026-07-15T10:00:00Z',
    });

    renderUpload();
    const user = userEvent.setup();

    expect(await screen.findByText(/uploading to live backend engagement alpha/i, {})).toBeVisible();

    const input = screen.getByLabelText(/select a pdf document/i);
    await user.upload(input, pdfFile());
    expect(await screen.findByText('VALIDATED')).toBeVisible();

    await user.click(screen.getByRole('button', { name: /upload document/i }));

    expect(uploadDocument).toHaveBeenCalledWith(
      expect.objectContaining({ engagementId: SINGLE_ENGAGEMENT.id }),
    );
    expect(navigateSpy).toHaveBeenCalledWith('/documents/doc-new-1');
  });

  it('rejects a non-PDF file locally without calling the backend', async () => {
    listEngagements.mockResolvedValue({ items: [SINGLE_ENGAGEMENT], page: 1, page_size: 100, total: 1 });
    renderUpload();
    const user = userEvent.setup();
    await screen.findByText(/uploading to live backend engagement alpha/i, {});

    const input = screen.getByLabelText(/select a pdf document/i);
    // Named with a `.pdf` extension (so @testing-library/user-event's own
    // `accept`-attribute filtering lets it through) but declares the wrong
    // MIME type — this is what actually exercises the app's own stricter
    // client-side check (type AND extension), not userEvent's filter.
    const wrongTypeFile = new File(['not a pdf'], 'notes.pdf', { type: 'text/plain' });
    await user.upload(input, wrongTypeFile);

    expect(await screen.findByText(/choose a pdf file/i)).toBeVisible();
    expect(uploadDocument).not.toHaveBeenCalled();
  });

  it('requires an explicit engagement choice when there is more than one, never silently picking the first', async () => {
    listEngagements.mockResolvedValue({ items: [SINGLE_ENGAGEMENT, SECOND_ENGAGEMENT], page: 1, page_size: 100, total: 2 });
    renderUpload();
    const user = userEvent.setup();

    const select = await screen.findByLabelText(/^engagement$/i, {});
    expect(select).toHaveValue('');

    const input = screen.getByLabelText(/select a pdf document/i);
    await user.upload(input, pdfFile());
    await screen.findByText('VALIDATED');

    expect(screen.getByRole('button', { name: /upload document/i })).toBeDisabled();

    await user.selectOptions(select, SECOND_ENGAGEMENT.id);
    expect(screen.getByRole('button', { name: /upload document/i })).toBeEnabled();
  });

  it('disables upload and explains why when the workspace has zero engagements', async () => {
    listEngagements.mockResolvedValue({ items: [], page: 1, page_size: 100, total: 0 });
    renderUpload();

    expect(await screen.findByRole('heading', { name: /no engagements yet/i })).toBeVisible();
    expect(screen.queryByLabelText(/select a pdf document/i)).not.toBeInTheDocument();
  });

  it('prevents duplicate submissions while an upload is in flight', async () => {
    listEngagements.mockResolvedValue({ items: [SINGLE_ENGAGEMENT], page: 1, page_size: 100, total: 1 });
    let resolveUpload: (value: DocumentResponse) => void = () => {};
    uploadDocument.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveUpload = resolve;
        }),
    );

    renderUpload();
    const user = userEvent.setup();
    await screen.findByText(/uploading to live backend engagement alpha/i, {});

    const input = screen.getByLabelText(/select a pdf document/i);
    await user.upload(input, pdfFile());
    await screen.findByText('VALIDATED');

    const submitButton = screen.getByRole('button', { name: /upload document|uploading/i });
    await user.click(submitButton);
    await user.click(submitButton);

    expect(uploadDocument).toHaveBeenCalledTimes(1);
    resolveUpload({
      id: 'doc-new-1',
      engagement_id: SINGLE_ENGAGEMENT.id,
      filename: 'report.pdf',
      processing_status: 'PENDING',
      created_at: '2026-07-15T10:00:00Z',
      updated_at: '2026-07-15T10:00:00Z',
    });
  });

  it('preserves the selected file and shows the backend message on a recoverable validation failure', async () => {
    listEngagements.mockResolvedValue({ items: [SINGLE_ENGAGEMENT], page: 1, page_size: 100, total: 1 });
    uploadDocument.mockRejectedValue(new ValidationApiError('file content does not match the PDF format'));

    renderUpload();
    const user = userEvent.setup();
    await screen.findByText(/uploading to live backend engagement alpha/i, {});

    const input = screen.getByLabelText(/select a pdf document/i);
    await user.upload(input, pdfFile());
    await screen.findByText('VALIDATED');

    await user.click(screen.getByRole('button', { name: /upload document/i }));

    expect(await screen.findByText(/file content does not match the pdf format/i)).toBeVisible();
    // The file selection is preserved, not cleared, on a recoverable failure.
    expect(screen.getByText('report.pdf')).toBeVisible();
    expect(navigateSpy).not.toHaveBeenCalled();
  });
});
