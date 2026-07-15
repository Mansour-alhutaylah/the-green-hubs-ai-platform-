import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router';
import {
  Button,
  DemoDataBadge,
  DiamondGlyph,
  EmptyState,
  Icon,
  LoadingSkeleton,
  SectionCard,
  StatusBadge,
  type StatusTone,
} from '@/design-system';
import { PageHeader } from '@/shell/PageHeader';
import { useAuth } from '@/features/auth/useAuth';
import { useLocale } from '@/lib/i18n/useLocale';
import { formatDateTime } from '@/lib/utils/formatDate';
import { analyzeDocument, getAnalysisRun } from '@/lib/api/endpoints/analysis';
import { RequestAbortedError } from '@/lib/api/errors';
import type { AnalysisRunResponse, CitationResponse } from '@/lib/api/types';
import type { StringKey } from '@/lib/i18n/strings/en';
import { MOCK_ANALYSIS_RUNS } from '../mockAnalysisData';
import { AnalysisStatusBadge } from '../components/AnalysisStatusBadge';
import { useAnalysisRunQuery } from '../useAnalysisRunQuery';
import { useAnalysisRunPoll } from '../useAnalysisRunPoll';

export function AnalysisRunPage() {
  const { runId } = useParams<{ runId: string }>();
  const { sessionKind } = useAuth();
  const isLive = sessionKind === 'live';

  if (!isLive) {
    return <DemoAnalysisRun runId={runId} />;
  }

  return <LiveAnalysisRun runId={runId} />;
}

/** backend/app/services/analysis/structured_output.py::MetricValue.status */
const METRIC_STATUS_TONE: Record<string, StatusTone> = {
  stated: 'success',
  not_stated: 'neutral',
  uncertain: 'attention',
};

const METRIC_STATUS_LABEL_KEY: Record<string, StringKey> = {
  stated: 'analysis.run.metrics.stated',
  not_stated: 'analysis.run.metrics.notStated',
  uncertain: 'analysis.run.metrics.uncertain',
};

function LiveAnalysisRun({ runId }: { runId: string | undefined }) {
  const { t } = useLocale();
  const query = useAnalysisRunQuery(true, runId);

  const [polledRun, setPolledRun] = useState<AnalysisRunResponse | null>(null);
  useEffect(() => {
    setPolledRun(null);
  }, [runId]);

  const run = polledRun ?? query.run;
  const pollState = useAnalysisRunPoll(runId, run, setPolledRun);

  const [retrySubmitting, setRetrySubmitting] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  async function refreshRun() {
    if (!runId) return;
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      setPolledRun(await getAnalysisRun(runId, controller.signal));
    } catch {
      // A manual refresh failure just leaves the visible state unchanged
      // — the user can try again.
    }
  }

  /** Explicit user retry for a FAILED run — never automatic. The backend's
   * request hash resolves this to the same run and retries it server-side,
   * so no duplicate run is created. */
  async function handleRetryAnalysis(documentId: string) {
    if (retrySubmitting) return;
    setRetrySubmitting(true);
    setRetryError(null);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const next = await analyzeDocument(documentId, controller.signal);
      setPolledRun(next);
    } catch (error) {
      if (error instanceof RequestAbortedError) return;
      setRetryError(error instanceof Error ? error.message : t('documents.detail.intelligence.analysis.error'));
    } finally {
      setRetrySubmitting(false);
    }
  }

  if (query.status === 'loading') {
    return (
      <div>
        <PageHeader eyebrow={t('analysis.run.eyebrow')} title={t('analysis.run.live.title')} subtitle={runId} />
        <SectionCard className="rounded-xl" contentClassName="space-y-5" aria-live="polite" aria-busy="true">
          {Array.from({ length: 3 }, (_, index) => (
            <LoadingSkeleton key={index} lines={2} label={t('analysis.run.loading')} />
          ))}
        </SectionCard>
      </div>
    );
  }

  if (query.status === 'not-found') {
    return (
      <div>
        <PageHeader eyebrow={t('analysis.run.eyebrow')} title={t('analysis.run.live.title')} subtitle={runId} />
        <SectionCard>
          <EmptyState
            title={t('analysis.run.notFound.title')}
            description={t('analysis.run.notFound.description')}
            action={
              <Link className="font-semibold text-leaf-700 hover:underline" to="/documents">
                {t('analysis.run.backToDocuments')}
              </Link>
            }
          />
        </SectionCard>
      </div>
    );
  }

  if (query.status === 'error' || !run) {
    return (
      <div>
        <PageHeader eyebrow={t('analysis.run.eyebrow')} title={t('analysis.run.live.title')} subtitle={runId} />
        <SectionCard className="border-red-100 bg-red-100/35" aria-live="assertive">
          <EmptyState
            title={t('analysis.run.error.title')}
            description={query.error ?? undefined}
            action={
              <Button size="sm" variant="ghost" onClick={query.retry}>
                <Icon name="refresh" size={14} />
                {t('documents.retry')}
              </Button>
            }
          />
        </SectionCard>
      </div>
    );
  }

  if (run.status === 'PROCESSING') {
    return (
      <div>
        <PageHeader
          eyebrow={t('analysis.run.eyebrow')}
          title={t('analysis.run.live.title')}
          subtitle={run.created_at ? t('analysis.run.live.startedAt', { date: formatDateTime(run.created_at) }) : runId}
          action={<AnalysisStatusBadge status="PROCESSING" />}
        />
        <section
          className="mb-5 overflow-hidden rounded-xl border border-white/10 bg-forest-900 p-5 text-white shadow-brand sm:p-6"
          aria-live="polite"
        >
          <div className="flex items-start gap-4">
            <span className="status-processing flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-white/15 bg-white/8 text-leaf-300">
              <Icon name="analysis" size={24} />
            </span>
            <div>
              <h2 className="mt-1 text-title text-white">{t('analysis.run.processing.title')}</h2>
              <p className="mt-1 text-meta text-white/68">{t('analysis.run.processing.description')}</p>
            </div>
          </div>
        </section>
        {pollState.timedOut && (
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-l border border-amber-100 bg-amber-100 p-3 text-amber-700">
            <div>
              <p className="text-meta font-semibold">{t('analysis.run.processing.timeout.title')}</p>
              <p className="mt-1 text-caption">{t('analysis.run.processing.timeout.description')}</p>
            </div>
            <Button size="sm" variant="ghost" onClick={() => void refreshRun()}>
              <Icon name="refresh" size={14} />
              {t('analysis.run.refresh')}
            </Button>
          </div>
        )}
        <SectionCard className="rounded-xl border-leaf-300/60 bg-mist-50">
          <div className="grid gap-6 lg:grid-cols-2">
            <LoadingSkeleton lines={5} label={t('analysis.run.loading')} />
            <LoadingSkeleton lines={5} label={t('analysis.run.loading')} />
          </div>
        </SectionCard>
      </div>
    );
  }

  if (run.status === 'FAILED') {
    return (
      <div>
        <PageHeader
          eyebrow={t('analysis.run.eyebrow')}
          title={t('analysis.run.live.title')}
          subtitle={run.created_at ? t('analysis.run.live.startedAt', { date: formatDateTime(run.created_at) }) : runId}
          action={<AnalysisStatusBadge status="FAILED" />}
        />
        <SectionCard className="rounded-xl border-red-100 bg-red-100/30" aria-live="assertive">
          <EmptyState
            title={t('analysis.run.failed.title')}
            description={run.error_message ?? t('analysis.run.failed.description')}
            action={
              <div className="flex flex-col items-center gap-3">
                {retryError && <p className="text-meta font-semibold text-red-700">{retryError}</p>}
                {run.document_id && (
                  <Button
                    size="sm"
                    isLoading={retrySubmitting}
                    loadingLabel={t('analysis.run.failed.retrying')}
                    onClick={() => void handleRetryAnalysis(run.document_id as string)}
                  >
                    {t('analysis.run.failed.retryAction')}
                  </Button>
                )}
                {run.document_id && (
                  <Link
                    className="font-semibold text-leaf-700 hover:underline"
                    to={`/documents/${run.document_id}`}
                  >
                    {t('analysis.run.viewSourceDocument')}
                  </Link>
                )}
              </div>
            }
          />
        </SectionCard>
      </div>
    );
  }

  if (run.status === 'INSUFFICIENT_EVIDENCE') {
    const reason = run.insufficient_evidence_reason ?? run.structured_output?.insufficient_evidence_reason;
    return (
      <div>
        <PageHeader
          eyebrow={t('analysis.run.eyebrow')}
          title={t('analysis.run.live.title')}
          subtitle={run.created_at ? t('analysis.run.live.startedAt', { date: formatDateTime(run.created_at) }) : runId}
          action={<AnalysisStatusBadge status="INSUFFICIENT_EVIDENCE" />}
        />
        <SectionCard className="rounded-xl border-amber-100 bg-amber-100/30" aria-live="polite">
          <EmptyState
            title={t('analysis.run.insufficient.title')}
            description={t('analysis.run.insufficient.description')}
            action={
              run.document_id ? (
                <Link
                  className="font-semibold text-leaf-700 hover:underline"
                  to={`/documents/${run.document_id}`}
                >
                  {t('analysis.run.viewSourceDocument')}
                </Link>
              ) : undefined
            }
          />
        </SectionCard>
        {reason && (
          <SectionCard className="mt-5 rounded-xl" title={t('analysis.run.insufficient.reasonTitle')}>
            <p className="text-body text-ink-900" data-user-content>
              {reason}
            </p>
          </SectionCard>
        )}
      </div>
    );
  }

  if (run.status !== 'COMPLETED') {
    return (
      <div>
        <PageHeader
          eyebrow={t('analysis.run.eyebrow')}
          title={t('analysis.run.live.title')}
          subtitle={runId}
          action={
            <StatusBadge tone="neutral">
              <span dir="ltr">{run.status}</span>
            </StatusBadge>
          }
        />
        <SectionCard className="rounded-xl">
          <EmptyState
            title={t('analysis.run.unknownStatus.title')}
            description={t('analysis.run.unknownStatus.description')}
            action={
              <Button size="sm" variant="ghost" onClick={() => void refreshRun()}>
                <Icon name="refresh" size={14} />
                {t('analysis.run.refresh')}
              </Button>
            }
          />
        </SectionCard>
      </div>
    );
  }

  return <CompletedAnalysisRun run={run} onRefresh={refreshRun} />;
}

/** Maps persisted citation UUIDs (from structured-output `citation_ids`)
 * to their human-facing citation numbers. UUIDs are never the primary
 * user-facing label. */
function buildCitationOrderById(citations: CitationResponse[]): Map<string, number> {
  return new Map(citations.map((citation) => [citation.id, citation.citation_order]));
}

function CitationRefs({ citationIds, orderById }: { citationIds?: string[]; orderById: Map<string, number> }) {
  const { t } = useLocale();
  const numbers = (citationIds ?? [])
    .map((id) => orderById.get(id))
    .filter((order): order is number => order !== undefined)
    .sort((a, b) => a - b);
  if (numbers.length === 0) return null;
  return (
    <p className="mt-2 text-caption font-semibold text-leaf-700">
      {t('analysis.run.sources.label', { numbers: numbers.join(', ') })}
    </p>
  );
}

function CompletedAnalysisRun({ run, onRefresh }: { run: AnalysisRunResponse; onRefresh: () => Promise<void> }) {
  const { t } = useLocale();
  const structured = run.structured_output;
  const citations = [...run.citations].sort((a, b) => a.citation_order - b.citation_order);
  const orderById = buildCitationOrderById(citations);

  if (!structured) {
    return (
      <div>
        <PageHeader
          eyebrow={t('analysis.run.eyebrow')}
          title={t('analysis.run.live.title')}
          subtitle={run.completed_at ? t('analysis.run.live.completedAt', { date: formatDateTime(run.completed_at) }) : undefined}
          action={<AnalysisStatusBadge status="COMPLETED" />}
        />
        <SectionCard className="rounded-xl">
          <EmptyState
            title={t('analysis.run.result.unavailable.title')}
            description={t('analysis.run.result.unavailable.description')}
            action={
              <Button size="sm" variant="ghost" onClick={() => void onRefresh()}>
                <Icon name="refresh" size={14} />
                {t('analysis.run.refresh')}
              </Button>
            }
          />
        </SectionCard>
      </div>
    );
  }

  const confidence =
    typeof structured.overall_confidence === 'number'
      ? Math.round(structured.overall_confidence * 100)
      : null;
  const topics = structured.detected_topics ?? [];
  const metrics = structured.reported_metrics ?? [];
  const findings = structured.key_findings ?? [];
  const recommendations = structured.recommendations ?? [];

  return (
    <div>
      <header className="panel-enter relative mb-5 overflow-hidden rounded-xl border border-white/10 bg-forest-900 p-5 text-white shadow-brand sm:p-7">
        <span
          className="absolute -end-20 -top-28 h-80 w-80 rounded-full border border-leaf-300/20 shadow-[0_0_0_64px_rgb(184_222_195_/_0.035)]"
          aria-hidden
        />
        <div className="relative z-10 grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <AnalysisStatusBadge status="COMPLETED" />
            </div>
            <p className="type-label mt-5 text-leaf-300">{t('analysis.run.eyebrow')}</p>
            <h1 className="mt-2 break-words text-display text-white sm:text-hero">
              {t('analysis.run.live.title')}
            </h1>
            {run.completed_at && (
              <p className="mt-2 text-body text-white/68">
                {t('analysis.run.live.completedAt', { date: formatDateTime(run.completed_at) })}
              </p>
            )}
            <div className="mt-5 flex flex-wrap gap-2 text-caption font-semibold text-white/72">
              <span className="rounded-full border border-white/15 bg-white/7 px-3 py-1.5">
                {t('analysis.run.overview.reportingPeriod')}
                {': '}
                <span data-user-content dir="auto">
                  {structured.reporting_period ?? t('analysis.run.overview.notStated')}
                </span>
              </span>
              {run.document_id && (
                <Link
                  className="rounded-full border border-white/15 bg-white/7 px-3 py-1.5 text-leaf-300 hover:underline"
                  to={`/documents/${run.document_id}`}
                >
                  {t('analysis.run.viewSourceDocument')}
                </Link>
              )}
            </div>
          </div>

          {confidence !== null && (
            <div className="flex items-center gap-4 rounded-xl border border-white/12 bg-white/7 p-4 lg:min-w-64">
              <div
                className="relative flex h-24 w-24 shrink-0 items-center justify-center rounded-full p-2"
                style={{
                  background: `conic-gradient(var(--color-leaf-500) ${confidence}%, rgb(255 255 255 / 0.13) 0)`,
                }}
                aria-hidden
              >
                <span className="flex h-full w-full items-center justify-center rounded-full bg-forest-900 text-title text-white">
                  <span dir="ltr">{confidence}%</span>
                </span>
              </div>
              <div>
                <p className="type-label text-leaf-300">{t('analysis.run.confidence.label')}</p>
                <p className="mt-1 text-meta font-bold text-white">{t('analysis.run.confidence.detail')}</p>
                <p className="mt-1 text-caption text-white/58">{t('analysis.run.confidence.note')}</p>
              </div>
              <progress className="sr-only" aria-label={t('analysis.run.confidence.label')} max={100} value={confidence}>
                {confidence}%
              </progress>
            </div>
          )}
        </div>
      </header>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(19rem,1fr)]">
        <div className="space-y-5">
          <SectionCard
            className="rounded-xl border-leaf-300/70 bg-mist-50"
            title={t('analysis.run.summary.title')}
            description={t('analysis.run.summary.description')}
          >
            <div className="flex gap-4">
              <span className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-l bg-forest-900 text-leaf-300">
                <Icon name="analysis" size={18} />
              </span>
              <p className="max-w-3xl text-body leading-7 text-ink-900" data-user-content dir="auto">
                {structured.executive_summary}
              </p>
            </div>
            {topics.length > 0 && (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <span className="type-label text-gray-600">{t('analysis.run.overview.topics')}</span>
                {topics.map((topic) => (
                  <span
                    key={topic}
                    className="rounded-full border border-leaf-300 bg-leaf-100 px-3 py-1 text-caption font-semibold text-leaf-700"
                    data-user-content
                    dir="auto"
                  >
                    {topic}
                  </span>
                ))}
              </div>
            )}
          </SectionCard>

          <SectionCard
            className="rounded-xl"
            title={t('analysis.run.metrics.title')}
            description={t('analysis.run.metrics.description')}
          >
            {metrics.length === 0 ? (
              <p className="text-meta text-gray-600">{t('analysis.run.metrics.empty')}</p>
            ) : (
              <ul className="grid gap-3 md:grid-cols-2">
                {metrics.map((metric, index) => {
                  const statusLabelKey = METRIC_STATUS_LABEL_KEY[metric.status];
                  return (
                  <li key={`${metric.name}-${index}`} className="rounded-xl border border-line-200 bg-tint-100 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-body font-bold text-ink-900" data-user-content dir="auto">
                        {metric.name}
                      </p>
                      <StatusBadge tone={METRIC_STATUS_TONE[metric.status] ?? 'neutral'}>
                        {statusLabelKey ? t(statusLabelKey) : <span dir="ltr">{metric.status}</span>}
                      </StatusBadge>
                    </div>
                    {metric.status === 'stated' && metric.value != null ? (
                      <p className="mt-2 text-title text-forest-900" data-user-content dir="ltr">
                        {metric.value}
                        {metric.unit ? ` ${metric.unit}` : ''}
                      </p>
                    ) : (
                      <p className="mt-2 text-meta text-gray-600">{t('analysis.run.metrics.noValue')}</p>
                    )}
                    {metric.period && (
                      <p className="mt-1 text-caption text-gray-600" data-user-content dir="auto">
                        {t('analysis.run.metrics.period', { period: metric.period })}
                      </p>
                    )}
                    <CitationRefs citationIds={metric.citation_ids} orderById={orderById} />
                  </li>
                  );
                })}
              </ul>
            )}
          </SectionCard>

          <SectionCard
            className="rounded-xl"
            title={t('analysis.run.findings.title')}
            description={t('analysis.run.findings.description')}
          >
            {findings.length === 0 ? (
              <p className="text-meta text-gray-600">{t('analysis.run.findings.empty')}</p>
            ) : (
              <ul className="grid gap-3 md:grid-cols-2">
                {findings.map((finding, index) => (
                  <li key={`${index}-${finding.statement.slice(0, 24)}`} className="rounded-xl border border-line-200 bg-tint-100 p-4">
                    <div className="flex items-center gap-2">
                      <DiamondGlyph variant="hollow" size={10} className="text-leaf-700" />
                      <p className="type-label text-leaf-700">
                        {t('analysis.run.findings.label', { number: index + 1 })}
                      </p>
                    </div>
                    <p className="mt-3 text-body text-ink-900" data-user-content dir="auto">
                      {finding.statement}
                    </p>
                    <CitationRefs citationIds={finding.citation_ids} orderById={orderById} />
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard
            className="rounded-xl"
            title={t('analysis.run.recommendations.title')}
            description={t('analysis.run.recommendations.description')}
          >
            {recommendations.length === 0 ? (
              <p className="text-meta text-gray-600">{t('analysis.run.recommendations.empty')}</p>
            ) : (
              <ol className="space-y-3">
                {recommendations.map((recommendation, index) => (
                  <li
                    key={`${index}-${recommendation.statement.slice(0, 24)}`}
                    className="flex gap-4 rounded-l border border-line-200 bg-surface-0 p-4 shadow-card"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-m bg-forest-900 text-caption font-bold text-white">
                      <span dir="ltr">{String(index + 1).padStart(2, '0')}</span>
                    </span>
                    <div>
                      <p className="text-body text-ink-900" data-user-content dir="auto">
                        {recommendation.statement}
                      </p>
                      <CitationRefs citationIds={recommendation.citation_ids} orderById={orderById} />
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </SectionCard>
        </div>

        <aside className="space-y-5" aria-label={t('analysis.run.citations.title')}>
          <SectionCard
            className="rounded-xl border-leaf-300/60"
            title={t('analysis.run.citations.title')}
            description={t('analysis.run.citations.description')}
          >
            {citations.length === 0 ? (
              <p className="text-meta text-gray-600">{t('analysis.run.citations.empty')}</p>
            ) : (
              <ul className="space-y-3">
                {citations.map((citation) => (
                  <li key={citation.id} className="rounded-l border border-line-200 bg-tint-100 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-meta font-bold text-forest-900">
                        {t('analysis.run.citations.source', { number: citation.citation_order })}
                      </p>
                      <p className="text-caption text-gray-600">
                        {t('analysis.run.citations.relevance', { score: citation.relevance_score.toFixed(2) })}
                      </p>
                    </div>
                    <p className="mt-1 text-caption text-gray-600">
                      {t('analysis.run.citations.chunk', { index: citation.chunk_index })}
                      {' · '}
                      {t('analysis.run.citations.chars', { start: citation.char_start, end: citation.char_end })}
                    </p>
                    <details className="mt-2">
                      <summary className="cursor-pointer text-caption font-semibold text-leaf-700">
                        {t('analysis.run.citations.expand')}
                      </summary>
                      <blockquote
                        className="mt-2 border-s-2 border-leaf-300 ps-3 text-meta leading-6 text-ink-900"
                        data-user-content
                        dir="auto"
                      >
                        {citation.quoted_snippet}
                      </blockquote>
                    </details>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        </aside>
      </div>
    </div>
  );
}

/** Unchanged demo/preview rendering — the exact pre-live mock-data
 * component, preserved verbatim so the live branch above adds no risk to
 * the approved design. */
function DemoAnalysisRun({ runId }: { runId: string | undefined }) {
  const run = MOCK_ANALYSIS_RUNS.find((item) => item.id === runId);

  if (!run) {
    return (
      <div>
        <PageHeader
          eyebrow="Analysis intelligence"
          title="Analysis preview"
          subtitle={runId}
          action={<DemoDataBadge />}
        />
        <SectionCard>
          <EmptyState
            title="This analysis preview is unavailable"
            description="No AI request was made. Open one of the locally defined sample runs."
            action={
              <Link to="/analysis" className="font-semibold text-leaf-700 hover:underline">
                Back to analysis
              </Link>
            }
          />
        </SectionCard>
      </div>
    );
  }

  if (run.status === 'PROCESSING') {
    return (
      <div>
        <PageHeader
          eyebrow="Analysis intelligence"
          title={run.documentName}
          subtitle={`Started ${run.startedAt}`}
          action={
            <>
              <DemoDataBadge />
              <AnalysisStatusBadge status={run.status} />
            </>
          }
        />
        <section className="mb-5 overflow-hidden rounded-xl border border-white/10 bg-forest-900 p-5 text-white shadow-brand sm:p-6" aria-live="polite">
          <div className="flex items-start gap-4">
            <span className="status-processing flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-white/15 bg-white/8 text-leaf-300">
              <Icon name="analysis" size={24} />
            </span>
            <div>
              <p className="type-label text-leaf-300">Sample processing path</p>
              <h2 className="mt-1 text-title text-white">Analysis in progress</h2>
              <p className="mt-1 text-meta text-white/68">No AI service is running and no provider has been contacted.</p>
            </div>
          </div>
        </section>
        <SectionCard className="rounded-xl border-leaf-300/60 bg-mist-50">
          <div className="grid gap-6 lg:grid-cols-2">
            <LoadingSkeleton lines={5} label="Analysis summary is processing" />
            <LoadingSkeleton lines={5} label="Analysis findings are processing" />
          </div>
        </SectionCard>
      </div>
    );
  }

  if (run.status === 'FAILED') {
    return (
      <div>
        <PageHeader
          eyebrow="Analysis intelligence"
          title={run.documentName}
          subtitle={`Started ${run.startedAt}`}
          action={
            <>
              <DemoDataBadge />
              <AnalysisStatusBadge status={run.status} />
            </>
          }
        />
        <SectionCard className="rounded-xl border-red-100 bg-red-100/30" aria-live="assertive">
          <EmptyState
            title="Sample analysis could not be completed"
            description="The preview demonstrates a recoverable failure state. No provider or backend was contacted."
            action={
              <Link to="/analysis" className="font-semibold text-leaf-700 hover:underline">
                Return to analysis runs
              </Link>
            }
          />
        </SectionCard>
      </div>
    );
  }

  if (run.status === 'INSUFFICIENT_EVIDENCE') {
    return (
      <div>
        <PageHeader
          eyebrow="Analysis intelligence"
          title={run.documentName}
          subtitle={`Started ${run.startedAt}`}
          action={
            <>
              <DemoDataBadge />
              <AnalysisStatusBadge status={run.status} />
            </>
          }
        />
        <SectionCard className="rounded-xl border-amber-100 bg-amber-100/30" aria-live="polite">
          <EmptyState
            title="Not enough evidence to summarize"
            description={
              run.summary ||
              'The sample source did not contain enough structured data to produce a reliable summary. No provider or backend was contacted.'
            }
            action={
              <Link to="/analysis" className="font-semibold text-leaf-700 hover:underline">
                Return to analysis runs
              </Link>
            }
          />
        </SectionCard>
        {run.findings.length > 0 && (
          <SectionCard className="mt-5 rounded-xl" title="What was found" description="Illustrative observations · Not verified evidence">
            <ul className="grid gap-3 md:grid-cols-2">
              {run.findings.map((finding) => (
                <li key={finding} className="rounded-xl border border-line-200 bg-tint-100 p-4">
                  <p className="text-body text-ink-900">{finding}</p>
                </li>
              ))}
            </ul>
          </SectionCard>
        )}
      </div>
    );
  }

  const confidence = run.confidence ?? 0;

  return (
    <div>
      <header className="panel-enter relative mb-5 overflow-hidden rounded-xl border border-white/10 bg-forest-900 p-5 text-white shadow-brand sm:p-7">
        <span className="absolute -end-20 -top-28 h-80 w-80 rounded-full border border-leaf-300/20 shadow-[0_0_0_64px_rgb(184_222_195_/_0.035)]" aria-hidden />
        <div className="relative z-10 grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <DemoDataBadge label="Preview · Not verified evidence" />
              <AnalysisStatusBadge status={run.status} />
            </div>
            <p className="type-label mt-5 text-leaf-300">Executive analysis preview</p>
            <h1 className="mt-2 break-words text-display text-white sm:text-hero" data-user-content>
              {run.documentName}
            </h1>
            <p className="mt-2 text-body text-white/68">Sample run · Started {run.startedAt}</p>
            <div className="mt-5 flex flex-wrap gap-2 text-caption font-semibold text-white/72">
              <span className="rounded-full border border-white/15 bg-white/7 px-3 py-1.5">Human review required</span>
              <span className="rounded-full border border-white/15 bg-white/7 px-3 py-1.5">Source provenance pending</span>
            </div>
          </div>

          <div className="flex items-center gap-4 rounded-xl border border-white/12 bg-white/7 p-4 lg:min-w-64">
            <div
              className="relative flex h-24 w-24 shrink-0 items-center justify-center rounded-full p-2"
              style={{
                background: `conic-gradient(var(--color-leaf-500) ${confidence}%, rgb(255 255 255 / 0.13) 0)`,
              }}
              aria-hidden
            >
              <span className="flex h-full w-full items-center justify-center rounded-full bg-forest-900 text-title text-white">
                {confidence}%
              </span>
            </div>
            <div>
              <p className="type-label text-leaf-300">Sample confidence</p>
              <p className="mt-1 text-meta font-bold text-white">Illustrative score</p>
              <p className="mt-1 text-caption text-white/58">Not evaluation-calibrated</p>
            </div>
            <progress
              className="sr-only"
              aria-label="Sample analysis confidence"
              max={100}
              value={confidence}
            >
              {confidence}%
            </progress>
          </div>
        </div>
      </header>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(19rem,1fr)]">
        <div className="space-y-5">
          <SectionCard
            className="rounded-xl border-leaf-300/70 bg-mist-50"
            title="Executive summary"
            description="Sample model output for layout review only."
          >
            <div className="flex gap-4">
              <span className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-l bg-forest-900 text-leaf-300">
                <Icon name="analysis" size={18} />
              </span>
              <p className="max-w-3xl text-body leading-7 text-ink-900">{run.summary}</p>
            </div>
          </SectionCard>

          <SectionCard className="rounded-xl" title="Key findings" description="Illustrative observations · Not verified evidence">
            <ul className="grid gap-3 md:grid-cols-2">
              {run.findings.map((finding, index) => (
                <li key={finding} className="rounded-xl border border-line-200 bg-tint-100 p-4">
                  <div className="flex items-center gap-2">
                    <DiamondGlyph variant="hollow" size={10} className="text-leaf-700" />
                    <p className="type-label text-leaf-700">Sample finding {index + 1}</p>
                  </div>
                  <p className="mt-3 text-body text-ink-900">{finding}</p>
                </li>
              ))}
            </ul>
          </SectionCard>

          <SectionCard className="rounded-xl" title="Recommendations" description="Suggested review sequence for demonstration">
            <ol className="space-y-3">
              {run.recommendations.map((recommendation, index) => (
                <li key={recommendation} className="flex gap-4 rounded-l border border-line-200 bg-surface-0 p-4 shadow-card">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-m bg-forest-900 text-caption font-bold text-white">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <div>
                    <p className="type-label text-gray-600">Recommendation</p>
                    <p className="mt-1 text-body text-ink-900">{recommendation}</p>
                  </div>
                </li>
              ))}
            </ol>
          </SectionCard>
        </div>

        <aside className="space-y-5" aria-label="Analysis reference and review boundaries">
          <SectionCard className="rounded-xl border-amber-100" title="Source reference">
            <div className="rounded-l border border-amber-100 bg-amber-100 p-4">
              <div className="flex items-start gap-3">
                <Icon name="documents" size={19} className="mt-0.5 shrink-0 text-amber-700" />
                <div className="min-w-0">
                  <p className="text-meta font-bold text-amber-700">Sample reference · Not verified evidence</p>
                  <p className="mt-2 truncate text-meta text-ink-900">Q3 2025 Sustainability Report.pdf</p>
                  <p className="mt-1 text-caption text-gray-600">Pages 18–21 · Preview placeholder</p>
                </div>
              </div>
            </div>
            <p className="mt-3 text-caption text-gray-600">
              Production citations will require source-backed extraction and explicit provenance. This preview does not claim that evidence exists.
            </p>
          </SectionCard>

          <section className="rounded-xl border border-leaf-300 bg-mist-50 p-5 shadow-card">
            <span className="flex h-10 w-10 items-center justify-center rounded-l bg-forest-900 text-leaf-300">
              <Icon name="shield-check" size={20} />
            </span>
            <h2 className="mt-4 text-panel text-forest-900">Review boundary</h2>
            <p className="mt-1 text-meta text-gray-600">
              Confidence is illustrative and has not been calibrated against an evaluation dataset. Human validation remains required.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
