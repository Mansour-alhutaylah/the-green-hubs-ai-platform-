import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useParams } from 'react-router';
import { AuthProvider } from '@/features/auth/AuthContext';
import { WorkspaceProvider } from '@/features/organizations/workspace/WorkspaceProvider';
import { LocaleProvider } from '@/lib/i18n/LocaleContext';
import { TooltipProvider, ToastProvider } from '@/design-system';
import type { AuthService, LoginResult } from '@/features/auth/services/AuthService';
import type { Session } from '@/features/auth/types';
import { Role } from '@/features/rbac/roles';
import { DocumentDetailPage } from '../pages/DocumentDetailPage';
import type {
  AnalysisRunResponse,
  DocumentReadResponse,
  EmbeddingGenerationSummaryResponse,
  EngagementListResponse,
} from '@/lib/api/types';
import { ConflictError, ValidationApiError } from '@/lib/api/errors';

const getDocument = vi.fn<() => Promise<DocumentReadResponse>>();
const generateEmbeddings = vi.fn<() => Promise<EmbeddingGenerationSummaryResponse>>();
const analyzeDocument = vi.fn<() => Promise<AnalysisRunResponse>>();
const listEngagements = vi.fn<() => Promise<EngagementListResponse>>();

vi.mock('@/lib/api/endpoints/documents', () => ({
  getDocument: (...args: unknown[]) => getDocument(...(args as [])),
  generateEmbeddings: (...args: unknown[]) => generateEmbeddings(...(args as [])),
  processDocument: () => {
    throw new Error('processDocument must not be called by these tests');
  },
}));

vi.mock('@/lib/api/endpoints/analysis', () => ({
  analyzeDocument: (...args: unknown[]) => analyzeDocument(...(args as [])),
  getAnalysisRun: () => {
    throw new Error('getAnalysisRun must not be called by these tests');
  },
}));

vi.mock('@/lib/api/endpoints/engagements', () => ({
  listEngagements: (...args: unknown[]) => listEngagements(...(args as [])),
}));

vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: async () => ({
    items: [{ id: 'org-1', name: 'Al-Riyadh Industrial Group', created_at: null }],
    page: 1,
    page_size: 1,
    total: 1,
  }),
}));

function buildSession(kind: 'live' | 'preview'): Session {
  return {
    kind,
    user: { id: 'user-1', name: 'Reem Al-Harbi', email: 'reem@example.com', role: Role.Admin, orgIds: ['org-1'] },
    token: kind === 'live' ? 'supabase-session' : 'demo-token',
    expiresAt: Date.now() + 60 * 60 * 1000,
    activeOrgId: 'org-1',
  };
}

function buildAuthService(kind: 'live' | 'preview'): AuthService {
  return {
    async requestLogin(): Promise<LoginResult> {
      throw new Error('unused');
    },
    async logout(): Promise<void> {},
    getSession: () => (kind === 'preview' ? buildSession('preview') : null),
    setActiveOrg: () => null,
    restoreSession: async () => buildSession(kind),
  };
}

function AnalysisRouteMarker() {
  const { runId } = useParams<{ runId: string }>();
  return <div data-testid="analysis-run-route">{runId}</div>;
}

function renderDetail(documentId: string, kind: 'live' | 'preview' = 'live') {
  return render(
    <MemoryRouter initialEntries={[`/documents/${documentId}`]}>
      <LocaleProvider>
        <AuthProvider service={buildAuthService(kind)}>
          <WorkspaceProvider>
            <TooltipProvider>
              <ToastProvider>
                <Routes>
                  <Route path="/documents/:id" element={<DocumentDetailPage />} />
                  <Route path="/analysis/:runId" element={<AnalysisRouteMarker />} />
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
    embedding_summary: { total_chunks: 0, processing: 0, completed: 0, failed: 0, is_complete: false },
    latest_analysis_summary: null,
    ...overrides,
  };
}

function buildEmbeddingSummary(
  overrides: Partial<EmbeddingGenerationSummaryResponse> = {},
): EmbeddingGenerationSummaryResponse {
  return {
    document_id: 'doc-live-1',
    total_chunks: 12,
    newly_completed: 12,
    already_completed: 0,
    failed: 0,
    in_progress: 0,
    conflicts: 0,
    ...overrides,
  };
}

function buildRun(overrides: Partial<AnalysisRunResponse> = {}): AnalysisRunResponse {
  return {
    analysis_run_id: 'run-live-9',
    engagement_id: 'eng-live-1',
    document_id: 'doc-live-1',
    status: 'COMPLETED',
    analysis_type: 'sustainability_summary',
    structured_output: null,
    insufficient_evidence_reason: null,
    error_message: null,
    citations: [],
    created_at: '2026-07-14T10:00:00Z',
    updated_at: '2026-07-14T10:01:00Z',
    completed_at: '2026-07-14T10:01:00Z',
    ...overrides,
  };
}

describe('DocumentIntelligencePanel — live mode', () => {
  beforeEach(() => {
    getDocument.mockReset();
    generateEmbeddings.mockReset();
    analyzeDocument.mockReset();
    listEngagements.mockReset();
    listEngagements.mockResolvedValue({ items: [], page: 1, page_size: 100, total: 0 });
  });

  it('disables embeddings and analysis for an unprocessed document, with explanations', async () => {
    getDocument.mockResolvedValue(
      buildDocument({ processing_status: 'PENDING', has_extracted_text: false, chunk_count: 0 }),
    );

    renderDetail('doc-live-1');

    const embedButton = await screen.findByRole('button', { name: /generate embeddings/i });
    expect(embedButton).toBeDisabled();
    expect(screen.getByText('Process the document before generating embeddings.')).toBeVisible();

    expect(screen.getByRole('button', { name: /run ai analysis/i })).toBeDisabled();
    expect(screen.getByText('Process the document before running analysis.')).toBeVisible();
  });

  it('disables embeddings for a document whose processing failed', async () => {
    getDocument.mockResolvedValue(
      buildDocument({ processing_status: 'FAILED', has_extracted_text: false, chunk_count: 0 }),
    );

    renderDetail('doc-live-1');

    const embedButton = await screen.findByRole('button', { name: /generate embeddings/i });
    expect(embedButton).toBeDisabled();
    expect(screen.getByRole('button', { name: /run ai analysis/i })).toBeDisabled();
  });

  it('generates embeddings exactly once on duplicate clicks, refreshes detail, and shows real aggregates', async () => {
    getDocument.mockResolvedValueOnce(buildDocument());
    let resolveGeneration: (value: EmbeddingGenerationSummaryResponse) => void = () => {};
    generateEmbeddings.mockImplementation(
      () =>
        new Promise<EmbeddingGenerationSummaryResponse>((resolve) => {
          resolveGeneration = resolve;
        }),
    );
    getDocument.mockResolvedValueOnce(
      buildDocument({
        embedding_summary: { total_chunks: 12, processing: 0, completed: 12, failed: 0, is_complete: true },
      }),
    );

    renderDetail('doc-live-1');
    const user = userEvent.setup();

    const embedButton = await screen.findByRole('button', { name: /generate embeddings/i });
    await user.click(embedButton);
    await user.click(embedButton);
    expect(generateEmbeddings).toHaveBeenCalledTimes(1);
    expect(generateEmbeddings).toHaveBeenCalledWith('doc-live-1', expect.anything());

    resolveGeneration(buildEmbeddingSummary());

    expect(await screen.findByText('Latest generation result', {})).toBeVisible();
    const result = screen.getByText('Latest generation result').closest('div') as HTMLElement;
    expect(within(result).getByText('Total chunks')).toBeVisible();
    expect(within(result).getByText('Newly completed')).toBeVisible();
    // Detail was re-fetched after success and now reflects completion.
    await waitFor(() => expect(getDocument).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('12 of 12 chunk embeddings completed', {})).toBeVisible();
    // Aggregate counts only — never raw vectors or provider payloads.
    expect(screen.queryByText(/\[\s*-?0\.\d+/)).not.toBeInTheDocument();
  });

  it('treats an idempotent already-completed response as success, never as failure', async () => {
    getDocument.mockResolvedValue(
      buildDocument({
        embedding_summary: { total_chunks: 12, processing: 0, completed: 12, failed: 0, is_complete: true },
      }),
    );
    generateEmbeddings.mockResolvedValue(
      buildEmbeddingSummary({ newly_completed: 0, already_completed: 12 }),
    );

    renderDetail('doc-live-1');
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: /generate embeddings/i }));

    expect(
      await screen.findByText('Embeddings were already complete for these chunks.', {}),
    ).toBeVisible();
    expect(screen.queryByText('Unable to generate embeddings.')).not.toBeInTheDocument();
  });

  it('shows a safe aggregate for a partial failure and offers a retry, without provider internals', async () => {
    getDocument.mockResolvedValueOnce(buildDocument());
    generateEmbeddings.mockResolvedValue(
      buildEmbeddingSummary({ newly_completed: 8, failed: 4 }),
    );
    getDocument.mockResolvedValueOnce(
      buildDocument({
        embedding_summary: { total_chunks: 12, processing: 0, completed: 8, failed: 4, is_complete: false },
      }),
    );

    renderDetail('doc-live-1');
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: /generate embeddings/i }));

    expect(
      await screen.findByText(
        'Some chunk embeddings failed. Retrying will attempt only the failed chunks.',
        {},
      ),
    ).toBeVisible();
    expect(await screen.findByRole('button', { name: /retry embeddings/i })).toBeEnabled();
    expect(screen.queryByText(/openai/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/traceback/i)).not.toBeInTheDocument();
  });

  it('renders conflict counts from the aggregate response', async () => {
    getDocument.mockResolvedValue(buildDocument());
    generateEmbeddings.mockResolvedValue(
      buildEmbeddingSummary({ newly_completed: 11, conflicts: 1 }),
    );

    renderDetail('doc-live-1');
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: /generate embeddings/i }));

    const result = (await screen.findByText('Latest generation result', {})).closest(
      'div',
    ) as HTMLElement;
    const conflictsRow = within(result).getByText('Conflicts').closest('div') as HTMLElement;
    expect(within(conflictsRow).getByText('1')).toBeVisible();
  });

  it('surfaces a backend 409 conflict safely and re-syncs the document', async () => {
    getDocument.mockResolvedValue(buildDocument());
    generateEmbeddings.mockRejectedValue(
      new ConflictError('Document must be processed before embeddings can be generated.'),
    );

    renderDetail('doc-live-1');
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: /generate embeddings/i }));

    expect(
      await screen.findByText(
        'Document must be processed before embeddings can be generated.',
        {},
      ),
    ).toBeVisible();
    await waitFor(() => expect(getDocument).toHaveBeenCalledTimes(2));
  });

  it('surfaces a backend 422 validation error safely', async () => {
    getDocument.mockResolvedValue(buildDocument());
    generateEmbeddings.mockRejectedValue(new ValidationApiError('Some of the submitted information is not valid.'));

    renderDetail('doc-live-1');
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: /generate embeddings/i }));

    expect(
      await screen.findByText('Some of the submitted information is not valid.', {}),
    ).toBeVisible();
  });

  it('keeps analysis disabled until at least one embedding is completed', async () => {
    getDocument.mockResolvedValue(buildDocument());

    renderDetail('doc-live-1');

    const analysisButton = await screen.findByRole('button', { name: /run ai analysis/i });
    expect(analysisButton).toBeDisabled();
    expect(screen.getByText('Generate embeddings before running analysis.')).toBeVisible();
  });

  it('runs analysis once on duplicate clicks and navigates to the real returned run id', async () => {
    getDocument.mockResolvedValue(
      buildDocument({
        embedding_summary: { total_chunks: 12, processing: 0, completed: 9, failed: 0, is_complete: false },
      }),
    );
    let resolveAnalysis: (value: AnalysisRunResponse) => void = () => {};
    analyzeDocument.mockImplementation(
      () =>
        new Promise<AnalysisRunResponse>((resolve) => {
          resolveAnalysis = resolve;
        }),
    );

    renderDetail('doc-live-1');
    const user = userEvent.setup();

    const analysisButton = await screen.findByRole('button', { name: /run ai analysis/i });
    // Partial embeddings are accepted, and stated honestly.
    expect(screen.getByText('Some embeddings are incomplete. Analysis uses only the completed ones.')).toBeVisible();

    await user.click(analysisButton);
    await user.click(analysisButton);
    expect(analyzeDocument).toHaveBeenCalledTimes(1);
    expect(analyzeDocument).toHaveBeenCalledWith('doc-live-1', expect.anything());

    resolveAnalysis(buildRun());

    const marker = await screen.findByTestId('analysis-run-route', {});
    expect(marker).toHaveTextContent('run-live-9');
  });

  it('shows a safe message when the analysis request is rejected, without navigating', async () => {
    getDocument.mockResolvedValue(
      buildDocument({
        embedding_summary: { total_chunks: 12, processing: 0, completed: 12, failed: 0, is_complete: true },
      }),
    );
    analyzeDocument.mockRejectedValue(new ValidationApiError('analysis_type must be one of [sustainability_summary]'));

    renderDetail('doc-live-1');
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: /run ai analysis/i }));

    expect(
      await screen.findByText('analysis_type must be one of [sustainability_summary]', {}),
    ).toBeVisible();
    expect(screen.queryByTestId('analysis-run-route')).not.toBeInTheDocument();
  });

  it('links to the latest analysis run when the document already has one', async () => {
    getDocument.mockResolvedValue(
      buildDocument({
        embedding_summary: { total_chunks: 12, processing: 0, completed: 12, failed: 0, is_complete: true },
        latest_analysis_summary: {
          id: 'run-live-3',
          status: 'COMPLETED',
          analysis_type: 'sustainability_summary',
          created_at: '2026-07-13T08:00:00Z',
          completed_at: '2026-07-13T08:01:00Z',
          overall_confidence: 0.8,
        },
      }),
    );

    renderDetail('doc-live-1');

    const link = await screen.findByRole('link', { name: /view latest analysis/i });
    expect(link).toHaveAttribute('href', '/analysis/run-live-3');
  });

  it('demo mode renders the preview page and sends no embeddings or analysis request', async () => {
    renderDetail('doc-1', 'preview');

    expect(await screen.findByText(/local preview record/i, {})).toBeVisible();
    expect(getDocument).not.toHaveBeenCalled();
    expect(generateEmbeddings).not.toHaveBeenCalled();
    expect(analyzeDocument).not.toHaveBeenCalled();
    // The live workflow actions do not exist in the demo preview.
    expect(screen.queryByRole('button', { name: /generate embeddings/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /run ai analysis/i })).not.toBeInTheDocument();
  });
});
