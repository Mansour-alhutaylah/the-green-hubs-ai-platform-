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
import { AnalysisRunPage } from '../pages/AnalysisRunPage';
import type { AnalysisRunResponse, StructuredAnalysisResponse } from '@/lib/api/types';
import { ApiError, NotFoundApiError } from '@/lib/api/errors';

const getAnalysisRun = vi.fn<() => Promise<AnalysisRunResponse>>();
const analyzeDocument = vi.fn<() => Promise<AnalysisRunResponse>>();

vi.mock('@/lib/api/endpoints/analysis', () => ({
  getAnalysisRun: (...args: unknown[]) => getAnalysisRun(...(args as [])),
  analyzeDocument: (...args: unknown[]) => analyzeDocument(...(args as [])),
}));

vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: async () => ({
    items: [{ id: 'org-1', name: 'Al-Riyadh Industrial Group', created_at: null }],
    page: 1,
    page_size: 1,
    total: 1,
  }),
}));

vi.mock('@/lib/api/endpoints/engagements', () => ({
  listEngagements: async () => ({ items: [], page: 1, page_size: 100, total: 0 }),
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

function renderRun(runId: string) {
  return render(
    <MemoryRouter initialEntries={[`/analysis/${runId}`]}>
      <LocaleProvider>
        <AuthProvider service={buildLiveAuthService()}>
          <WorkspaceProvider>
            <TooltipProvider>
              <ToastProvider>
                <Routes>
                  <Route path="/analysis/:runId" element={<AnalysisRunPage />} />
                </Routes>
              </ToastProvider>
            </TooltipProvider>
          </WorkspaceProvider>
        </AuthProvider>
      </LocaleProvider>
    </MemoryRouter>,
  );
}

function buildStructuredOutput(overrides: Partial<StructuredAnalysisResponse> = {}): StructuredAnalysisResponse {
  return {
    analysis_type: 'sustainability_summary',
    evidence_status: 'sufficient',
    insufficient_evidence_reason: null,
    executive_summary: 'The report presents verified emissions figures for the 2025 fiscal year.',
    reporting_period: 'FY2025',
    detected_topics: ['Emissions', 'Renewable energy'],
    reported_metrics: [
      {
        name: 'Scope 1 emissions',
        status: 'stated',
        value: '12500',
        unit: 'tCO2e',
        period: 'FY2025',
        citation_ids: ['cit-1'],
      },
      { name: 'Water withdrawal', status: 'not_stated', value: null, unit: null, period: null, citation_ids: [] },
      { name: 'Renewable share', status: 'uncertain', value: null, unit: null, period: null, citation_ids: ['cit-2'] },
    ],
    key_findings: [{ statement: 'Scope 1 emissions decreased year over year.', citation_ids: ['cit-1'] }],
    recommendations: [{ statement: 'Document the estimation methodology.', citation_ids: ['cit-2'] }],
    overall_confidence: 0.87,
    ...overrides,
  };
}

function buildRun(overrides: Partial<AnalysisRunResponse> = {}): AnalysisRunResponse {
  return {
    analysis_run_id: 'run-live-1',
    engagement_id: 'eng-live-1',
    document_id: 'doc-live-1',
    status: 'COMPLETED',
    analysis_type: 'sustainability_summary',
    structured_output: buildStructuredOutput(),
    insufficient_evidence_reason: null,
    error_message: null,
    // Deliberately out of order — the page must order by citation_order.
    citations: [
      {
        id: 'cit-2',
        document_id: 'doc-live-1',
        chunk_index: 4,
        char_start: 120,
        char_end: 480,
        quoted_snippet: 'Renewable electricity covered a large share of operations.',
        citation_order: 2,
        relevance_score: 0.74,
      },
      {
        id: 'cit-1',
        document_id: 'doc-live-1',
        chunk_index: 1,
        char_start: 0,
        char_end: 300,
        quoted_snippet: 'Scope 1 emissions were 12,500 tCO2e in FY2025.',
        citation_order: 1,
        relevance_score: 0.91,
      },
    ],
    created_at: '2026-07-14T10:00:00Z',
    updated_at: '2026-07-14T10:01:00Z',
    completed_at: '2026-07-14T10:01:00Z',
    ...overrides,
  };
}

describe('AnalysisRunPage — live mode', () => {
  beforeEach(() => {
    getAnalysisRun.mockReset();
    analyzeDocument.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders a completed structured result with honest metric states and verified citations', async () => {
    getAnalysisRun.mockResolvedValue(buildRun());

    renderRun('run-live-1');

    // Executive summary, reporting period, topics.
    expect(
      await screen.findByText(
        'The report presents verified emissions figures for the 2025 fiscal year.',
        {},
      ),
    ).toBeVisible();
    expect(getAnalysisRun).toHaveBeenCalledWith('run-live-1', expect.anything());
    expect(screen.getByText('FY2025', { selector: 'span[data-user-content]' })).toBeVisible();
    expect(screen.getByText('Emissions')).toBeVisible();
    expect(screen.getByText('Renewable energy')).toBeVisible();

    // Stated metric shows its real value and unit.
    const statedCard = screen.getByText('Scope 1 emissions').closest('li') as HTMLElement;
    expect(within(statedCard).getByText('Stated')).toBeVisible();
    expect(within(statedCard).getByText('12500 tCO2e')).toBeVisible();

    // A not_stated metric never becomes a zero or an invented value.
    const notStatedCard = screen.getByText('Water withdrawal').closest('li') as HTMLElement;
    expect(within(notStatedCard).getByText('Not stated')).toBeVisible();
    expect(within(notStatedCard).getByText('No value stated in the document')).toBeVisible();
    expect(within(notStatedCard).queryByText('0')).not.toBeInTheDocument();

    const uncertainCard = screen.getByText('Renewable share').closest('li') as HTMLElement;
    expect(within(uncertainCard).getByText('Uncertain')).toBeVisible();

    // Findings and recommendations link to citation numbers.
    const findingCard = screen.getByText('Scope 1 emissions decreased year over year.').closest('li') as HTMLElement;
    expect(within(findingCard).getByText('Sources: 1')).toBeVisible();
    const recommendationCard = screen.getByText('Document the estimation methodology.').closest('li') as HTMLElement;
    expect(within(recommendationCard).getByText('Sources: 2')).toBeVisible();

    // Confidence comes from the backend output.
    expect(screen.getAllByText('87%').length).toBeGreaterThan(0);

    // Citations render in citation_order despite the shuffled response.
    const sourceLabels = screen
      .getAllByText(/^Source \d+$/)
      .map((element) => element.textContent);
    expect(sourceLabels).toEqual(['Source 1', 'Source 2']);
    expect(screen.getByText('Chunk 1 · Characters 0–300')).toBeVisible();
    expect(screen.getByText('Relevance 0.91')).toBeVisible();

    // No fabricated page numbers, no vectors, no raw JSON dump.
    expect(screen.queryByText(/page \d+/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\[\s*-?0\.\d+/)).not.toBeInTheDocument();
    expect(screen.queryByText(/"executive_summary"/)).not.toBeInTheDocument();
  });

  it('expands a citation excerpt on demand', async () => {
    getAnalysisRun.mockResolvedValue(buildRun());

    renderRun('run-live-1');
    const user = userEvent.setup();

    await screen.findByText('Source 1', {});

    const snippet = screen.getByText('Scope 1 emissions were 12,500 tCO2e in FY2025.');
    expect(snippet).not.toBeVisible();

    const firstCitation = screen.getByText('Source 1').closest('li') as HTMLElement;
    await user.click(within(firstCitation).getByText('Show excerpt'));
    expect(snippet).toBeVisible();
  });

  it('renders partial structured output (missing optional arrays, empty citations) without crashing', async () => {
    getAnalysisRun.mockResolvedValue(
      buildRun({
        structured_output: {
          analysis_type: 'sustainability_summary',
          evidence_status: 'sufficient',
          executive_summary: 'Only a summary was stored for this older run.',
        },
        citations: [],
      }),
    );

    renderRun('run-live-1');

    expect(
      await screen.findByText('Only a summary was stored for this older run.', {}),
    ).toBeVisible();
    expect(screen.getByText('No metrics were reported in this analysis.')).toBeVisible();
    expect(screen.getByText('No findings were produced by this analysis.')).toBeVisible();
    expect(screen.getByText('No recommendations were produced by this analysis.')).toBeVisible();
    expect(screen.getByText('No citations were stored for this run.')).toBeVisible();
    // Absent reporting period is stated honestly, never invented.
    expect(screen.getByText('Not stated in the document')).toBeVisible();
    // Absent confidence renders no ring rather than a fabricated number.
    expect(screen.queryByText(/%$/)).not.toBeInTheDocument();
  });

  it('ignores unknown optional fields in structured output', async () => {
    const structured = {
      ...buildStructuredOutput(),
      future_field: { nested: true },
    } as unknown as StructuredAnalysisResponse;
    getAnalysisRun.mockResolvedValue(buildRun({ structured_output: structured }));

    renderRun('run-live-1');

    expect(
      await screen.findByText(
        'The report presents verified emissions figures for the 2025 fiscal year.',
        {},
      ),
    ).toBeVisible();
  });

  it('shows a truthful fallback when a completed run has no structured result', async () => {
    getAnalysisRun.mockResolvedValue(buildRun({ structured_output: null, citations: [] }));

    renderRun('run-live-1');

    expect(await screen.findByText('Result data unavailable', {})).toBeVisible();
  });

  it('renders INSUFFICIENT_EVIDENCE as a distinct valid outcome, not a failure or zeroed result', async () => {
    getAnalysisRun.mockResolvedValue(
      buildRun({
        status: 'INSUFFICIENT_EVIDENCE',
        structured_output: null,
        citations: [],
        insufficient_evidence_reason: 'No sufficiently relevant content was found for this request.',
        completed_at: null,
      }),
    );

    renderRun('run-live-1');

    expect(await screen.findByText('Not enough supporting evidence', {})).toBeVisible();
    expect(screen.getByText('No sufficiently relevant content was found for this request.')).toBeVisible();
    expect(screen.getAllByText('Insufficient evidence').length).toBeGreaterThan(0);
    expect(screen.queryByText('The analysis could not be completed')).not.toBeInTheDocument();
    expect(screen.queryByText('Reported metrics')).not.toBeInTheDocument();
    // No automatic retry is offered for this valid outcome.
    expect(screen.queryByRole('button', { name: /run analysis again/i })).not.toBeInTheDocument();
    expect(analyzeDocument).not.toHaveBeenCalled();
  });

  it('renders FAILED distinctly with the safe backend message and an explicit retry', async () => {
    getAnalysisRun.mockResolvedValue(
      buildRun({
        status: 'FAILED',
        structured_output: null,
        citations: [],
        error_message: 'Analysis provider timed out',
        completed_at: null,
      }),
    );
    analyzeDocument.mockResolvedValue(buildRun());

    renderRun('run-live-1');
    const user = userEvent.setup();

    expect(await screen.findByText('The analysis could not be completed', {})).toBeVisible();
    expect(screen.getByText('Analysis provider timed out')).toBeVisible();
    expect(screen.queryByText('Not enough supporting evidence')).not.toBeInTheDocument();
    expect(screen.queryByText(/traceback/i)).not.toBeInTheDocument();
    // Retry never fires automatically.
    expect(analyzeDocument).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: /run analysis again/i }));
    expect(analyzeDocument).toHaveBeenCalledTimes(1);
    expect(analyzeDocument).toHaveBeenCalledWith('doc-live-1', expect.anything());

    expect(
      await screen.findByText(
        'The report presents verified emissions figures for the 2025 fiscal year.',
        {},
      ),
    ).toBeVisible();
  });

  it(
    'polls a PROCESSING run and stops at the terminal state',
    async () => {
      // Real timers, matching the document-processing poll test: the 2s
      // interval is a real setTimeout and fake timers fight React's
      // scheduler in this environment.
      getAnalysisRun.mockResolvedValueOnce(
        buildRun({ status: 'PROCESSING', structured_output: null, citations: [], completed_at: null }),
      );
      getAnalysisRun.mockResolvedValueOnce(
        buildRun({ status: 'PROCESSING', structured_output: null, citations: [], completed_at: null }),
      );
      getAnalysisRun.mockResolvedValueOnce(buildRun());

      renderRun('run-live-1');

      expect(await screen.findByText('Analysis in progress', {})).toBeVisible();
      await waitFor(() => expect(getAnalysisRun).toHaveBeenCalledTimes(2));
      await waitFor(() => expect(getAnalysisRun).toHaveBeenCalledTimes(3));
      expect(
        await screen.findByText(
          'The report presents verified emissions figures for the 2025 fiscal year.',
          {},
        ),
      ).toBeVisible();

      // Polling stopped at the terminal state — no further request after
      // another full interval.
      await new Promise((resolve) => setTimeout(resolve, 2500));
      expect(getAnalysisRun).toHaveBeenCalledTimes(3);
    },
    15_000,
  );

  it(
    'stops polling when the page unmounts',
    async () => {
      getAnalysisRun.mockResolvedValue(
        buildRun({ status: 'PROCESSING', structured_output: null, citations: [], completed_at: null }),
      );

      const view = renderRun('run-live-1');
      expect(await screen.findByText('Analysis in progress', {})).toBeVisible();
      const callsBeforeUnmount = getAnalysisRun.mock.calls.length;
      view.unmount();

      await new Promise((resolve) => setTimeout(resolve, 2500));
      // At most one already-scheduled tick can land; no ongoing polling.
      expect(getAnalysisRun.mock.calls.length).toBeLessThanOrEqual(callsBeforeUnmount + 1);
      const settled = getAnalysisRun.mock.calls.length;
      await new Promise((resolve) => setTimeout(resolve, 2500));
      expect(getAnalysisRun.mock.calls.length).toBe(settled);
    },
    15_000,
  );

  it('shows a not-found state for a missing or foreign-tenant run', async () => {
    getAnalysisRun.mockRejectedValue(new NotFoundApiError('Analysis run not found'));

    renderRun('run-missing');

    expect(
      await screen.findByText('This analysis run could not be found', {}),
    ).toBeVisible();
    expect(screen.getByRole('link', { name: /back to documents/i })).toHaveAttribute('href', '/documents');
  });

  it('shows a retry action on a backend error and recovers on retry', async () => {
    getAnalysisRun.mockRejectedValueOnce(new ApiError(500, 'Something went wrong on our end. Try again.'));
    getAnalysisRun.mockResolvedValueOnce(buildRun());

    renderRun('run-live-1');
    const user = userEvent.setup();

    expect(
      await screen.findByText('This analysis run could not be loaded', {}),
    ).toBeVisible();

    await user.click(screen.getByRole('button', { name: /try again/i }));

    expect(
      await screen.findByText(
        'The report presents verified emissions figures for the 2025 fiscal year.',
        {},
      ),
    ).toBeVisible();
  });

  it('renders an unrecognized status safely with a refresh action', async () => {
    getAnalysisRun.mockResolvedValue(
      buildRun({ status: 'ARCHIVED', structured_output: null, citations: [] }),
    );

    renderRun('run-live-1');

    expect(await screen.findByText('Unrecognized run state', {})).toBeVisible();
    expect(screen.getByRole('button', { name: /refresh status/i })).toBeVisible();
  });
});
