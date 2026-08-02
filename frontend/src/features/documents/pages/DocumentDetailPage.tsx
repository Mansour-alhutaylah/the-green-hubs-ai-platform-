import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router';
import { Button, DemoDataBadge, EmptyState, Icon, LoadingSkeleton, SectionCard } from '@/design-system';
import { PageHeader } from '@/shell/PageHeader';
import { cn } from '@/lib/utils/cn';
import { useAuth } from '@/features/auth/useAuth';
import { useEngagements } from '@/features/engagements/useEngagements';
import { useLocale } from '@/lib/i18n/useLocale';
import { formatDateTime } from '@/lib/utils/formatDate';
import { getDocument, processDocument } from '@/lib/api/endpoints/documents';
import type { DocumentReadResponse } from '@/lib/api/types';
import type { StringKey } from '@/lib/i18n/strings/en';
import { MOCK_DOCUMENTS, type DocumentProcessingStatus } from '../mockDocuments';
import { DocumentStatusBadge } from '../components/DocumentStatusBadge';
import { DocumentIntelligencePanel } from '../components/DocumentIntelligencePanel';
import { useDocumentQuery } from '../useDocumentQuery';
import { useDocumentProcessingPoll } from '../useDocumentProcessingPoll';

const TIMELINE_STATUSES: readonly DocumentProcessingStatus[] = ['PENDING', 'PROCESSING', 'PROCESSED'];

const TIMELINE_STEPS: Array<{
  status: DocumentProcessingStatus;
  label: string;
  description: string;
}> = [
  { status: 'PENDING', label: 'Received', description: 'File registered in the preview queue' },
  { status: 'PROCESSING', label: 'Processing', description: 'Text extraction and quality checks' },
  { status: 'PROCESSED', label: 'Ready for review', description: 'Processing completed successfully' },
];

const LIVE_TIMELINE_LABEL_KEY: Record<DocumentProcessingStatus, StringKey> = {
  PENDING: 'documents.status.pending',
  PROCESSING: 'documents.status.processing',
  PROCESSED: 'documents.status.processed',
  FAILED: 'documents.status.failed',
};

const LIVE_TIMELINE_DESCRIPTION_KEY: Record<DocumentProcessingStatus, StringKey> = {
  PENDING: 'documents.status.context.live.pending',
  PROCESSING: 'documents.status.context.live.processing',
  PROCESSED: 'documents.status.context.live.processed',
  FAILED: 'documents.status.context.live.failed',
};

const STEP_ORDER: Record<DocumentProcessingStatus, number> = {
  PENDING: 0,
  PROCESSING: 1,
  PROCESSED: 2,
  FAILED: 1,
};

export function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useLocale();
  const { sessionKind } = useAuth();
  const isLive = sessionKind === 'live';

  const liveQuery = useDocumentQuery(isLive, id);
  const engagementsState = useEngagements();

  const [polledDocument, setPolledDocument] = useState<DocumentReadResponse | null>(null);
  useEffect(() => {
    setPolledDocument(null);
  }, [id]);

  const pollState = useDocumentProcessingPoll(
    isLive ? id : undefined,
    polledDocument ?? liveQuery.document,
    setPolledDocument,
  );

  const [isProcessing, setIsProcessing] = useState(false);
  const [processError, setProcessError] = useState<string | null>(null);

  async function refreshDocument() {
    if (!id) return;
    try {
      setPolledDocument(await getDocument(id));
    } catch {
      // A manual refresh failure just leaves the visible state unchanged
      // — the user can try again.
    }
  }

  async function handleProcess() {
    if (!id || isProcessing) return;
    setIsProcessing(true);
    setProcessError(null);
    try {
      await processDocument(id);
    } catch (error) {
      setProcessError(error instanceof Error ? error.message : t('documents.detail.process.error'));
    } finally {
      await refreshDocument();
      setIsProcessing(false);
    }
  }

  if (!isLive) {
    return <DemoDocumentDetail id={id} />;
  }

  if (liveQuery.status === 'loading') {
    return (
      <div>
        <PageHeader eyebrow={t('documents.detail.eyebrow')} title={t('nav.documents')} subtitle={id} />
        <SectionCard className="rounded-xl" contentClassName="space-y-5" aria-live="polite" aria-busy="true">
          {Array.from({ length: 3 }, (_, index) => (
            <LoadingSkeleton key={index} lines={2} label="Loading document" />
          ))}
        </SectionCard>
      </div>
    );
  }

  if (liveQuery.status === 'not-found') {
    return (
      <div>
        <PageHeader eyebrow={t('documents.detail.eyebrow')} title={t('nav.documents')} subtitle={id} />
        <SectionCard>
          <EmptyState
            title={t('documents.detail.notFound.title')}
            description={t('documents.detail.notFound.description')}
            action={
              <Link className="font-semibold text-leaf-700 hover:underline" to="/documents">
                {t('documents.detail.backToDocuments')}
              </Link>
            }
          />
        </SectionCard>
      </div>
    );
  }

  if (liveQuery.status === 'error' || !liveQuery.document) {
    return (
      <div>
        <PageHeader eyebrow={t('documents.detail.eyebrow')} title={t('nav.documents')} subtitle={id} />
        <SectionCard className="border-red-100 bg-red-100/35" aria-live="assertive">
          <EmptyState
            title={t('documents.detail.error.title')}
            description={liveQuery.error ?? undefined}
            action={
              <Button size="sm" variant="ghost" onClick={liveQuery.retry}>
                <Icon name="refresh" size={14} />
                {t('documents.retry')}
              </Button>
            }
          />
        </SectionCard>
      </div>
    );
  }

  const confirmedDocument = liveQuery.document;
  const document = polledDocument ?? confirmedDocument;
  const status = document.processing_status as DocumentProcessingStatus;
  const currentStep = STEP_ORDER[status];
  const engagementTitle =
    engagementsState.engagements.find((item) => item.id === document.engagement_id)?.title ?? document.engagement_id;
  const embeddingSummary = document.embedding_summary;

  return (
    <div>
      <PageHeader
        eyebrow={t('documents.detail.eyebrow')}
        title={document.filename}
        subtitle={engagementTitle}
        action={<DocumentStatusBadge status={status} />}
      />

      <section className="relative mb-5 overflow-hidden rounded-xl border border-white/10 bg-forest-900 p-5 text-white shadow-brand sm:p-6">
        <span className="absolute -end-16 -top-20 h-56 w-56 rounded-full border border-leaf-300/20 shadow-[0_0_0_48px_rgb(184_222_195_/_0.035)]" aria-hidden />
        <div className="relative z-10 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex min-w-0 items-start gap-4">
            <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl border border-white/15 bg-white/8 text-leaf-300 shadow-raise">
              <Icon name="documents" size={26} />
            </span>
            <div className="min-w-0">
              <p className="type-label text-leaf-300">{t('documents.detail.metadata.filename')}</p>
              <p className="mt-1 truncate text-title text-white" data-user-content>
                {document.filename}
              </p>
              <p className="mt-1 text-caption text-white/62" data-user-content dir="ltr">
                {document.id}
              </p>
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 lg:min-w-[28rem]">
            <IdentityMetric label={t('documents.detail.metadata.created')} value={formatDateTime(document.created_at)} />
            <IdentityMetric label={t('documents.detail.metadata.updated')} value={formatDateTime(document.updated_at)} />
            <IdentityMetric label={t('documents.table.column.status')} value={t(LIVE_TIMELINE_LABEL_KEY[status])} />
          </dl>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(19rem,1fr)]">
        <SectionCard
          className="rounded-xl border-leaf-300/60"
          title={t('documents.detail.timeline.title')}
          description={t('documents.detail.timeline.description')}
          action={
            <div className="flex items-center gap-2">
              <DocumentStatusBadge status={status} />
              {status === 'PENDING' && (
                <Button
                  size="sm"
                  isLoading={isProcessing}
                  loadingLabel={t('documents.detail.process.submitting')}
                  onClick={() => void handleProcess()}
                >
                  {t('documents.detail.process.action')}
                </Button>
              )}
              <Button
                size="sm"
                variant="ghost"
                aria-label={t('documents.detail.refresh')}
                onClick={() => void refreshDocument()}
              >
                <Icon name="refresh" size={14} />
              </Button>
            </div>
          }
        >
          {processError && (
            <div className="mb-4 flex items-start gap-3 rounded-l border border-red-100 bg-red-100 p-3 text-red-700">
              <Icon name="circle-alert" size={16} className="mt-0.5 shrink-0" />
              <p className="text-meta font-semibold">{processError}</p>
            </div>
          )}
          {pollState.timedOut && (
            <div className="mb-4 rounded-l border border-amber-100 bg-amber-100 p-3 text-amber-700">
              <p className="text-meta font-semibold">{t('documents.detail.process.timeout.title')}</p>
              <p className="mt-1 text-caption">{t('documents.detail.process.timeout.description')}</p>
            </div>
          )}
          <ol className="space-y-0">
            {TIMELINE_STATUSES.map((stepStatus, index) => {
              const complete = index < currentStep || status === 'PROCESSED';
              const active = index === currentStep && status !== 'FAILED';
              const failed = status === 'FAILED' && index === currentStep;
              const isCurrent = active || failed;

              return (
                <li key={stepStatus} className="relative flex gap-4 pb-8 last:pb-0" aria-current={isCurrent ? 'step' : undefined}>
                  {index < TIMELINE_STATUSES.length - 1 && (
                    <span
                      className={cn(
                        'absolute start-[15px] top-8 h-[calc(100%-8px)] w-px',
                        complete ? 'bg-leaf-500' : 'bg-line-200',
                      )}
                      aria-hidden
                    />
                  )}
                  <span
                    className={cn(
                      'relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-micro font-bold shadow-card',
                      failed && 'border-red-700 bg-red-100 text-red-700',
                      complete && !failed && 'border-leaf-700 bg-leaf-700 text-white',
                      active && !complete && 'border-leaf-700 bg-leaf-100 text-leaf-700',
                      !failed && !complete && !active && 'border-line-300 bg-surface-0 text-gray-600',
                    )}
                    aria-hidden
                  >
                    {failed ? <Icon name="circle-alert" size={15} /> : complete ? <Icon name="check" size={15} /> : index + 1}
                  </span>
                  <div className="min-w-0 rounded-l border border-line-200 bg-tint-100 px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-body font-bold text-ink-900">
                        {failed ? t(LIVE_TIMELINE_LABEL_KEY.FAILED) : t(LIVE_TIMELINE_LABEL_KEY[stepStatus])}
                      </p>
                    </div>
                    <p className="mt-1 text-meta text-gray-600">
                      {failed ? t(LIVE_TIMELINE_DESCRIPTION_KEY.FAILED) : t(LIVE_TIMELINE_DESCRIPTION_KEY[stepStatus])}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        </SectionCard>

        <div className="space-y-5">
          <SectionCard className="rounded-xl" title={t('documents.detail.metadata.title')}>
            <dl className="divide-y divide-line-200">
              {[
                [t('documents.detail.metadata.engagement'), engagementTitle],
                [t('documents.detail.metadata.created'), formatDateTime(document.created_at)],
                [t('documents.detail.metadata.updated'), formatDateTime(document.updated_at)],
                [
                  t('documents.detail.metadata.extractedText'),
                  document.has_extracted_text
                    ? t('documents.detail.metadata.extractedText.yes')
                    : t('documents.detail.metadata.extractedText.no'),
                ],
                [t('documents.detail.metadata.chunkCount'), String(document.chunk_count)],
                [
                  t('documents.detail.metadata.embeddings'),
                  embeddingSummary.total_chunks === 0
                    ? t('documents.detail.embeddings.none')
                    : embeddingSummary.is_complete
                      ? t('documents.detail.embeddings.complete', {
                          completed: embeddingSummary.completed,
                          total: embeddingSummary.total_chunks,
                        })
                      : t('documents.detail.embeddings.inProgress', {
                          completed: embeddingSummary.completed,
                          total: embeddingSummary.total_chunks,
                        }),
                ],
              ].map(([label, value]) => (
                <div key={label} className="flex items-start justify-between gap-4 py-3 first:pt-0 last:pb-0">
                  <dt className="text-meta text-gray-600">{label}</dt>
                  <dd className="text-end text-meta font-semibold text-ink-900" data-user-content>
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
          </SectionCard>

          <DocumentIntelligencePanel document={document} onRefresh={refreshDocument} />
        </div>
      </div>
    </div>
  );
}

function IdentityMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-s border-white/12 ps-3 first:border-s-0 first:ps-0">
      <dt className="text-caption text-white/58">{label}</dt>
      <dd className="mt-0.5 truncate text-meta font-bold text-white" data-user-content dir="ltr">
        {value}
      </dd>
    </div>
  );
}

/** Unchanged demo/preview rendering — the exact Phase-1 mock-data
 * component, extracted verbatim so the live branch above adds no risk to
 * it. */
function DemoDocumentDetail({ id }: { id: string | undefined }) {
  const document = MOCK_DOCUMENTS.find((item) => item.id === id);

  if (!document) {
    return (
      <div>
        <PageHeader eyebrow="Document intelligence" title="Document preview" subtitle={id} action={<DemoDataBadge />} />
        <SectionCard>
          <EmptyState
            title="This sample document is unavailable"
            description="Only locally defined preview records can be opened in this frontend sprint."
            action={
              <Link className="font-semibold text-leaf-700 hover:underline" to="/documents">
                Back to documents
              </Link>
            }
          />
        </SectionCard>
      </div>
    );
  }

  const currentStep = STEP_ORDER[document.status];

  return (
    <div>
      <PageHeader
        eyebrow="Document intelligence"
        title={document.name}
        subtitle={document.engagement}
        action={
          <>
            <DemoDataBadge />
            <DocumentStatusBadge status={document.status} />
          </>
        }
      />

      <section className="relative mb-5 overflow-hidden rounded-xl border border-white/10 bg-forest-900 p-5 text-white shadow-brand sm:p-6">
        <span className="absolute -end-16 -top-20 h-56 w-56 rounded-full border border-leaf-300/20 shadow-[0_0_0_48px_rgb(184_222_195_/_0.035)]" aria-hidden />
        <div className="relative z-10 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex min-w-0 items-start gap-4">
            <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl border border-white/15 bg-white/8 text-leaf-300 shadow-raise">
              <Icon name="documents" size={26} />
            </span>
            <div className="min-w-0">
              <p className="type-label text-leaf-300">Source document</p>
              <p className="mt-1 truncate text-title text-white" data-user-content>
                {document.name}
              </p>
              <p className="mt-1 text-caption text-white/62">
                {document.type} · {document.size} · Local preview record
              </p>
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 lg:min-w-[28rem]">
            <IdentityMetric label="Owner" value={document.owner} />
            <IdentityMetric label="Uploaded" value={document.uploadedAt} />
            <IdentityMetric label="Current state" value={document.status} />
          </dl>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(19rem,1fr)]">
        <SectionCard
          className="rounded-xl border-leaf-300/60"
          title="Processing journey"
          description="Preview of the document lifecycle. No processing is running."
          action={<DocumentStatusBadge status={document.status} />}
        >
          <ol className="space-y-0">
            {TIMELINE_STEPS.map((step, index) => {
              const complete = index < currentStep || document.status === 'PROCESSED';
              const active = index === currentStep && document.status !== 'FAILED';
              const failed = document.status === 'FAILED' && index === currentStep;
              const isCurrent = active || failed;

              return (
                <li key={step.status} className="relative flex gap-4 pb-8 last:pb-0" aria-current={isCurrent ? 'step' : undefined}>
                  {index < TIMELINE_STEPS.length - 1 && (
                    <span
                      className={cn(
                        'absolute start-[15px] top-8 h-[calc(100%-8px)] w-px',
                        complete ? 'bg-leaf-500' : 'bg-line-200',
                      )}
                      aria-hidden
                    />
                  )}
                  <span
                    className={cn(
                      'relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-micro font-bold shadow-card',
                      failed && 'border-red-700 bg-red-100 text-red-700',
                      complete && !failed && 'border-leaf-700 bg-leaf-700 text-white',
                      active && !complete && 'border-leaf-700 bg-leaf-100 text-leaf-700',
                      !failed && !complete && !active && 'border-line-300 bg-surface-0 text-gray-600',
                    )}
                    aria-hidden
                  >
                    {failed ? <Icon name="circle-alert" size={15} /> : complete ? <Icon name="check" size={15} /> : index + 1}
                  </span>
                  <div className="min-w-0 rounded-l border border-line-200 bg-tint-100 px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-body font-bold text-ink-900">{failed ? 'Processing failed' : step.label}</p>
                      {isCurrent && (
                        <span className="type-label rounded-full bg-surface-0 px-2 py-0.5 text-leaf-700">Current sample state</span>
                      )}
                    </div>
                    <p className="mt-1 text-meta text-gray-600">
                      {failed ? 'The sample parser could not complete this file.' : step.description}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        </SectionCard>

        <div className="space-y-5">
          <SectionCard className="rounded-xl" title="Source metadata">
            <dl className="divide-y divide-line-200">
              {[
                ['File type', document.type],
                ['File size', document.size],
                ['Uploaded by', document.owner],
                ['Uploaded', document.uploadedAt],
                ['Last updated', document.updatedAt],
              ].map(([label, value]) => (
                <div key={label} className="flex items-start justify-between gap-4 py-3 first:pt-0 last:pb-0">
                  <dt className="text-meta text-gray-600">{label}</dt>
                  <dd className="text-end text-meta font-semibold text-ink-900" data-user-content>
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
          </SectionCard>

          <section className="rounded-xl border border-leaf-300 bg-mist-50 p-5 shadow-card">
            <span className="flex h-10 w-10 items-center justify-center rounded-l bg-forest-900 text-leaf-300">
              <Icon name="analysis" size={20} />
            </span>
            <h2 className="mt-4 text-panel text-forest-900">Intelligence handoff</h2>
            <p className="mt-1 text-meta text-gray-600">
              No generated intelligence exists for this preview. A connected workflow would require explicit review and provenance.
            </p>
            <Button disabled size="md" className="mt-4 w-full">
              Analysis unavailable in preview
            </Button>
          </section>
        </div>
      </div>
    </div>
  );
}
