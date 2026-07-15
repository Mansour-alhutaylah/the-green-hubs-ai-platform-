import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { Button, Icon, SectionCard, StatusBadge, type StatusTone } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { formatDateTime } from '@/lib/utils/formatDate';
import { generateEmbeddings } from '@/lib/api/endpoints/documents';
import { analyzeDocument } from '@/lib/api/endpoints/analysis';
import { RequestAbortedError } from '@/lib/api/errors';
import type { DocumentReadResponse, EmbeddingGenerationSummaryResponse } from '@/lib/api/types';
import type { StringKey } from '@/lib/i18n/strings/en';

/** Frontend presentation stages derived from the backend's real
 * `embedding_summary`. `total_chunks` there counts embedding-attempt rows
 * (not document chunks), so "not started" is zero attempts, and
 * `is_complete` is only trusted as "fully embedded" when the attempts
 * cover every extracted chunk — anything less is honestly "partial".
 * These stages exist only for display; no new database status is
 * invented. */
type EmbeddingStage = 'notStarted' | 'processing' | 'failed' | 'completed' | 'partial';

function deriveEmbeddingStage(document: DocumentReadResponse): EmbeddingStage {
  const summary = document.embedding_summary;
  if (summary.total_chunks === 0) return 'notStarted';
  if (summary.processing > 0) return 'processing';
  if (summary.failed > 0) return 'failed';
  if (summary.is_complete && summary.total_chunks >= document.chunk_count) return 'completed';
  return 'partial';
}

const EMBEDDING_STAGE_TONE: Record<EmbeddingStage, StatusTone> = {
  notStarted: 'neutral',
  processing: 'processing',
  failed: 'danger',
  completed: 'success',
  partial: 'attention',
};

const EMBEDDING_STAGE_LABEL_KEY: Record<EmbeddingStage, StringKey> = {
  notStarted: 'documents.detail.intelligence.embeddings.notStarted',
  processing: 'documents.detail.intelligence.embeddings.processing',
  failed: 'documents.detail.intelligence.embeddings.failed',
  completed: 'documents.detail.intelligence.embeddings.completed',
  partial: 'documents.detail.intelligence.embeddings.partial',
};

/** The backend's own analysis-run statuses (plain strings on the wire);
 * anything unrecognized falls back to a neutral badge showing the raw
 * token rather than crashing or guessing. */
const ANALYSIS_STATUS_TONE: Record<string, StatusTone> = {
  PROCESSING: 'processing',
  COMPLETED: 'success',
  FAILED: 'danger',
  INSUFFICIENT_EVIDENCE: 'attention',
};

const ANALYSIS_STATUS_LABEL_KEY: Record<string, StringKey> = {
  PROCESSING: 'analysis.status.processing',
  COMPLETED: 'analysis.status.complete',
  FAILED: 'analysis.status.failed',
  INSUFFICIENT_EVIDENCE: 'analysis.status.insufficientEvidence',
};

interface DocumentIntelligencePanelProps {
  document: DocumentReadResponse;
  /** Re-fetches the document detail so `embedding_summary` and
   * `latest_analysis_summary` reflect the backend after an action. */
  onRefresh: () => Promise<void>;
}

/** Live-mode only: the embeddings → analysis workflow for one processed
 * document. Every action goes through the authenticated API client;
 * nothing here ever renders vectors, content hashes, or raw provider
 * errors — only the backend's own aggregate counts and safe messages. */
export function DocumentIntelligencePanel({ document, onRefresh }: DocumentIntelligencePanelProps) {
  const { t } = useLocale();
  const navigate = useNavigate();

  const [embedSubmitting, setEmbedSubmitting] = useState(false);
  const [embedResult, setEmbedResult] = useState<EmbeddingGenerationSummaryResponse | null>(null);
  const [embedError, setEmbedError] = useState<string | null>(null);

  const [analysisSubmitting, setAnalysisSubmitting] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const isProcessed = document.processing_status === 'PROCESSED';
  const embeddingStage = deriveEmbeddingStage(document);
  const embeddingSummary = document.embedding_summary;

  // The analyze endpoint itself accepts any tenant-visible document and
  // returns INSUFFICIENT_EVIDENCE when retrieval finds nothing; retrieval
  // only searches COMPLETED embeddings, so requiring at least one merely
  // avoids a guaranteed-empty run. Partial embeddings are accepted.
  const analysisReady = isProcessed && embeddingSummary.completed > 0;
  const latestAnalysis = document.latest_analysis_summary;

  async function handleGenerateEmbeddings() {
    if (embedSubmitting || !isProcessed) return;
    setEmbedSubmitting(true);
    setEmbedError(null);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const summary = await generateEmbeddings(document.id, controller.signal);
      setEmbedResult(summary);
      await onRefresh();
    } catch (error) {
      if (error instanceof RequestAbortedError) return;
      setEmbedError(
        error instanceof Error ? error.message : t('documents.detail.intelligence.embeddings.error'),
      );
      // A 409 means the shown processing state is stale — re-sync it.
      await onRefresh();
    } finally {
      setEmbedSubmitting(false);
    }
  }

  async function handleRunAnalysis() {
    if (analysisSubmitting || !analysisReady) return;
    setAnalysisSubmitting(true);
    setAnalysisError(null);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const run = await analyzeDocument(document.id, controller.signal);
      navigate(`/analysis/${run.analysis_run_id}`);
    } catch (error) {
      if (error instanceof RequestAbortedError) return;
      setAnalysisError(
        error instanceof Error ? error.message : t('documents.detail.intelligence.analysis.error'),
      );
      setAnalysisSubmitting(false);
      await onRefresh();
      return;
    }
    setAnalysisSubmitting(false);
  }

  const embedActionLabel =
    embeddingStage === 'failed' || embeddingStage === 'partial'
      ? t('documents.detail.intelligence.embeddings.retryAction')
      : t('documents.detail.intelligence.embeddings.action');

  return (
    <SectionCard
      className="rounded-xl border-leaf-300/60"
      title={t('documents.detail.intelligence.title')}
      description={t('documents.detail.intelligence.description')}
    >
      <div className="space-y-5" aria-live="polite">
        <section aria-label={t('documents.detail.intelligence.embeddings.title')}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-body font-bold text-ink-900">
              {t('documents.detail.intelligence.embeddings.title')}
            </h3>
            <StatusBadge tone={EMBEDDING_STAGE_TONE[embeddingStage]}>
              {t(EMBEDDING_STAGE_LABEL_KEY[embeddingStage])}
            </StatusBadge>
          </div>

          {embeddingStage !== 'notStarted' && (
            <p className="mt-2 text-meta text-gray-600">
              {t('documents.detail.intelligence.embeddings.counts', {
                completed: embeddingSummary.completed,
                total: document.chunk_count,
              })}
              {embeddingSummary.failed > 0 && (
                <>
                  {' · '}
                  {t('documents.detail.intelligence.embeddings.failedCount', {
                    failed: embeddingSummary.failed,
                  })}
                </>
              )}
            </p>
          )}

          {embedError && (
            <div className="mt-3 flex items-start gap-2 rounded-l border border-red-100 bg-red-100 p-3 text-red-700">
              <Icon name="circle-alert" size={15} className="mt-0.5 shrink-0" />
              <p className="text-meta font-semibold">{embedError}</p>
            </div>
          )}

          {embedResult && !embedError && (
            <div className="mt-3 rounded-l border border-line-200 bg-tint-100 p-3">
              <p className="type-label text-leaf-700">
                {t('documents.detail.intelligence.embeddings.result.title')}
              </p>
              <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5">
                {(
                  [
                    ['documents.detail.intelligence.embeddings.result.totalChunks', embedResult.total_chunks],
                    ['documents.detail.intelligence.embeddings.result.newlyCompleted', embedResult.newly_completed],
                    ['documents.detail.intelligence.embeddings.result.alreadyCompleted', embedResult.already_completed],
                    ['documents.detail.intelligence.embeddings.result.failed', embedResult.failed],
                    ['documents.detail.intelligence.embeddings.result.inProgress', embedResult.in_progress],
                    ['documents.detail.intelligence.embeddings.result.conflicts', embedResult.conflicts],
                  ] as Array<[StringKey, number]>
                ).map(([labelKey, count]) => (
                  <div key={labelKey} className="flex items-center justify-between gap-2">
                    <dt className="text-caption text-gray-600">{t(labelKey)}</dt>
                    <dd className="text-caption font-bold text-ink-900">{count}</dd>
                  </div>
                ))}
              </dl>
              {embedResult.failed > 0 && (
                <p className="mt-2 text-caption font-semibold text-amber-700">
                  {t('documents.detail.intelligence.embeddings.result.partialFailure')}
                </p>
              )}
              {embedResult.failed === 0 &&
                embedResult.newly_completed === 0 &&
                embedResult.already_completed > 0 && (
                  <p className="mt-2 text-caption font-semibold text-leaf-700">
                    {t('documents.detail.intelligence.embeddings.result.alreadyDone')}
                  </p>
                )}
            </div>
          )}

          {!isProcessed && (
            <p className="mt-2 text-caption text-gray-600">
              {t('documents.detail.intelligence.embeddings.requiresProcessed')}
            </p>
          )}

          <Button
            size="sm"
            className="mt-3 w-full"
            disabled={!isProcessed || embedSubmitting}
            isLoading={embedSubmitting}
            loadingLabel={t('documents.detail.intelligence.embeddings.submitting')}
            onClick={() => void handleGenerateEmbeddings()}
          >
            {embedActionLabel}
          </Button>
        </section>

        <section
          aria-label={t('documents.detail.intelligence.analysis.title')}
          className="border-t border-line-200 pt-5"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-body font-bold text-ink-900">
              {t('documents.detail.intelligence.analysis.title')}
            </h3>
            {latestAnalysis ? (
              <StatusBadge tone={ANALYSIS_STATUS_TONE[latestAnalysis.status] ?? 'neutral'}>
                {(() => {
                  const labelKey = ANALYSIS_STATUS_LABEL_KEY[latestAnalysis.status];
                  return labelKey ? t(labelKey) : <span dir="ltr">{latestAnalysis.status}</span>;
                })()}
              </StatusBadge>
            ) : (
              <StatusBadge tone="neutral">
                {t('documents.detail.intelligence.analysis.notStarted')}
              </StatusBadge>
            )}
          </div>

          {latestAnalysis && (
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-caption text-gray-600">
                {t('documents.detail.intelligence.analysis.latestLabel')}
                {latestAnalysis.created_at ? ` · ${formatDateTime(latestAnalysis.created_at)}` : ''}
              </p>
              <Link
                to={`/analysis/${latestAnalysis.id}`}
                className="text-caption font-semibold text-leaf-700 hover:underline"
              >
                {t('documents.detail.intelligence.analysis.viewLatest')}
              </Link>
            </div>
          )}

          {!isProcessed && (
            <p className="mt-2 text-caption text-gray-600">
              {t('documents.detail.intelligence.analysis.requiresProcessed')}
            </p>
          )}
          {isProcessed && embeddingSummary.completed === 0 && (
            <p className="mt-2 text-caption text-gray-600">
              {t('documents.detail.intelligence.analysis.requiresEmbeddings')}
            </p>
          )}
          {analysisReady && embeddingStage !== 'completed' && (
            <p className="mt-2 text-caption text-gray-600">
              {t('documents.detail.intelligence.analysis.partialNote')}
            </p>
          )}

          {analysisError && (
            <div className="mt-3 flex items-start gap-2 rounded-l border border-red-100 bg-red-100 p-3 text-red-700">
              <Icon name="circle-alert" size={15} className="mt-0.5 shrink-0" />
              <p className="text-meta font-semibold">{analysisError}</p>
            </div>
          )}

          <Button
            size="sm"
            className="mt-3 w-full"
            disabled={!analysisReady || analysisSubmitting}
            isLoading={analysisSubmitting}
            loadingLabel={t('documents.detail.intelligence.analysis.submitting')}
            onClick={() => void handleRunAnalysis()}
          >
            {t('documents.detail.intelligence.analysis.action')}
          </Button>
        </section>
      </div>
    </SectionCard>
  );
}
