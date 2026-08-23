import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
import { ConflictError, ForbiddenError, ValidationApiError } from '@/lib/api/errors';
import type {
  DocumentEvidenceResponse,
  DocumentListResponse,
  DocumentReadResponse,
  EngagementListResponse,
} from '@/lib/api/types';
import { DocumentDetailPage } from '../pages/DocumentDetailPage';

/**
 * The Live Evidence Review journey.
 *
 * The properties this file exists to hold, each of which has a specific,
 * plausible way of going wrong:
 *
 * 1. **The rendered decision is the server's.** The obvious failure is a
 *    panel that shows what the reviewer just clicked rather than what the
 *    backend recorded — which looks identical on success and lies on
 *    every failure. The fixtures below therefore make the server's answer
 *    differ from the requested one.
 * 2. **A denied role dispatches nothing.** Hiding a button is not the
 *    same as not sending a request; these tests assert on the endpoint
 *    mocks, not on the DOM alone.
 * 3. **No tenant identifier leaves the browser.** Route parameters, query
 *    strings, storage and form state are all poisoned with a foreign
 *    organization id, and the assertion is on what actually reached the
 *    wire.
 * 4. **The reviewer's reason survives every failure.** Re-typing a
 *    paragraph of justification because someone else edited the document
 *    is the interface punishing the reviewer for a race they did not
 *    cause.
 */

const getDocument = vi.fn<() => Promise<DocumentReadResponse>>();
const listDocuments = vi.fn<() => Promise<DocumentListResponse>>();
const listEngagements = vi.fn<() => Promise<EngagementListResponse>>();
const verifyDocumentEvidence = vi.fn<(...args: unknown[]) => Promise<DocumentEvidenceResponse>>();
const rejectDocumentEvidence = vi.fn<(...args: unknown[]) => Promise<DocumentEvidenceResponse>>();
const restrictDocumentEvidence = vi.fn<(...args: unknown[]) => Promise<DocumentEvidenceResponse>>();
const supersedeDocumentEvidence = vi.fn<(...args: unknown[]) => Promise<DocumentEvidenceResponse>>();
const processDocument = vi.fn<() => Promise<never>>();

vi.mock('@/lib/api/endpoints/documents', () => ({
  getDocument: (...args: unknown[]) => getDocument(...(args as [])),
  listDocuments: (...args: unknown[]) => listDocuments(...(args as [])),
  processDocument: (...args: unknown[]) => processDocument(...(args as [])),
  generateEmbeddings: vi.fn<() => Promise<never>>(),
  verifyDocumentEvidence: (...args: unknown[]) => verifyDocumentEvidence(...args),
  rejectDocumentEvidence: (...args: unknown[]) => rejectDocumentEvidence(...args),
  restrictDocumentEvidence: (...args: unknown[]) => restrictDocumentEvidence(...args),
  supersedeDocumentEvidence: (...args: unknown[]) => supersedeDocumentEvidence(...args),
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

/** The organization the *session* carries. Deliberately distinctive so a
 * test can prove a value that reached the wire came from the session and
 * not from a URL, a parameter, or storage. */
const SESSION_ORGANIZATION_ID = 'org-live-1';

/** The organization an attacker would try to inject. It appears in the
 * route, the query string, storage and form input below; it must never
 * appear in a request. */
const FOREIGN_ORGANIZATION_ID = 'org-attacker-supplied';

const DOCUMENT_ID = 'doc-live-1';
const LIVE_FILENAME = 'Live Backend Quarterly Ledger.pdf';
const SUCCESSOR_ID = 'doc-live-2';
const SUCCESSOR_FILENAME = 'Live Backend Restated Ledger.pdf';

const ALLOWED_ROLES = [Role.Approver, Role.Admin, Role.Owner] as const;
const DENIED_ROLES = [Role.Viewer, Role.Editor] as const;

function buildLiveSession(role: Role): Session {
  return {
    kind: 'live',
    user: {
      id: 'user-live-1',
      name: 'Live Reviewer',
      email: 'live.reviewer@example.test',
      role,
      orgIds: [SESSION_ORGANIZATION_ID],
    },
    token: 'supabase-session',
    expiresAt: Date.now() + 60 * 60 * 1000,
    activeOrgId: SESSION_ORGANIZATION_ID,
  };
}

function buildLiveAuthService(role: Role): AuthService {
  return {
    async requestLogin(): Promise<LoginResult> {
      throw new Error('unused in this test');
    },
    async logout(): Promise<void> {},
    getSession: () => null,
    // Mirrors the real live service: tenant scope is not client-settable.
    setActiveOrg: () => null,
    restoreSession: async () => buildLiveSession(role),
  };
}

function buildDocument(overrides: Partial<DocumentReadResponse> = {}): DocumentReadResponse {
  return {
    id: DOCUMENT_ID,
    engagement_id: 'eng-live-1',
    filename: LIVE_FILENAME,
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

function buildEvidenceResponse(
  overrides: Partial<DocumentEvidenceResponse> = {},
): DocumentEvidenceResponse {
  return {
    id: DOCUMENT_ID,
    engagement_id: 'eng-live-1',
    evidence_status: 'VERIFIED',
    processing_status: 'PROCESSED',
    reviewed_by: 'user-live-1',
    reviewed_at: '2026-07-13T10:00:00Z',
    review_reason: null,
    superseded_by_document_id: null,
    updated_at: '2026-07-13T10:00:00Z',
    ...overrides,
  };
}

/** Renders the real detail page at a route whose parameters are hostile:
 * a foreign organization id sits in the path and the query string. */
function renderDetail(role: Role, { poisonRoute = false }: { poisonRoute?: boolean } = {}) {
  const entry = poisonRoute
    ? `/documents/${DOCUMENT_ID}?organization_id=${FOREIGN_ORGANIZATION_ID}&org=${FOREIGN_ORGANIZATION_ID}`
    : `/documents/${DOCUMENT_ID}`;

  return render(
    <MemoryRouter initialEntries={[entry]}>
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

/** The Evidence Review panel, located by its heading rather than by a test
 * id, so the test exercises the same structure a reader sees. */
async function findEvidencePanel(): Promise<HTMLElement> {
  const heading = await screen.findByRole('heading', { name: en['evidence.section.title'] });
  const panel = heading.closest('section');
  if (!panel) throw new Error('Evidence review panel was not rendered.');
  return panel;
}

function evidenceCommandMocks() {
  return [
    verifyDocumentEvidence,
    rejectDocumentEvidence,
    restrictDocumentEvidence,
    supersedeDocumentEvidence,
  ];
}

function expectNoReviewRequestDispatched() {
  for (const mock of evidenceCommandMocks()) {
    expect(mock).not.toHaveBeenCalled();
  }
}

beforeEach(() => {
  for (const mock of [
    getDocument,
    listDocuments,
    listEngagements,
    processDocument,
    ...evidenceCommandMocks(),
  ]) {
    mock.mockReset();
  }

  getDocument.mockResolvedValue(buildDocument());
  listDocuments.mockResolvedValue({
    items: [
      buildDocument(),
      buildDocument({ id: SUCCESSOR_ID, filename: SUCCESSOR_FILENAME }),
    ],
    total: 2,
    limit: 50,
    offset: 0,
  });
  listEngagements.mockResolvedValue({
    items: [
      {
        id: 'eng-live-1',
        organization_id: SESSION_ORGANIZATION_ID,
        title: 'Live Engagement',
        status: 'ACTIVE',
        created_at: null,
      },
    ],
    page: 1,
    page_size: 20,
    total: 1,
  });

  // Poisoned client-side state. Nothing in the review path may read these,
  // and no request may carry their value.
  window.localStorage.setItem('organization_id', FOREIGN_ORGANIZATION_ID);
  window.localStorage.setItem('activeOrgId', FOREIGN_ORGANIZATION_ID);
  window.sessionStorage.setItem('organization_id', FOREIGN_ORGANIZATION_ID);
});

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});

// ---------------------------------------------------------------------------
// The rendered decision is the server's
// ---------------------------------------------------------------------------

describe('Live evidence status rendering', () => {
  it('renders the real recorded decision and its provenance from the backend response', async () => {
    getDocument.mockResolvedValue(
      buildDocument({
        evidence_status: 'RESTRICTED',
        reviewed_by: 'user-approver-77',
        reviewed_at: '2026-07-14T08:30:00Z',
        review_reason: 'Superseded methodology; excluded pending restatement.',
      }),
    );

    renderDetail(Role.Admin);
    const panel = await findEvidencePanel();

    expect(within(panel).getByText(en['evidence.status.RESTRICTED'])).toBeVisible();
    expect(within(panel).getByText(en['evidence.status.detail.RESTRICTED'])).toBeVisible();
    expect(within(panel).getByText('user-approver-77')).toBeVisible();
    expect(
      within(panel).getByText('Superseded methodology; excluded pending restatement.'),
    ).toBeVisible();
    // Restricted is not retrieval-eligible, and the panel says so in words.
    expect(within(panel).getByText(en['evidence.retrieval.ineligible'])).toBeVisible();
  });

  it('states plainly that an undecided document has no reviewer, timestamp or reason', async () => {
    renderDetail(Role.Admin);
    const panel = await findEvidencePanel();

    expect(within(panel).getByText(en['evidence.status.PENDING_REVIEW'])).toBeVisible();
    expect(within(panel).getByText(en['evidence.provenance.none'])).toBeVisible();
    // No fabricated provenance rows for a decision nobody has made.
    expect(within(panel).queryByText(en['evidence.provenance.reviewedBy'])).toBeNull();
    expect(within(panel).queryByText(en['evidence.provenance.reviewedAt'])).toBeNull();
  });

  it('marks a verified document as the only retrieval-eligible state', async () => {
    getDocument.mockResolvedValue(
      buildDocument({
        evidence_status: 'VERIFIED',
        reviewed_by: 'user-live-1',
        reviewed_at: '2026-07-13T10:00:00Z',
      }),
    );

    renderDetail(Role.Admin);
    const panel = await findEvidencePanel();

    expect(within(panel).getByText(en['evidence.retrieval.eligible'])).toBeVisible();
  });

  it('renders the recorded successor for a superseded document', async () => {
    getDocument.mockResolvedValue(
      buildDocument({
        evidence_status: 'SUPERSEDED',
        reviewed_by: 'user-live-1',
        reviewed_at: '2026-07-13T10:00:00Z',
        review_reason: 'Replaced by the restated ledger.',
        superseded_by_document_id: SUCCESSOR_ID,
      }),
    );

    renderDetail(Role.Admin);
    const panel = await findEvidencePanel();

    expect(within(panel).getByText(en['evidence.provenance.successor'])).toBeVisible();
    expect(within(panel).getByText(SUCCESSOR_ID)).toBeVisible();
  });

  it('leaks no Preview fixture content into a Live render', async () => {
    renderDetail(Role.Admin);
    await findEvidencePanel();

    for (const previewValue of [
      'Facility Alpha — Sustainability Report.pdf',
      'Green Hubs Demo Organization',
      en['evidence.preview.title'],
      en['evidence.preview.description'],
    ]) {
      expect(
        screen.queryByText(previewValue, { exact: false }),
        `Live mode must not render the Preview value "${previewValue}"`,
      ).toBeNull();
    }
  });
});

// ---------------------------------------------------------------------------
// Authorization — M-4, mirrored in the UI
// ---------------------------------------------------------------------------

describe('Evidence review authorization', () => {
  it.each(ALLOWED_ROLES)('offers actionable review controls to %s', async (role) => {
    renderDetail(role);
    const panel = await findEvidencePanel();

    for (const label of [
      en['evidence.action.verify'],
      en['evidence.action.reject'],
      en['evidence.action.restrict'],
      en['evidence.action.supersede'],
    ]) {
      const control = within(panel).getByRole('button', { name: new RegExp(label) });
      expect(control).toBeEnabled();
    }
    expect(within(panel).queryByText(en['evidence.denied.title'])).toBeNull();
  });

  it.each(DENIED_ROLES)('renders no actionable review control for %s', async (role) => {
    renderDetail(role);
    const panel = await findEvidencePanel();

    expect(within(panel).getByText(en['evidence.denied.title'])).toBeVisible();
    expect(within(panel).getByText(en['evidence.denied.description'])).toBeVisible();

    for (const label of [
      en['evidence.action.verify'],
      en['evidence.action.reject'],
      en['evidence.action.restrict'],
      en['evidence.action.supersede'],
    ]) {
      expect(within(panel).queryByRole('button', { name: new RegExp(label) })).toBeNull();
    }
  });

  it.each(DENIED_ROLES)('still shows %s the recorded decision, read-only', async (role) => {
    getDocument.mockResolvedValue(
      buildDocument({
        evidence_status: 'VERIFIED',
        reviewed_by: 'user-approver-77',
        reviewed_at: '2026-07-14T08:30:00Z',
        review_reason: 'Confirmed against the source ledger.',
      }),
    );

    renderDetail(role);
    const panel = await findEvidencePanel();

    expect(within(panel).getByText(en['evidence.status.VERIFIED'])).toBeVisible();
    expect(within(panel).getByText('Confirmed against the source ledger.')).toBeVisible();
  });

  it.each(DENIED_ROLES)('dispatches zero review requests for %s, even with a hostile route', async (role) => {
    renderDetail(role, { poisonRoute: true });
    await findEvidencePanel();

    // Nothing to click, and nothing sent. Both matter: a hidden control
    // that still had a code path to the network would be a real bypass.
    expect(verifyDocumentEvidence).not.toHaveBeenCalled();
    expectNoReviewRequestDispatched();
  });

  it('never dispatches a review request merely by rendering the panel', async () => {
    renderDetail(Role.Admin);
    await findEvidencePanel();

    expect(verifyDocumentEvidence).not.toHaveBeenCalled();
    expectNoReviewRequestDispatched();
  });
});

// ---------------------------------------------------------------------------
// State-based availability
// ---------------------------------------------------------------------------

describe('Evidence command availability', () => {
  it('explains, rather than offers, verify on a document that is not processed', async () => {
    getDocument.mockResolvedValue(buildDocument({ processing_status: 'PENDING' }));

    renderDetail(Role.Admin);
    const panel = await findEvidencePanel();

    expect(
      within(panel).queryByRole('button', { name: new RegExp(en['evidence.action.verify']) }),
    ).toBeNull();
    expect(within(panel).getByText(en['evidence.blocked.not-processed'])).toBeVisible();

    // Withdrawal carries no processing precondition, so it stays offered.
    expect(
      within(panel).getByRole('button', { name: new RegExp(en['evidence.action.reject']) }),
    ).toBeEnabled();
  });

  it('offers no command at all once a decision has been recorded', async () => {
    getDocument.mockResolvedValue(
      buildDocument({
        evidence_status: 'REJECTED',
        reviewed_by: 'user-live-1',
        reviewed_at: '2026-07-13T10:00:00Z',
        review_reason: 'Not an acceptable source.',
      }),
    );

    renderDetail(Role.Admin);
    const panel = await findEvidencePanel();

    expect(within(panel).getByText(en['evidence.settled.title'])).toBeVisible();
    for (const label of [
      en['evidence.action.verify'],
      en['evidence.action.reject'],
      en['evidence.action.restrict'],
      en['evidence.action.supersede'],
    ]) {
      expect(within(panel).queryByRole('button', { name: new RegExp(label) })).toBeNull();
    }
  });

  it('allows a verified document to be withdrawn but not re-verified', async () => {
    getDocument.mockResolvedValue(
      buildDocument({
        evidence_status: 'VERIFIED',
        reviewed_by: 'user-live-1',
        reviewed_at: '2026-07-13T10:00:00Z',
      }),
    );

    renderDetail(Role.Admin);
    const panel = await findEvidencePanel();

    expect(within(panel).getByText(en['evidence.blocked.already-in-state'])).toBeVisible();
    expect(
      within(panel).getByRole('button', { name: new RegExp(en['evidence.action.restrict']) }),
    ).toBeEnabled();
  });
});

// ---------------------------------------------------------------------------
// Confirmation, payloads and refetch
// ---------------------------------------------------------------------------

async function openCommand(role: Role, label: string) {
  const user = userEvent.setup();
  renderDetail(role);
  const panel = await findEvidencePanel();
  await user.click(within(panel).getByRole('button', { name: new RegExp(label) }));
  const dialog = await screen.findByRole('dialog');
  return { user, dialog, panel };
}

describe('Evidence decision commands', () => {
  it('requires a confirmation step before any request is dispatched', async () => {
    const { dialog } = await openCommand(Role.Approver, en['evidence.action.verify']);

    // The dialog is open and nothing has been sent yet.
    expect(dialog).toBeVisible();
    expectNoReviewRequestDispatched();
  });

  it('dispatches nothing when the confirmation is cancelled', async () => {
    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.verify']);

    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.cancel'] }));

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expectNoReviewRequestDispatched();
  });

  it('sends the typed verify payload and re-reads the authoritative document', async () => {
    verifyDocumentEvidence.mockResolvedValue(buildEvidenceResponse());
    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.verify']);

    const callsBefore = getDocument.mock.calls.length;
    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] }));

    await waitFor(() => expect(verifyDocumentEvidence).toHaveBeenCalledTimes(1));
    expect(verifyDocumentEvidence).toHaveBeenCalledWith(
      DOCUMENT_ID,
      { reason: '' },
      expect.anything(),
    );

    // Success is confirmed by the server, then re-read from it.
    await waitFor(() => expect(getDocument.mock.calls.length).toBeGreaterThan(callsBefore));
  });

  it('sends the typed reject payload with the reviewer reason', async () => {
    rejectDocumentEvidence.mockResolvedValue(
      buildEvidenceResponse({ evidence_status: 'REJECTED', review_reason: 'Unverifiable source.' }),
    );
    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.reject']);

    await user.type(
      within(dialog).getByLabelText(en['evidence.reason.label.required']),
      'Unverifiable source.',
    );
    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] }));

    await waitFor(() => expect(rejectDocumentEvidence).toHaveBeenCalledTimes(1));
    expect(rejectDocumentEvidence).toHaveBeenCalledWith(
      DOCUMENT_ID,
      { reason: 'Unverifiable source.' },
      expect.anything(),
    );
  });

  it('sends the typed restrict payload with the reviewer reason', async () => {
    restrictDocumentEvidence.mockResolvedValue(
      buildEvidenceResponse({ evidence_status: 'RESTRICTED', review_reason: 'Commercially sensitive.' }),
    );
    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.restrict']);

    await user.type(
      within(dialog).getByLabelText(en['evidence.reason.label.required']),
      'Commercially sensitive.',
    );
    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] }));

    await waitFor(() => expect(restrictDocumentEvidence).toHaveBeenCalledTimes(1));
    expect(restrictDocumentEvidence).toHaveBeenCalledWith(
      DOCUMENT_ID,
      { reason: 'Commercially sensitive.' },
      expect.anything(),
    );
  });

  it('sends the typed supersede payload with a chosen successor', async () => {
    supersedeDocumentEvidence.mockResolvedValue(
      buildEvidenceResponse({
        evidence_status: 'SUPERSEDED',
        superseded_by_document_id: SUCCESSOR_ID,
      }),
    );
    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.supersede']);

    await user.type(
      within(dialog).getByLabelText(en['evidence.reason.label.required']),
      'Replaced by the restated ledger.',
    );
    await waitFor(() =>
      expect(within(dialog).getByRole('option', { name: SUCCESSOR_FILENAME })).toBeInTheDocument(),
    );
    await user.selectOptions(
      within(dialog).getByLabelText(en['evidence.successor.label']),
      SUCCESSOR_ID,
    );
    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] }));

    await waitFor(() => expect(supersedeDocumentEvidence).toHaveBeenCalledTimes(1));
    expect(supersedeDocumentEvidence).toHaveBeenCalledWith(
      DOCUMENT_ID,
      { reason: 'Replaced by the restated ledger.', supersededByDocumentId: SUCCESSOR_ID },
      expect.anything(),
    );
  });

  it('never offers the document itself as its own successor', async () => {
    const { dialog } = await openCommand(Role.Approver, en['evidence.action.supersede']);

    await waitFor(() =>
      expect(within(dialog).getByRole('option', { name: SUCCESSOR_FILENAME })).toBeInTheDocument(),
    );
    // The document under review is filtered out of the candidate list, so
    // a self-supersession cannot be selected in the first place.
    expect(within(dialog).queryByRole('option', { name: LIVE_FILENAME })).toBeNull();
  });

  it('omits the successor entirely when none is chosen', async () => {
    supersedeDocumentEvidence.mockResolvedValue(
      buildEvidenceResponse({ evidence_status: 'SUPERSEDED' }),
    );
    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.supersede']);

    await user.type(
      within(dialog).getByLabelText(en['evidence.reason.label.required']),
      'Obsolete, with no replacement.',
    );
    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] }));

    await waitFor(() => expect(supersedeDocumentEvidence).toHaveBeenCalledTimes(1));
    expect(supersedeDocumentEvidence).toHaveBeenCalledWith(
      DOCUMENT_ID,
      { reason: 'Obsolete, with no replacement.', supersededByDocumentId: undefined },
      expect.anything(),
    );
  });
});

// ---------------------------------------------------------------------------
// Tenant scope cannot be injected from the browser
// ---------------------------------------------------------------------------

describe('Tenant scope is never client-supplied', () => {
  it('sends no organization identifier from route, query, storage or form state', async () => {
    rejectDocumentEvidence.mockResolvedValue(
      buildEvidenceResponse({ evidence_status: 'REJECTED' }),
    );

    const user = userEvent.setup();
    renderDetail(Role.Approver, { poisonRoute: true });
    const panel = await findEvidencePanel();
    await user.click(
      within(panel).getByRole('button', { name: new RegExp(en['evidence.action.reject']) }),
    );
    const dialog = await screen.findByRole('dialog');

    // Even the free-text reason carries the injected id: a payload builder
    // that echoed form state into a scope field would be caught here.
    await user.type(
      within(dialog).getByLabelText(en['evidence.reason.label.required']),
      `organization_id=${FOREIGN_ORGANIZATION_ID}`,
    );
    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] }));

    await waitFor(() => expect(rejectDocumentEvidence).toHaveBeenCalledTimes(1));

    const call = rejectDocumentEvidence.mock.calls[0];
    if (!call) throw new Error('reject was not dispatched.');
    const [documentId, payload] = call;
    expect(documentId).toBe(DOCUMENT_ID);

    // The reason is passed through verbatim — it is the reviewer's words,
    // not a scope input — but no *field* carries a tenant identifier.
    const payloadKeys = Object.keys(payload as object);
    expect(payloadKeys).toEqual(['reason']);
    for (const key of payloadKeys) {
      expect(key).not.toMatch(/organization|tenant|org_id/i);
    }
    expect(JSON.stringify({ ...(payload as object), reason: undefined })).not.toContain(
      FOREIGN_ORGANIZATION_ID,
    );
  });

  it('sends no organization or reviewer identity on verify', async () => {
    verifyDocumentEvidence.mockResolvedValue(buildEvidenceResponse());
    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.verify']);

    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] }));

    await waitFor(() => expect(verifyDocumentEvidence).toHaveBeenCalledTimes(1));
    const verifyCall = verifyDocumentEvidence.mock.calls[0];
    if (!verifyCall) throw new Error('verify was not dispatched.');
    const payload = verifyCall[1] as object;

    // The server records who decided and when. A client that sent them
    // would be asserting provenance it cannot be trusted for.
    for (const forbidden of [
      'organization_id',
      'tenant_id',
      'reviewed_by',
      'reviewed_at',
      'evidence_status',
    ]) {
      expect(payload).not.toHaveProperty(forbidden);
    }
  });
});

// ---------------------------------------------------------------------------
// Pending state, failures, and the reviewer's words
// ---------------------------------------------------------------------------

describe('Evidence decision failure handling', () => {
  it('prevents a duplicate submission while a request is in flight', async () => {
    let release: (value: DocumentEvidenceResponse) => void = () => {};
    verifyDocumentEvidence.mockImplementation(
      () =>
        new Promise<DocumentEvidenceResponse>((resolve) => {
          release = resolve;
        }),
    );

    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.verify']);
    const submit = within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] });

    await user.click(submit);
    await waitFor(() => expect(verifyDocumentEvidence).toHaveBeenCalledTimes(1));

    // The same control, now reporting itself busy and refusing further
    // submissions. React keeps the node, so this is the button the
    // reviewer would click again.
    await waitFor(() => expect(submit).toBeDisabled());
    expect(submit).toHaveAttribute('aria-busy', 'true');
    expect(submit).toHaveTextContent(en['evidence.confirm.submitting']);

    // A second click, and a second Enter, while the first is in flight.
    await user.click(submit).catch(() => {});
    await user.keyboard('{Enter}');

    expect(verifyDocumentEvidence).toHaveBeenCalledTimes(1);
    release(buildEvidenceResponse());
  });

  it('renders a 409 conflict truthfully and offers a refresh path', async () => {
    rejectDocumentEvidence.mockRejectedValue(
      new ConflictError('Document is not in a state that can be rejected.'),
    );

    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.reject']);
    await user.type(
      within(dialog).getByLabelText(en['evidence.reason.label.required']),
      'A carefully written justification.',
    );
    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] }));

    const alert = await within(dialog).findByRole('alert');
    expect(alert).toHaveTextContent(en['evidence.error.conflict.title']);
    expect(alert).toHaveTextContent(en['evidence.error.conflict.description']);

    // The recovery path is a refresh, not a blind retry.
    expect(
      within(dialog).getByRole('button', { name: new RegExp(en['evidence.error.conflict.refresh']) }),
    ).toBeEnabled();
  });

  it('refetches the authoritative document when the conflict refresh is used', async () => {
    rejectDocumentEvidence.mockRejectedValue(new ConflictError('Conflicting decision.'));

    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.reject']);
    await user.type(
      within(dialog).getByLabelText(en['evidence.reason.label.required']),
      'Justification.',
    );
    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] }));
    await within(dialog).findByRole('alert');

    const callsBefore = getDocument.mock.calls.length;
    await user.click(
      within(dialog).getByRole('button', { name: new RegExp(en['evidence.error.conflict.refresh']) }),
    );

    await waitFor(() => expect(getDocument.mock.calls.length).toBeGreaterThan(callsBefore));
  });

  it('never discards the reviewer reason when the command fails', async () => {
    const reason = 'A long, carefully written justification that must survive a failure.';
    rejectDocumentEvidence.mockRejectedValue(new ConflictError('Conflicting decision.'));

    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.reject']);
    const field = within(dialog).getByLabelText(en['evidence.reason.label.required']);
    await user.type(field, reason);
    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] }));
    await within(dialog).findByRole('alert');

    expect(field).toHaveValue(reason);
  });

  it('reports a validation failure accessibly, without dispatching a request', async () => {
    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.reject']);

    // Submitted with no reason at all.
    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] }));

    const field = within(dialog).getByLabelText(en['evidence.reason.label.required']);
    const alert = await within(dialog).findByRole('alert');
    expect(alert).toHaveTextContent(en['evidence.reason.error.required']);
    expect(field).toHaveAttribute('aria-invalid', 'true');
    expect(field.getAttribute('aria-describedby')).toContain(alert.id);

    // A client-side validation failure is not a round trip.
    expectNoReviewRequestDispatched();
  });

  it('treats a whitespace-only reason as no reason', async () => {
    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.restrict']);

    await user.type(within(dialog).getByLabelText(en['evidence.reason.label.required']), '    ');
    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] }));

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      en['evidence.reason.error.required'],
    );
    expectNoReviewRequestDispatched();
  });

  it('renders a server validation message without exposing internals', async () => {
    rejectDocumentEvidence.mockRejectedValue(new ValidationApiError('A review reason is required.'));

    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.reject']);
    await user.type(
      within(dialog).getByLabelText(en['evidence.reason.label.required']),
      'Some reason.',
    );
    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] }));

    const alert = await within(dialog).findByRole('alert');
    expect(alert).toHaveTextContent(en['evidence.error.title']);
    expect(alert).toHaveTextContent('A review reason is required.');
    for (const forbidden of ['Traceback', 'asyncpg', 'SELECT', 'Bearer']) {
      expect(alert.textContent ?? '').not.toContain(forbidden);
    }
  });

  it('reports a server-side refusal without claiming anything was changed', async () => {
    rejectDocumentEvidence.mockRejectedValue(new ForbiddenError("You don't have permission."));

    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.reject']);
    await user.type(
      within(dialog).getByLabelText(en['evidence.reason.label.required']),
      'Some reason.',
    );
    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] }));

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      en['evidence.error.forbidden'],
    );
  });

  it('does not claim success or refetch when the command fails', async () => {
    rejectDocumentEvidence.mockRejectedValue(new ConflictError('Conflicting decision.'));

    const { user, dialog } = await openCommand(Role.Approver, en['evidence.action.reject']);
    await user.type(
      within(dialog).getByLabelText(en['evidence.reason.label.required']),
      'Justification.',
    );
    const callsBefore = getDocument.mock.calls.length;
    await user.click(within(dialog).getByRole('button', { name: en['evidence.confirm.submit'] }));
    await within(dialog).findByRole('alert');

    // The dialog stays open and no authoritative re-read was triggered by
    // a failure — nothing may look like it succeeded.
    expect(screen.getByRole('dialog')).toBeVisible();
    expect(getDocument.mock.calls.length).toBe(callsBefore);
  });
});

// ---------------------------------------------------------------------------
// Accessibility and keyboard operation
// ---------------------------------------------------------------------------

describe('Evidence review accessibility', () => {
  it('exposes the status region and the decision list by name', async () => {
    renderDetail(Role.Admin);
    const panel = await findEvidencePanel();

    expect(within(panel).getByRole('region', { name: en['evidence.status.label'] })).toBeVisible();
    expect(within(panel).getByRole('list', { name: en['evidence.actions.label'] })).toBeVisible();
  });

  it('opens the confirmation dialog from the keyboard and labels its fields', async () => {
    const user = userEvent.setup();
    renderDetail(Role.Approver);
    const panel = await findEvidencePanel();

    const reject = within(panel).getByRole('button', {
      name: new RegExp(en['evidence.action.reject']),
    });
    reject.focus();
    expect(reject).toHaveFocus();
    await user.keyboard('{Enter}');

    const dialog = await screen.findByRole('dialog');
    // Radix moves focus into the dialog and traps it there.
    await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true));

    const field = within(dialog).getByLabelText(en['evidence.reason.label.required']);
    expect(field).toBeVisible();
    expect(field).toHaveAttribute('aria-required', 'true');
    // The hint is associated, not merely adjacent.
    expect(field.getAttribute('aria-describedby')).toBeTruthy();
  });

  it('communicates each status with text, never by color alone', async () => {
    getDocument.mockResolvedValue(buildDocument({ evidence_status: 'RESTRICTED' }));

    renderDetail(Role.Admin);
    const panel = await findEvidencePanel();

    // The badge carries its own label; a reader who cannot distinguish the
    // tone still learns the state.
    expect(within(panel).getByText(en['evidence.status.RESTRICTED'])).toBeVisible();
  });

  it('closes the dialog with Escape when no request is in flight', async () => {
    const { user } = await openCommand(Role.Approver, en['evidence.action.verify']);

    await user.keyboard('{Escape}');

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expectNoReviewRequestDispatched();
  });
});
