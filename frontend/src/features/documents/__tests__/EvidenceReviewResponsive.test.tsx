import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { AuthProvider } from '@/features/auth/AuthContext';
import { WorkspaceProvider } from '@/features/organizations/workspace/WorkspaceProvider';
import { LocaleProvider } from '@/lib/i18n/LocaleContext';
import { TooltipProvider, ToastProvider } from '@/design-system';
import type { AuthService, LoginResult } from '@/features/auth/services/AuthService';
import type { Session } from '@/features/auth/types';
import { Role } from '@/features/rbac/roles';
import { en } from '@/lib/i18n/strings/en';
import type {
  DocumentListResponse,
  DocumentReadResponse,
  EngagementListResponse,
} from '@/lib/api/types';
import { DocumentDetailPage } from '../pages/DocumentDetailPage';

/**
 * Responsive and accessibility checks for the Evidence Review panel,
 * English/LTR.
 *
 * **What jsdom can and cannot prove.** jsdom performs no layout:
 * `scrollWidth` and `clientWidth` are both `0`, so an overflow assertion
 * would compare `0 <= 0` and pass regardless of the CSS. Real
 * horizontal-overflow checking needs a browser, and this file does not
 * pretend otherwise.
 *
 * What it *can* prove, and does:
 *
 * - The panel renders its status, provenance and decision controls at all
 *   five required widths — no breakpoint drops the primary action.
 * - The confirmation dialog is reachable and operable at the narrowest
 *   width, which is where a mobile overlay would most plausibly obstruct
 *   the control a reviewer needs.
 * - The structural rules that make the CSS work are present: long
 *   filenames and long reasons are rendered in full rather than truncated
 *   away, the status region and decision list are named, every control has
 *   an accessible name, and focus moves into the dialog and back out.
 */

const WIDTHS = [360, 480, 768, 1280, 1440] as const;

const getDocument = vi.fn<() => Promise<DocumentReadResponse>>();
const listDocuments = vi.fn<() => Promise<DocumentListResponse>>();
const listEngagements = vi.fn<() => Promise<EngagementListResponse>>();

vi.mock('@/lib/api/endpoints/documents', () => ({
  getDocument: (...args: unknown[]) => getDocument(...(args as [])),
  listDocuments: (...args: unknown[]) => listDocuments(...(args as [])),
  processDocument: vi.fn<() => Promise<never>>(),
  generateEmbeddings: vi.fn<() => Promise<never>>(),
  verifyDocumentEvidence: vi.fn<() => Promise<never>>(),
  rejectDocumentEvidence: vi.fn<() => Promise<never>>(),
  restrictDocumentEvidence: vi.fn<() => Promise<never>>(),
  supersedeDocumentEvidence: vi.fn<() => Promise<never>>(),
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

vi.mock('@/lib/api/endpoints/analysis', () => ({
  analyzeDocument: vi.fn<() => Promise<never>>(),
}));

/** Deliberately hostile content: a filename with no spaces to break on and
 * a reason far longer than any panel column. */
const LONG_FILENAME =
  'Consolidated-Group-Scope-1-and-Scope-2-Greenhouse-Gas-Emissions-Restatement-Appendix-C-2026-Final-v11.pdf';
const LONG_REASON =
  'Restricted pending restatement of the underlying methodology, because the reported ' +
  'intensity figures were derived from a boundary definition that changed midway through ' +
  'the reporting period and the resulting series is not comparable across quarters without ' +
  'a documented reconciliation that has not yet been produced by the reporting entity.';

const DOCUMENT_ID = 'doc-live-1';

function setViewport(width: number) {
  Object.defineProperty(window, 'innerWidth', { value: width, configurable: true });
  window.dispatchEvent(new Event('resize'));
}

function buildLiveSession(role: Role): Session {
  return {
    kind: 'live',
    user: {
      id: 'user-live-1',
      name: 'Live Reviewer',
      email: 'live.reviewer@example.test',
      role,
      orgIds: ['org-live-1'],
    },
    token: 'supabase-session',
    expiresAt: Date.now() + 60 * 60 * 1000,
    activeOrgId: 'org-live-1',
  };
}

function buildLiveAuthService(role: Role): AuthService {
  return {
    async requestLogin(): Promise<LoginResult> {
      throw new Error('unused in this test');
    },
    async logout(): Promise<void> {},
    getSession: () => null,
    setActiveOrg: () => null,
    restoreSession: async () => buildLiveSession(role),
  };
}

function buildDocument(overrides: Partial<DocumentReadResponse> = {}): DocumentReadResponse {
  return {
    id: DOCUMENT_ID,
    engagement_id: 'eng-live-1',
    filename: LONG_FILENAME,
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
    ...overrides,
  };
}

function renderDetail(role: Role = Role.Approver) {
  return render(
    <MemoryRouter initialEntries={[`/documents/${DOCUMENT_ID}`]}>
      <LocaleProvider>
        <AuthProvider service={buildLiveAuthService(role)}>
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

async function findEvidencePanel(): Promise<HTMLElement> {
  const heading = await screen.findByRole('heading', { name: en['evidence.section.title'] });
  const panel = heading.closest('section');
  if (!panel) throw new Error('Evidence review panel was not rendered.');
  return panel;
}

beforeEach(() => {
  getDocument.mockReset();
  listDocuments.mockReset();
  listEngagements.mockReset();

  getDocument.mockResolvedValue(buildDocument());
  listDocuments.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
  listEngagements.mockResolvedValue({
    items: [
      {
        id: 'eng-live-1',
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

/**
 * Per-width cases are limited to the two properties that genuinely depend
 * on viewport width: that the panel renders its decision controls, and
 * that the confirmation dialog stays operable. Everything else about this
 * panel is width-independent, and is proved once below at the narrowest
 * width rather than five times over — re-mounting the whole route tree
 * thirty-five times to re-assert identical facts costs minutes of suite
 * time and proves nothing extra.
 */
describe.each(WIDTHS)('Evidence review at %ipx', (width) => {
  beforeEach(() => setViewport(width));

  it('renders the status, its consequence, and every decision control', async () => {
    renderDetail();
    const panel = await findEvidencePanel();

    expect(within(panel).getByText(en['evidence.status.PENDING_REVIEW'])).toBeVisible();
    expect(within(panel).getByText(en['evidence.status.detail.PENDING_REVIEW'])).toBeVisible();

    for (const label of [
      en['evidence.action.verify'],
      en['evidence.action.reject'],
      en['evidence.action.restrict'],
      en['evidence.action.supersede'],
    ]) {
      expect(within(panel).getByRole('button', { name: new RegExp(label) })).toBeEnabled();
    }
  });

  it('opens a usable confirmation dialog without obstructing the primary action', async () => {
    const user = userEvent.setup();
    renderDetail();
    const panel = await findEvidencePanel();

    await user.click(
      within(panel).getByRole('button', { name: new RegExp(en['evidence.action.reject']) }),
    );
    const dialog = await screen.findByRole('dialog');

    // The submit control — the thing a mobile overlay would most
    // plausibly cover — is present and operable at this width, as are the
    // reason field and the way out.
    const submit = within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] });
    expect(submit).toBeVisible();
    expect(submit).toBeEnabled();
    expect(
      within(dialog).getByRole('button', { name: en['evidence.confirm.cancel'] }),
    ).toBeVisible();
    expect(within(dialog).getByLabelText(en['evidence.reason.label.required'])).toBeVisible();
  });
});

/** The narrowest supported viewport — the hardest case for every one of
 * these, and the one where a layout or focus defect would surface first. */
describe('Evidence review structure at the narrowest viewport', () => {
  beforeEach(() => setViewport(360));

  it('names the status region and the decision list', async () => {
    renderDetail();
    const panel = await findEvidencePanel();

    expect(within(panel).getByRole('region', { name: en['evidence.status.label'] })).toBeVisible();
    expect(within(panel).getByRole('list', { name: en['evidence.actions.label'] })).toBeVisible();
  });

  it('gives every decision control an accessible name', async () => {
    renderDetail();
    const panel = await findEvidencePanel();

    for (const control of within(panel).getAllByRole('button')) {
      expect(control).toHaveAccessibleName();
    }
  });

  it('renders a long filename in full rather than truncating it away', async () => {
    const user = userEvent.setup();
    renderDetail();
    const panel = await findEvidencePanel();

    await user.click(
      within(panel).getByRole('button', { name: new RegExp(en['evidence.action.reject']) }),
    );
    const dialog = await screen.findByRole('dialog');

    // A reviewer confirming an irreversible decision must be able to read
    // the whole filename, however long it is.
    expect(within(dialog).getByText(LONG_FILENAME)).toBeVisible();
  });

  it('renders a long recorded reason in full', async () => {
    getDocument.mockResolvedValue(
      buildDocument({
        evidence_status: 'RESTRICTED',
        reviewed_by: 'user-approver-77',
        reviewed_at: '2026-07-14T08:30:00Z',
        review_reason: LONG_REASON,
      }),
    );

    renderDetail();
    const panel = await findEvidencePanel();

    expect(within(panel).getByText(LONG_REASON)).toBeVisible();
  });

  it('states the denial truthfully for a role that cannot decide', async () => {
    renderDetail(Role.Editor);
    const panel = await findEvidencePanel();

    expect(within(panel).getByText(en['evidence.denied.title'])).toBeVisible();
    expect(
      within(panel).queryByRole('button', { name: new RegExp(en['evidence.action.verify']) }),
    ).toBeNull();
  });
});

describe('Evidence review dialog focus management', () => {
  beforeEach(() => setViewport(360));

  it('moves focus into the dialog and restores it to the trigger on close', async () => {
    const user = userEvent.setup();
    renderDetail();
    const panel = await findEvidencePanel();

    const trigger = within(panel).getByRole('button', {
      name: new RegExp(en['evidence.action.reject']),
    });
    await user.click(trigger);

    const dialog = await screen.findByRole('dialog');
    await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true));

    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.cancel'] }));

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    // Radix restores focus to the trigger, so a keyboard user is returned
    // to where they were rather than to the top of the document.
    await waitFor(() => expect(trigger).toHaveFocus());
  });
});
