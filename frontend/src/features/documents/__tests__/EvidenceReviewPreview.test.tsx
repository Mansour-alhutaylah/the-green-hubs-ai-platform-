import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { AuthProvider } from '@/features/auth/AuthContext';
import { WorkspaceProvider } from '@/features/organizations/workspace/WorkspaceProvider';
import { LocaleProvider } from '@/lib/i18n/LocaleContext';
import { TooltipProvider, ToastProvider } from '@/design-system';
import { buildTestSession } from '@/test/renderWithProviders';
import type { AuthService, LoginResult } from '@/features/auth/services/AuthService';
import type { Session } from '@/features/auth/types';
import { Role } from '@/features/rbac/roles';
import { en } from '@/lib/i18n/strings/en';
import { MOCK_DOCUMENTS } from '../mockDocuments';
import { DocumentDetailPage } from '../pages/DocumentDetailPage';

/**
 * Preview must stay a self-contained demonstration.
 *
 * The property under test is not "the buttons are hidden" — it is that
 * Preview has no path to a backend at all, and makes no claim that a
 * decision was recorded. A Preview that rendered a working-looking Verify
 * control would be teaching the opposite of what this journey exists to
 * demonstrate: that an evidence decision is durable and attributable.
 *
 * `fetch` is replaced with a spy that fails loudly rather than merely
 * counted, so a request does not quietly resolve to `undefined` and let an
 * assertion pass for the wrong reason.
 */

const fetchSpy = vi.fn<() => never>(() => {
  throw new Error('Preview must never issue a network request.');
});

/** Every real API endpoint module, mocked to throw. Preview importing any
 * of these would be the exact Live/Preview mixing this test forbids. */
function forbidden(name: string) {
  return (...args: unknown[]) => {
    void args;
    throw new Error(`Preview must never call ${name}.`);
  };
}

vi.mock('@/lib/api/endpoints/documents', () => ({
  getDocument: forbidden('getDocument'),
  listDocuments: forbidden('listDocuments'),
  processDocument: forbidden('processDocument'),
  generateEmbeddings: forbidden('generateEmbeddings'),
  verifyDocumentEvidence: forbidden('verifyDocumentEvidence'),
  rejectDocumentEvidence: forbidden('rejectDocumentEvidence'),
  restrictDocumentEvidence: forbidden('restrictDocumentEvidence'),
  supersedeDocumentEvidence: forbidden('supersedeDocumentEvidence'),
}));

vi.mock('@/lib/api/endpoints/engagements', () => ({
  listEngagements: forbidden('listEngagements'),
}));

vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: forbidden('listOrganizations'),
}));

vi.mock('@/lib/api/endpoints/analysis', () => ({
  analyzeDocument: forbidden('analyzeDocument'),
}));

/** The fixture list is non-empty by construction; this makes that a typed
 * fact rather than an assumption the test would trip over later. */
function firstPreviewDocument() {
  const document = MOCK_DOCUMENTS[0];
  if (!document) throw new Error('Preview fixtures are empty.');
  return document;
}

const PREVIEW_DOCUMENT = firstPreviewDocument();

function buildPreviewAuthService(session: Session): AuthService {
  return {
    async requestLogin(): Promise<LoginResult> {
      throw new Error('unused in this test');
    },
    async logout(): Promise<void> {},
    getSession: () => session,
    setActiveOrg: () => session,
  };
}

function renderPreviewDetail(role: Role = Role.Owner) {
  const session = buildTestSession({
    id: 'preview-user',
    name: 'Preview User',
    email: 'preview@example.test',
    role,
    orgIds: ['preview-org'],
  });
  // A `kind: 'preview'` session — the only kind a Preview build produces.
  expect(session.kind).toBe('preview');

  return render(
    <MemoryRouter initialEntries={[`/documents/${PREVIEW_DOCUMENT.id}`]}>
      <LocaleProvider>
        <AuthProvider service={buildPreviewAuthService(session)}>
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

beforeEach(() => {
  fetchSpy.mockClear();
  vi.stubGlobal('fetch', fetchSpy);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('Evidence review in Preview', () => {
  it('explains truthfully that evidence review requires a live workspace', async () => {
    renderPreviewDetail();

    expect(await screen.findByText(en['evidence.preview.title'])).toBeVisible();
    expect(screen.getByText(en['evidence.preview.description'])).toBeVisible();
  });

  it('renders no evidence decision control of any kind', async () => {
    renderPreviewDetail();
    await screen.findByText(en['evidence.preview.title']);

    for (const label of [
      en['evidence.action.verify'],
      en['evidence.action.reject'],
      en['evidence.action.restrict'],
      en['evidence.action.supersede'],
      en['evidence.confirm.submit'],
    ]) {
      expect(screen.queryByRole('button', { name: new RegExp(label) })).toBeNull();
    }
  });

  it('makes no network request at all', async () => {
    renderPreviewDetail();
    await screen.findByText(en['evidence.preview.title']);

    // The endpoint mocks throw, and `fetch` throws; a passing assertion
    // here means neither was reached.
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('claims no recorded decision, reviewer, timestamp or evidence status', async () => {
    renderPreviewDetail();
    await screen.findByText(en['evidence.preview.title']);

    for (const claim of [
      en['evidence.status.VERIFIED'],
      en['evidence.status.REJECTED'],
      en['evidence.status.RESTRICTED'],
      en['evidence.status.SUPERSEDED'],
      en['evidence.provenance.reviewedBy'],
      en['evidence.provenance.reviewedAt'],
      en['evidence.retrieval.eligible'],
    ]) {
      expect(
        screen.queryByText(claim, { exact: false }),
        `Preview must not claim "${claim}"`,
      ).toBeNull();
    }
  });

  it('offers no evidence decision even to the highest tier', async () => {
    // Preview isolation is not a permission question: an Owner in Preview
    // still has no backend to record a decision against.
    renderPreviewDetail(Role.Owner);
    await screen.findByText(en['evidence.preview.title']);

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('cannot be driven into a decision dialog by the keyboard', async () => {
    const user = userEvent.setup();
    renderPreviewDetail();
    await screen.findByText(en['evidence.preview.title']);

    await user.tab();
    await user.tab();
    await user.keyboard('{Enter}');

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});