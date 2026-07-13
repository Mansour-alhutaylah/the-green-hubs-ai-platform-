import { Link } from 'react-router';
import { DemoDataBadge, Icon, SectionCard, type IconName } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { PageHeader } from '@/shell/PageHeader';
import { ROUTES } from '@/app/navigation/routePaths';
import { cn } from '@/lib/utils/cn';
import { MOCK_DOCUMENTS, type DocumentProcessingStatus } from '../mockDocuments';
import { DocumentStatusBadge } from '../components/DocumentStatusBadge';
import { DocumentCollectionState } from '../components/DocumentCollectionState';

const countStatus = (status: DocumentProcessingStatus) =>
  MOCK_DOCUMENTS.filter((document) => document.status === status).length;

const SUMMARY: Array<{
  label: string;
  value: number;
  detail: string;
  icon: IconName;
  className: string;
}> = [
  {
    label: 'Total documents',
    value: MOCK_DOCUMENTS.length,
    detail: 'Sample source library',
    icon: 'documents',
    className: 'border-leaf-300 bg-mist-50 text-forest-800',
  },
  {
    label: 'Processed',
    value: countStatus('PROCESSED'),
    detail: 'Ready for review',
    icon: 'check',
    className: 'border-leaf-300 bg-leaf-100 text-leaf-700',
  },
  {
    label: 'In progress',
    value: countStatus('PROCESSING') + countStatus('PENDING'),
    detail: 'Preview workflow states',
    icon: 'analysis',
    className: 'border-sky-100 bg-sky-100 text-sky-700',
  },
  {
    label: 'Needs attention',
    value: countStatus('FAILED'),
    detail: 'Controlled failure state',
    icon: 'triangle-alert',
    className: 'border-amber-100 bg-amber-100 text-amber-700',
  },
];

const STATUS_RAIL: Record<DocumentProcessingStatus, string> = {
  PENDING: 'bg-gray-400',
  PROCESSING: 'bg-sky-700',
  PROCESSED: 'bg-leaf-500',
  FAILED: 'bg-red-700',
};

const STATUS_CONTEXT: Record<DocumentProcessingStatus, string> = {
  PENDING: 'Waiting in the sample queue',
  PROCESSING: 'Sample extraction in progress',
  PROCESSED: 'Ready for sample review',
  FAILED: 'Sample processing needs attention',
};

export function DocumentsListPage() {
  const { t } = useLocale();

  return (
    <div>
      <PageHeader
        eyebrow="Source intelligence"
        title={t('nav.documents')}
        subtitle="Review source files, processing journeys, and readiness signals in this presentation-only workspace."
        action={
          <>
            <DemoDataBadge label={t('dashboard.sampleData')} />
            <Link
              to={ROUTES.documentUpload}
              className="inline-flex min-h-10 items-center gap-2 rounded-m bg-forest-900 px-4 text-body font-semibold text-white shadow-raise transition-colors hover:bg-forest-800 active:scale-[var(--scale-press)]"
            >
              <Icon name="upload" size={17} />
              Upload preview
            </Link>
          </>
        }
      />

      <dl className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 min-[1380px]:grid-cols-4">
        {SUMMARY.map((item) => (
          <div
            key={item.label}
            className="surface-lift flex items-center gap-3 rounded-xl border border-line-200 bg-surface-0 p-4 shadow-card"
          >
            <span className={cn('flex h-11 w-11 shrink-0 items-center justify-center rounded-l border', item.className)}>
              <Icon name={item.icon} size={20} />
            </span>
            <div className="min-w-0">
              <dt className="text-caption font-semibold text-gray-600">{item.label}</dt>
              <dd className="mt-0.5 flex items-baseline gap-2">
                <span className="text-title text-forest-900">{item.value}</span>
                <span className="truncate text-caption text-gray-600">{item.detail}</span>
              </dd>
            </div>
          </div>
        ))}
      </dl>

      <DocumentCollectionState state="ready">
        <SectionCard
          className="mt-5 rounded-xl border-leaf-300/60"
          title="Workspace documents"
          description="Every record is local sample content; status combines text, shape, and color."
          action={<span className="text-caption font-semibold text-gray-600">4 sample files</span>}
          contentClassName="p-0 sm:p-0"
        >
          <div className="hidden grid-cols-[minmax(0,1.8fr)_minmax(10rem,1fr)_9rem_9rem] gap-4 border-b border-line-200 bg-mist-50 px-5 py-3 text-caption font-bold text-gray-600 md:grid">
            <span>Document</span>
            <span>Engagement</span>
            <span>Status</span>
            <span>Updated</span>
          </div>

          <ul className="divide-y divide-line-200" aria-label="Sample documents">
            {MOCK_DOCUMENTS.map((document) => (
              <li key={document.id}>
                <Link
                  to={`/documents/${document.id}`}
                  className="group relative grid gap-3 overflow-hidden px-4 py-4 transition-colors hover:bg-mist-50 sm:px-5 md:grid-cols-[minmax(0,1.8fr)_minmax(10rem,1fr)_9rem_9rem] md:items-center md:gap-4"
                >
                  <span className={cn('absolute inset-y-2 start-0 w-1 rounded-e-full', STATUS_RAIL[document.status])} aria-hidden />
                  <span className="flex min-w-0 items-start gap-3">
                    <span className="relative mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-l border border-leaf-300 bg-leaf-100 text-leaf-700 shadow-card" aria-hidden>
                      <Icon name="documents" size={20} />
                      <span className="absolute -bottom-1 -end-1 rounded-s bg-forest-900 px-1 py-0.5 text-micro font-bold text-white">PDF</span>
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-body font-bold text-ink-900 transition-colors group-hover:text-leaf-700" data-user-content>
                        {document.name}
                      </span>
                      <span className="mt-0.5 block text-caption text-gray-600">
                        {document.size} · {document.owner}
                      </span>
                      <span className="mt-1 block text-caption font-medium text-gray-600 md:hidden">
                        {STATUS_CONTEXT[document.status]}
                      </span>
                    </span>
                  </span>
                  <span className="min-w-0">
                    <span className="type-label mb-1 block text-gray-600 md:hidden">Engagement</span>
                    <span className="block truncate text-meta text-gray-600" data-user-content>
                      {document.engagement}
                    </span>
                  </span>
                  <span>
                    <DocumentStatusBadge status={document.status} />
                  </span>
                  <span>
                    <span className="type-label mb-1 block text-gray-600 md:hidden">Updated</span>
                    <time className="text-caption text-gray-600">{document.updatedAt}</time>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </SectionCard>
      </DocumentCollectionState>
    </div>
  );
}
